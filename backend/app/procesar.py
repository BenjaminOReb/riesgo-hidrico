import os
import datetime
import tempfile

import xarray as xr
import numpy as np
import skfuzzy as fuzz
import geopandas as gpd
from rasterio.transform import from_origin
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
    ds = xr.open_dataset(ruta_archivo, decode_times=False)
    # detecta variable
    if 'pr' in ds.data_vars:
        var = 'pr'
    elif 't2m' in ds.data_vars:
        var = 't2m'
    else:
        raise ValueError("No se reconoce variable 'pr' o 't2m'")
    da    = ds[var]
    datos = da.values.astype(float)  # (time, lat, lon)
    # --- transformación log para pr ----
    if var == 'pr':
        datos = np.log10(np.where(np.isnan(datos), np.nan, datos) + 0.1)
    T, Y, X = datos.shape

    # rasteriza regiones
    regiones = gpd.read_file("shapefiles/regiones/Regional.shp").to_crs(epsg=4326)
    regiones['rid'] = np.arange(len(regiones))
    lons = ds['lon'].values; lats = ds['lat'].values
    transform = Affine.translation(lons[0]-0.25, lats[0]-0.25) * Affine.scale(0.05, 0.05)
    mask2d = features.rasterize(
        [(geom, rid) for geom,rid in zip(regiones.geometry, regiones.rid)],
        out_shape=(Y, X), transform=transform, fill=-1, dtype='int16'
    )

    baja_3d  = np.zeros_like(datos)
    media_3d = np.zeros_like(datos)
    alta_3d  = np.zeros_like(datos)

    for rid in np.unique(mask2d):
        if rid < 0: continue
        mask3d = (mask2d == rid)[None,:,:]
        mask3d = np.broadcast_to(mask3d, datos.shape)
        vals = datos[mask3d]
        vals = vals[~np.isnan(vals)]
        if vals.size == 0: continue

        # usa percentiles para los trapézios
        m, M = vals.min(), vals.max()
        p10, p50, p90 = np.nanpercentile(vals, [10,50,90])
        TL_low  = [m, m, p10,  p50]
        TL_med  = [p10, p50, p50, p90]
        TL_high = [p50, p90, M,   M]

        uni      = np.linspace(m, M, 1000)
        mf_low   = fuzz.trapmf(uni, TL_low)
        mf_med   = fuzz.trapmf(uni, TL_med)
        mf_high  = fuzz.trapmf(uni, TL_high)

        # mascara región
        regs = np.where(mask3d, datos, np.nan)
        baja_3d[mask3d]  = fuzz.interp_membership(uni, mf_low,  regs)[mask3d]
        media_3d[mask3d] = fuzz.interp_membership(uni, mf_med,  regs)[mask3d]
        alta_3d[mask3d]  = fuzz.interp_membership(uni, mf_high, regs)[mask3d]

    # añade variables al dataset
    ds[f"{var}_baja"]  = (da.dims, baja_3d)
    ds[f"{var}_media"] = (da.dims, media_3d)
    ds[f"{var}_alta"]  = (da.dims, alta_3d)

    ds = limpiar_atributos_conflictivos(ds)
    nombre_base = generar_nombre_base(ds)
    ruta_salida = os.path.join(carpeta_salida, f"fuzzy_{var}_{nombre_base}.nc")
    ds.to_netcdf(ruta_salida)
    ds.close()

    return {
        'archivo_salida': ruta_salida,
        'tipo_variable': var,
        'nombre_base': nombre_base,
        'mensaje': "Capas fuzzy calculadas por región (percentiles/log)."
    }


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
    # 1) Asegurar CRS en EPSG:4326
    if zona_gdf.crs != "EPSG:4326":
        zona_gdf = zona_gdf.to_crs(epsg=4326)

    # 2) Abrir NetCDF y extraer la capa requerida
    ds   = xr.open_dataset(ruta_netcdf, decode_times=False)
    data = ds[var_name].isel(time=indice_tiempo).values
    lons = ds["lon"].values
    lats = ds["lat"].values
    ds.close()

    # 3) Asegurar orientación: latitudes de Norte a Sur
    if lats[0] > lats[-1]:
        data = data[::-1, :]
        lats = lats[::-1]

    # 4) Definir transform con from_origin
    dx = float(lons[1] - lons[0])
    dy = float(lats[1] - lats[0])
    transform = from_origin(
        west=lons.min(),
        north=lats.max(),
        xsize=dx,
        ysize=dy
    )

    # 5) Rasterizar la geometría de la zona
    mask = features.rasterize(
        ((geom, 1) for geom in zona_gdf.geometry),
        out_shape=data.shape,
        transform=transform,
        fill=0,
        dtype="uint8"
    )

    # 6) Aplicar la máscara (fuera de la zona → NaN)
    data_mask = np.where(mask == 1, data, np.nan)

    # 7) Generar el archivo GeoTIFF temporal
    tmp = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
    with rasterio.open(
        tmp.name,
        "w",
        driver="GTiff",
        height=data_mask.shape[0],
        width=data_mask.shape[1],
        count=1,
        dtype="float32",
        crs=CRS.from_epsg(4326),
        transform=transform,
        nodata=np.nan
    ) as dst:
        dst.write(data_mask.astype(np.float32), 1)

    return tmp.name