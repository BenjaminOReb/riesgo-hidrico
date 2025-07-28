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

    # 1) Abrir NetCDF original
    raw = xr.open_dataset(ruta_archivo, decode_times=False)
    da = raw['pr'] if 'pr' in raw else raw['t2m']
    var = da.name
    datos = da.values.astype(float)  # (time, lat, lon)

    # 2) Log si es precipitación
    if var == 'pr':
        datos = np.log10(datos + 0.1)

    T, Y, X = datos.shape

    # 3) Guardar rejilla original
    lons = raw['lon'].values.copy()
    lats = raw['lat'].values.copy()

    # 4) Rasterizar regiones
    regiones = (
        gpd.read_file("shapefiles/regiones/Regional.shp")
           .to_crs(epsg=4326)
           .assign(rid=lambda df: np.arange(len(df)))
    )
    transform = from_bounds(
        lons.min(), lats.min(), lons.max(), lats.max(),
        width=X, height=Y
    )
    mask2d = features.rasterize(
        [(g, rid) for g, rid in zip(regiones.geometry, regiones.rid)],
        out_shape=(Y, X), transform=transform,
        fill=-1, dtype='int16'
    )

    # 5) Inicializar arrays fuzzy
    baja  = np.zeros_like(datos);  baja [np.isnan(datos)] = np.nan
    media = np.zeros_like(datos); media[np.isnan(datos)] = np.nan
    alta  = np.zeros_like(datos);  alta [np.isnan(datos)] = np.nan

    # 6) Calcular memberships
    for rid in np.unique(mask2d):
        if rid < 0: continue
        msk2 = (mask2d == rid)
        msk3 = np.broadcast_to(msk2[None], datos.shape)
        valid = msk3 & ~np.isnan(datos)
        if not valid.any(): continue

        vals = datos[valid]
        m, M = vals.min(), vals.max()
        L8 = (M - m)/8.0
        L2 = (M + m)/2.0
        uni = np.linspace(m, M, 1000)

        mf_low  = fuzz.trapmf(uni, [m,    m,    m+L8,   m+3*L8])
        mf_med  = fuzz.trapmf(uni, [L2-3*L8, L2-L8, L2+L8, L2+3*L8])
        mf_high = fuzz.trapmf(uni, [M-3*L8,   M-L8,   M,      M])

        v = datos[valid]
        baja [valid] = fuzz.interp_membership(uni, mf_low,  v)
        media[valid] = fuzz.interp_membership(uni, mf_med,  v)
        alta [valid] = fuzz.interp_membership(uni, mf_high, v)

    # 7) Forzar orientación:  
    #    Si latitudes van de Sur→Norte, invertimos eje lat (axis=1).
    if lats[0] < lats[-1]:
        baja  = baja[:, ::-1, :]
        media = media[:, ::-1, :]
        alta  = alta[:, ::-1, :]
        lats = lats[::-1]
    #    Si longitudes van de Este→Oeste, invertimos eje lon (axis=2).
    if lons[0] > lons[-1]:
        baja  = baja[:, :, ::-1]
        media = media[:, :, ::-1]
        alta  = alta[:, :, ::-1]
        lons = lons[::-1]

    # 8) Crear DataArrays con coords y dims exactos
    coords = {'time': raw['time'], 'lat': lats, 'lon': lons}
    dims = ('time','lat','lon')
    da_baja  = xr.DataArray(baja,  dims=dims, coords=coords, name=f"{var}_baja")
    da_media = xr.DataArray(media, dims=dims, coords=coords, name=f"{var}_media")
    da_alta  = xr.DataArray(alta,  dims=dims, coords=coords, name=f"{var}_alta")

    # 9) Montar Dataset de salida
    ds = raw.assign({da_baja.name: da_baja,
                     da_media.name: da_media,
                     da_alta.name: da_alta})
    ds = ds.transpose('time','lat','lon')

    # 10) Guardar y cerrar
    ds = limpiar_atributos_conflictivos(ds)
    base = generar_nombre_base(ds)
    out = os.path.join(carpeta_salida, f"fuzzy_{var}_{base}.nc")
    ds.to_netcdf(out)
    raw.close()
    ds.close()

    return {'archivo_salida': out, 'tipo_variable': var,
            'nombre_base': base, 'mensaje': "Capas fuzzy calculadas."}

def calcular_indice_riesgo_fuzzy(pr_path, t2m_path, carpeta_salida="uploads/riesgo_fuzzy"):
    
    # Genera un NetCDF con índice de riesgo fuzzy = max(pr_baja, t2m_alta).
    
    os.makedirs(carpeta_salida, exist_ok=True)
    pr_ds  = xr.open_dataset(pr_path,  decode_times=False)
    t2m_ds = xr.open_dataset(t2m_path, decode_times=False)
    pr_baja  = pr_ds['pr_baja'].values
    t2m_alta = t2m_ds['t2m_alta'].values
    riesgo_fuzzy = np.maximum(pr_baja, t2m_alta)
    coords = pr_ds.coords

    ds_r = xr.Dataset({"riesgo_fuzzy": (("time","lat","lon"), riesgo_fuzzy)}, coords=coords)
    ds_r = limpiar_atributos_conflictivos(ds_r)
    nombre_base = generar_nombre_base(pr_ds)
    ruta_salida = os.path.join(carpeta_salida, f"riesgo_fuzzy_{nombre_base}.nc")
    ds_r.to_netcdf(ruta_salida)

    pr_ds.close()
    t2m_ds.close()
    ds_r.close()

    return {'archivo': ruta_salida, 'nombre_base': nombre_base, 'mensaje': 'Índice fuzzy generado'}


def calcular_indice_riesgo_raw(pr_path, t2m_path, carpeta_salida="uploads/riesgo_raw"):
    
    #Genera un NetCDF con índice de riesgo crudo:
    #riesgo_raw = max(1 - pr_norm, t2m_norm)
    
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

    raw = np.maximum(1 - pr_norm, t_norm)

    ds_raw = xr.Dataset({"riesgo_raw": (("time","lat","lon"), raw)}, coords=coords)
    ds_raw = limpiar_atributos_conflictivos(ds_raw)
    nombre_base = generar_nombre_base(ds_pr)
    ruta_salida = os.path.join(carpeta_salida, f"riesgo_raw_{nombre_base}.nc")
    ds_raw.to_netcdf(ruta_salida)

    ds_pr.close()
    ds_t2m.close()
    ds_raw.close()

    return {'archivo': ruta_salida, 'nombre_base': nombre_base, 'mensaje': 'Índice raw generado'}


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