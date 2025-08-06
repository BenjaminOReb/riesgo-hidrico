import os
import datetime
import tempfile

import xarray as xr
import numpy as np
import skfuzzy as fuzz
import geopandas as gpd
from rasterio.transform import from_origin
from rasterio.transform import from_bounds
from rasterio.crs import CRS
from rasterio import features
from affine import Affine
import rasterio

ZONE_MAP = {
    'region':    ('shapefiles/regiones/Regional.shp',     'Region'),
    'provincia': ('shapefiles/provincias/Provincias.shp', 'Provincia'),
    'comuna':    ('shapefiles/comunas/comunas.shp',       'Comuna')
}

def limpiar_atributos_conflictivos(ds):
    
    # Elimina atributos y codificaciones conflictivos al escribir NetCDF.
    
    for v in ds.variables:
        if '_FillValue' in ds[v].encoding:
            del ds[v].encoding['_FillValue']
        if 'missing_value' in ds[v].attrs:
            del ds[v].attrs['missing_value']
    return ds


def generar_nombre_base(ds):
    
    # Genera un nombre base 'YYYY-MM' a partir del último step temporal.
    
    try:
        ultimo = ds.sizes['time'] - 1
        valor  = ds['time'].values[ultimo]
        base   = datetime.datetime(1978, 12, 15)
        fecha  = base + datetime.timedelta(days=int(valor * 30))
        return f"{fecha.year}-{fecha.month:02d}"
    except Exception:
        return datetime.datetime.now().strftime('%Y-%m')


def recortar_ultimos_5_anos(ruta_archivo, carpeta_salida="uploads/recortado"):
    
    # Abre un NetCDF y guarda los últimos 60 pasos temporales en un nuevo archivo.
    # Retorna la ruta al .nc recortado.
    
    os.makedirs(carpeta_salida, exist_ok=True)
    ds = xr.open_dataset(ruta_archivo, decode_times=False)
    if 'time' not in ds.dims or ds.sizes['time'] < 60:
        raise ValueError("El archivo no tiene al menos 60 pasos de tiempo")
    tipo = 'pr' if 'pr' in ds.data_vars else 't2m' if 't2m' in ds.data_vars else 'desconocido'
    ds_rec = ds.isel(time=slice(-60, None))
    nombre_base = generar_nombre_base(ds_rec)
    ds_rec = limpiar_atributos_conflictivos(ds_rec)
    ruta_salida = os.path.join(carpeta_salida, f"{tipo}_{nombre_base}_recortado.nc")
    ds_rec.to_netcdf(ruta_salida)
    ds.close()
    return ruta_salida


def generar_capas_fuzzy(ruta_archivo, carpeta_salida="uploads/fuzzy"):
    os.makedirs(carpeta_salida, exist_ok=True)

    # 1) Abrir el NetCDF original
    ds_crisp = xr.open_dataset(ruta_archivo, decode_times=False)
    if 'pr' in ds_crisp.data_vars:
        var = 'pr'
    elif 't2m' in ds_crisp.data_vars:
        var = 't2m'
    else:
        ds_crisp.close()
        raise ValueError("No se reconoce variable 'pr' o 't2m'")

    da = ds_crisp[var]                        # DataArray (time, lat, lon)
    datos = da.values.astype(float)         # numpy array

    # 2) Log10 si es precipitación
    if var == 'pr':
        datos = np.log10(datos + 0.1)

    # 3) Guardar rejilla original
    orig_lons = ds_crisp.lon.values.copy()
    orig_lats = ds_crisp.lat.values.copy()
    T, Y, X = datos.shape

    # 4) Rasterizar regiones
    regiones = (gpd.read_file("shapefiles/regiones/Regional.shp")
                    .to_crs(epsg=4326)
                    .assign(rid=lambda df: np.arange(len(df))))
    transform = from_bounds(
        orig_lons.min(), orig_lats.max(),
        orig_lons.max(), orig_lats.min(),
        width=X, height=Y
    )
    mask2d = features.rasterize(
        [(g, rid) for g, rid in zip(regiones.geometry, regiones.rid)],
        out_shape=(Y, X),
        transform=transform,
        fill=-1,
        dtype='int16'
    )

    mask3d_invalid = np.broadcast_to(mask2d[None, :, :] == -1, datos.shape)
    # 5) Preparar arrays fuzzy
    baja  = np.zeros_like(datos);  baja [np.isnan(datos)] = np.nan
    media = np.zeros_like(datos); media[np.isnan(datos)] = np.nan
    alta  = np.zeros_like(datos);  alta [np.isnan(datos)] = np.nan

    baja [mask3d_invalid] = np.nan
    media[mask3d_invalid] = np.nan
    alta [mask3d_invalid] = np.nan

    # 6) Calcular membresías
    for rid in np.unique(mask2d):
        if rid < 0: 
            continue
        region_mask2d = (mask2d == rid)

        for t in range(T):
            datos_t    = datos[t, :, :]
            valid_mask = region_mask2d & ~np.isnan(datos_t)
            if not valid_mask.any():
                continue

            vals = datos_t[valid_mask]          # ¡solo este mes!
            m, M = float(vals.min()), float(vals.max())
            L8   = (M - m) / 8.0
            L2   = (M + m) / 2.0
            uni  = np.linspace(m, M, 1000)

            mf_low  = fuzz.trapmf(uni, [m,    m,    m+L8,   m+3*L8])
            mf_med  = fuzz.trapmf(uni, [L2-3*L8, L2-L8, L2+L8, L2+3*L8])
            mf_high = fuzz.trapmf(uni, [M-3*L8,   M-L8,   M,      M])

            v = datos_t[valid_mask]
            baja [t, valid_mask] = fuzz.interp_membership(uni, mf_low,  v)
            media[t, valid_mask] = fuzz.interp_membership(uni, mf_med,  v)
            alta [t, valid_mask] = fuzz.interp_membership(uni, mf_high, v)

    # 7) Voltear arrays si la rejilla original está invertida
    #    latitudes
    if orig_lats[0] < orig_lats[-1]:
        baja  = baja[:, ::-1, :]
        media = media[:, ::-1, :]
        alta  = alta[:, ::-1, :]
        orig_lats = orig_lats[::-1]
    #    longitudes
    if orig_lons[0] > orig_lons[-1]:
        baja  = baja[:, :, ::-1]
        media = media[:, :, ::-1]
        alta  = alta[:, :, ::-1]
        orig_lons = orig_lons[::-1]

    # 8) Crear DataArrays fuzzy con las coords corregidas
    coords = {'time': ds_crisp.time, 'lat': orig_lats, 'lon': orig_lons}
    dims = ('time', 'lat', 'lon')
    da_baja  = xr.DataArray(baja,  dims=dims, coords=coords, name=f"{var}_baja")
    da_media = xr.DataArray(media, dims=dims, coords=coords, name=f"{var}_media")
    da_alta  = xr.DataArray(alta,  dims=dims, coords=coords, name=f"{var}_alta")

    # 9) Montar y ordenar Dataset de salida
    ds_out = ds_crisp.assign({
        da_baja.name:  da_baja,
        da_media.name: da_media,
        da_alta.name:  da_alta
    })
    ds_out = ds_out.transpose('time','lat','lon')

    # 10) Guardar y cerrar
    ds_out = limpiar_atributos_conflictivos(ds_out)
    nombre_base = generar_nombre_base(ds_out)
    ruta_salida = os.path.join(carpeta_salida, f"fuzzy_{var}_{nombre_base}.nc")
    ds_out.to_netcdf(ruta_salida)
    ds_crisp.close()
    ds_out.close()

    return {
        'archivo_salida': ruta_salida,
        'tipo_variable': var,
        'nombre_base': nombre_base,
        'mensaje': "Capas fuzzy calculadas por región."
    }


def calcular_indice_riesgo_fuzzy(pr_path, t2m_path, carpeta_salida="uploads/riesgo_fuzzy"):
    # Genera un NetCDF con las nueve componentes:
    #  - riesgo_alto_A:  pr_baja
    #  - riesgo_alto_B:  t2m_alta
    #  - riesgo_medio_A: pr_media
    #  - riesgo_medio_B: t2m_media
    #  - riesgo_medio_C: min(pr_media, t2m_media)
    #  - riesgo_medio_D: max(pr_media, t2m_media)
    #  - riesgo_medio_E: (pr_media + t2m_media) / 2
    #  - riesgo_bajo_A:  pr_alta
    #  - riesgo_bajo_B:  t2m_baja

    os.makedirs(carpeta_salida, exist_ok=True)
    pr_ds  = xr.open_dataset(pr_path,  decode_times=False)
    t2m_ds = xr.open_dataset(t2m_path, decode_times=False)

    # Extraer arrays numpy directamente como en la versión original para evitar alineación
    pr_baja   = pr_ds['pr_baja'].values
    pr_media  = pr_ds['pr_media'].values
    pr_alta   = pr_ds['pr_alta'].values
    t2m_baja  = t2m_ds['t2m_baja'].values
    t2m_media = t2m_ds['t2m_media'].values
    t2m_alta  = t2m_ds['t2m_alta'].values

    # Calcular las componentes solicitadas
    riesgo_alto_A  = np.minimum(t2m_alta,  pr_baja)  # Tem Alta + Pr Baja 
    riesgo_alto_B  = np.minimum(t2m_media, pr_baja)  # Tem Media + Pr Baja

    riesgo_medio_A = np.minimum(t2m_baja,  pr_baja)  # Tem Baja + Pr Baja
    riesgo_medio_B = np.minimum(t2m_alta,  pr_media) # Tem Alta + Pr Media
    riesgo_medio_C = np.minimum(t2m_media, pr_media) # Tem Media + Pr Media
    riesgo_medio_D = np.minimum(t2m_baja,  pr_media) # Tem Baja + Pr Media
    riesgo_medio_E = np.minimum(t2m_alta,  pr_alta)  # Tem Alta + Pr Alta

    riesgo_bajo_A  = np.minimum(t2m_media, pr_alta)  # Tem Media + Pr Alta
    riesgo_bajo_B  = np.minimum(t2m_baja,  pr_alta)  # Tem Baja + Pr Alta

    riesgo_alto  = np.maximum(riesgo_alto_A, riesgo_alto_B)
    riesgo_medio = np.maximum.reduce([
        riesgo_medio_A,
        riesgo_medio_B,
        riesgo_medio_C,
        riesgo_medio_D,
        riesgo_medio_E
    ])
    riesgo_bajo  = np.maximum(riesgo_bajo_A, riesgo_bajo_B)

    riesgo_fuzzy = np.maximum.reduce([riesgo_alto, riesgo_medio, riesgo_bajo])

    coords = pr_ds.coords

    ds_r = xr.Dataset({
        "riesgo_alto_A":   (("time", "lat", "lon"), riesgo_alto_A),
        "riesgo_alto_B":   (("time", "lat", "lon"), riesgo_alto_B),
        "riesgo_medio_A":  (("time", "lat", "lon"), riesgo_medio_A),
        "riesgo_medio_B":  (("time", "lat", "lon"), riesgo_medio_B),
        "riesgo_medio_C":  (("time", "lat", "lon"), riesgo_medio_C),
        "riesgo_medio_D":  (("time", "lat", "lon"), riesgo_medio_D),
        "riesgo_medio_E":  (("time", "lat", "lon"), riesgo_medio_E),
        "riesgo_bajo_A":   (("time", "lat", "lon"), riesgo_bajo_A),
        "riesgo_bajo_B":   (("time", "lat", "lon"), riesgo_bajo_B),
        "riesgo_alto":   (("time", "lat", "lon"), riesgo_alto),
        "riesgo_medio":  (("time", "lat", "lon"), riesgo_medio),
        "riesgo_bajo":   (("time", "lat", "lon"), riesgo_bajo),
        "riesgo_fuzzy":  (("time", "lat", "lon"), riesgo_fuzzy),
    }, coords=coords)

    ds_r = limpiar_atributos_conflictivos(ds_r)
    nombre_base = generar_nombre_base(pr_ds)
    ruta_salida = os.path.join(carpeta_salida, f"riesgo_fuzzy_{nombre_base}.nc")
    ds_r.to_netcdf(ruta_salida)

    pr_ds.close()
    t2m_ds.close()
    ds_r.close()

    return {'archivo': ruta_salida, 'nombre_base': nombre_base, 'mensaje': 'Índice fuzzy descompuesto generado'}


def calcular_indice_riesgo_crisp(pr_path, t2m_path, carpeta_salida="uploads/riesgo_crisp"):
    
    #Genera un NetCDF con índice de riesgo crisp:
    #riesgo_crisp = max(1 - pr_norm, t2m_norm)
    
    os.makedirs(carpeta_salida, exist_ok=True)
    ds_pr  = xr.open_dataset(pr_path,  decode_times=False)
    ds_t2m = xr.open_dataset(t2m_path, decode_times=False)

    pr   = ds_pr['pr'].values.astype(float)
    t2m  = ds_t2m['t2m'].values.astype(float)
    coords = ds_pr.coords

    pr_min, pr_max = np.nanmin(pr), np.nanmax(pr)
    t_min,  t_max  = np.nanmin(t2m), np.nanmax(t2m)
    pr_norm = (pr - pr_min) / (pr_max - pr_min + 1e-9)
    t_norm  = (t2m - t_min) / (t_max - t_min  + 1e-9)

    crisp = np.maximum(1 - pr_norm, t_norm)

    ds_crisp = xr.Dataset({"riesgo_crisp": (("time","lat","lon"), crisp)}, coords=coords)
    ds_crisp = limpiar_atributos_conflictivos(ds_crisp)
    nombre_base = generar_nombre_base(ds_pr)
    ruta_salida = os.path.join(carpeta_salida, f"riesgo_crisp_{nombre_base}.nc")
    ds_crisp.to_netcdf(ruta_salida)

    ds_pr.close()
    ds_t2m.close()
    ds_crisp.close()

    return {'archivo': ruta_salida, 'nombre_base': nombre_base, 'mensaje': 'Índice crisp generado'}


def calcular_fecha_desde_indice(nombre_base, indice):
    
    # Dado 'YYYY-MM' y un índice (1–60), devuelve la fecha inicial correspondiente.
    
    año_fin, mes_fin = map(int, nombre_base.split('-'))
    fecha_fin = datetime.date(año_fin, mes_fin, 1)
    meses_restar = 60 - indice
    año = fecha_fin.year
    mes = fecha_fin.month - meses_restar
    while mes <= 0:
        mes += 12
        año -= 1
    return f"{año}-{mes:02d}"


def generar_geotiff_zona(zona_gdf, ruta_netcdf, indice_tiempo, var_name):
    """
    Genera un GeoTIFF recortado a la geometría zona_gdf, a partir de la variable var_name
    en el netCDF ruta_netcdf en el paso temporal indice_tiempo.
    Corrige la orientación de eje X e Y para que se muestre correctamente en Leaflet.
    """

    # 1) Asegurar CRS de la zona
    if zona_gdf.crs is None or zona_gdf.crs.to_string() != "EPSG:4326":
        zona_gdf = zona_gdf.to_crs(epsg=4326)

    # 2) Abrir el netCDF y extraer la capa (no decodificamos time)
    ds = xr.open_dataset(ruta_netcdf, decode_times=False)
    if var_name not in ds.data_vars:
        ds.close()
        raise KeyError(f"Variable {var_name} no encontrada en {ruta_netcdf}")
    data = ds[var_name].isel(time=indice_tiempo).values.astype(np.float32)
    lons = ds["lon"].values.copy()
    lats = ds["lat"].values.copy()
    ds.close()

    # 3) Forzar orientación de Z:
    #    latitudes de Norte→Sur (descendiente)
    if lats[0] < lats[-1]:
        data = data[::-1, :]
        lats = lats[::-1]
    #    longitudes de Oeste→Este (ascendiente)
    if lons[0] > lons[-1]:
        data = data[:, ::-1]
        lons = lons[::-1]

    # 4) Calcular resolución y transform
    dx = float(lons[1] - lons[0])
    dy = float(lats[0] - lats[1])  # lats[0]>lats[1] tras invertir
    transform = from_origin(
        west=lons.min(),
        north=lats.max(),
        xsize=dx,
        ysize=dy
    )

    # 5) Rasterizar la zona (1 dentro, 0 fuera)
    mask = features.rasterize(
        ((geom, 1) for geom in zona_gdf.geometry),
        out_shape=data.shape,
        transform=transform,
        fill=0,
        dtype="uint8"
    )

    # 6) Aplicar máscara: fuera de zona → nodata
    data_mask = np.where(mask == 1, data, np.nan)

    # 7) Crear GeoTIFF temporal
    tmp = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
    profile = {
        "driver": "GTiff",
        "height": data_mask.shape[0],
        "width": data_mask.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": CRS.from_epsg(4326),
        "transform": transform,
        "nodata": np.nan,
        # Opciones de rendimiento
        "compress": "lzw",
        "tiled": True,
    }

    with rasterio.open(tmp.name, "w", **profile) as dst:
        dst.write(data_mask, 1)
        # Escribimos la máscara interna (0 transparente, 255 opaco)
        dst.write_mask((mask * 255).astype("uint8"))

    return tmp.name


def calcular_stats_fuzzy(zona_gdf, ruta_netcdf, indice_tiempo, var_name):
    """
    Calcula las funciones de pertenencia (baja, media, alta) para la variable var_name
    ('pr' o 't2m') en el NetCDF ruta_netcdf, recortada a la geometría zona_gdf
    y al paso temporal indice_tiempo. Devuelve un dict con:
      - 'categories': dominio de entrada (100 puntos)
      - 'baja', 'media', 'alta': listas con el grado de pertenencia [0–1]
    """

    # 1) Asegurar CRS en EPSG:4326
    if zona_gdf.crs is None or zona_gdf.crs.to_string() != "EPSG:4326":
        zona_gdf = zona_gdf.to_crs(epsg=4326)

    # 2) Abrir NetCDF y extraer la capa deseada
    ds = xr.open_dataset(ruta_netcdf, decode_times=False)
    if var_name not in ds.data_vars:
        ds.close()
        raise KeyError(f"Variable '{var_name}' no encontrada en {ruta_netcdf}")
    da = ds[var_name].isel(time=indice_tiempo)  # DataArray (lat, lon)
    data2d = da.values.astype(float)
    lons = da["lon"].values
    lats = da["lat"].values
    ds.close()

    # 3) Forzar orientación: lat Norte→Sur, lon Oeste→Este
    if lats[0] < lats[-1]:
        data2d = data2d[::-1, :]
        lats = lats[::-1]
    if lons[0] > lons[-1]:
        data2d = data2d[:, ::-1]
        lons = lons[::-1]

    # 4) Rasterizar la zona (1 dentro, 0 fuera)
    transform = from_bounds(
        lons.min(), lats.min(),
        lons.max(), lats.max(),
        width=data2d.shape[1],
        height=data2d.shape[0]
    )
    mask2d = features.rasterize(
        [(geom, 1) for geom in zona_gdf.geometry],
        out_shape=data2d.shape,
        transform=transform,
        fill=0,
        dtype="uint8"
    )

    # 5) Extraer valores válidos dentro de la zona
    vals = data2d[mask2d == 1]
    vals = vals[~np.isnan(vals)]
    if vals.size == 0:
        raise ValueError("No hay datos válidos en esa zona/fecha")

    # 6) Calcular parámetros trapezoidales
    m, M = float(vals.min()), float(vals.max())
    L8 = (M - m) / 8.0
    L2 = (M + m) / 2.0
    TL_low  = [m,      m,       m+L8,    m+3*L8]
    TL_med  = [L2-3*L8, L2-L8,  L2+L8,   L2+3*L8]
    TL_high = [M-3*L8,  M-L8,   M,       M]

    # 7) Generar las MFs sobre un dominio de 100 puntos
    uni    = np.linspace(m, M, 100)
    baja   = fuzz.trapmf(uni, TL_low).tolist()
    media  = fuzz.trapmf(uni, TL_med).tolist()
    alta   = fuzz.trapmf(uni, TL_high).tolist()

    return {
        "categories": uni.tolist(),
        "baja":       baja,
        "media":      media,
        "alta":       alta
    }