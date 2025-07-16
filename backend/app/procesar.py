import xarray as xr
import numpy as np
import skfuzzy as fuzz
import geopandas as gpd
import rasterio
import tempfile

from rasterio.transform import from_origin
from rasterio.crs import CRS
from rasterio import features
from affine import Affine

import os
import datetime


def limpiar_atributos_conflictivos(ds):

    # Elimina atributos y codificaciones que suelen causar
    # problemas al escribir NetCDF (por ejemplo _FillValue o missing_value).

    for v in ds.variables:
        if '_FillValue' in ds[v].encoding:
            del ds[v].encoding['_FillValue']
        if 'missing_value' in ds[v].attrs:
            del ds[v].attrs['missing_value']
    return ds


def generar_nombre_base(ds):

    # Genera un nombre base en formato 'YYYY-MM' tomando el
    # último valor de time del dataset y sumándolo a la fecha base
    # 1978-12-15 (multiplicado por 30 días).
    # En caso de error, devuelve la fecha actual.

    try:
        ultimo_indice = ds.sizes['time'] - 1
        ultimo_valor = ds['time'].values[ultimo_indice]
        base_fecha = datetime.datetime(1978, 12, 15)
        # Asume que cada unidad de time es un mes ≈ 30 días
        fecha = base_fecha + datetime.timedelta(days=int(ultimo_valor * 30))
        return f"{fecha.year}-{fecha.month:02d}"
    except Exception:
        # Fallback a la fecha actual si algo falla
        return datetime.datetime.now().strftime('%Y-%m')


def recortar_ultimos_5_anos(ruta_archivo, carpeta_salida="uploads/recortado"):

    # Abre un NetCDF, verifica que tenga al menos 60 pasos
    # temporales (5 años de datos mensuales), corta los últimos
    # 60 y guarda un nuevo NetCDF recortado.

    os.makedirs(carpeta_salida, exist_ok=True)
    ds = xr.open_dataset(ruta_archivo, decode_times=False)

    # Verificación mínima de 60 pasos en dimensión time
    if 'time' not in ds.dims or ds.sizes['time'] < 60:
        raise ValueError("El archivo no tiene al menos 60 pasos de tiempo")

    # Determinar variable principal (pr o t2m)
    tipo = 'pr' if 'pr' in ds.data_vars else 't2m' if 't2m' in ds.data_vars else 'desconocido'
    
    # Seleccionar los últimos 60 pasos temporales
    ds_recortado = ds.isel(time=slice(-60, None))
    nombre_base = generar_nombre_base(ds_recortado)
    ds_recortado = limpiar_atributos_conflictivos(ds_recortado)

    # Guardar NetCDF recortado
    ruta_salida = os.path.join(carpeta_salida, f"{tipo}_{nombre_base}_recortado.nc")
    ds_recortado.to_netcdf(ruta_salida)
    ds.close()

    return ruta_salida


def generar_capas_fuzzy(ruta_archivo, carpeta_salida="uploads/fuzzy"):

    # Genera tres capas fuzzy (baja, media, alta) para la variable
    # pr o t2m en el NetCDF indicado, usando funciones
    # trapezoidales de scikit-fuzzy. Devuelve rutas y metadatos.

    os.makedirs(carpeta_salida, exist_ok=True)
    ds = xr.open_dataset(ruta_archivo, decode_times=False)

    # Elegir rangos para pr o t2m
    if 'pr' in ds.data_vars:
        var = 'pr'
        rango_baja = [0, 0, 10, 30]
        rango_media = [20, 35, 50, 65]
        rango_alta = [60, 80, 120, 150]
    elif 't2m' in ds.data_vars:
        var = 't2m'
        rango_baja = [0, 0, 10, 15]
        rango_media = [12, 17, 22, 27]
        rango_alta = [25, 28, 35, 40]
    else:
        raise ValueError("No se reconoce variable 'pr' o 't2m'")

    # Extracción y aplanado de valores (sin NaNs)
    datos = ds[var].values
    valores = datos.flatten()
    valores = valores[~np.isnan(valores)]

    # Universo para la membresía fuzzy
    universo = np.linspace(valores.min(), valores.max(), 1000)

    # Cálculo de membresías trapezoidales en 3D
    baja_3d = fuzz.interp_membership(universo, fuzz.trapmf(universo, rango_baja), datos)
    media_3d = fuzz.interp_membership(universo, fuzz.trapmf(universo, rango_media), datos)
    alta_3d = fuzz.interp_membership(universo, fuzz.trapmf(universo, rango_alta), datos)

    # Añade las nuevas variables al dataset
    ds[var + '_baja'] = (('time', 'lat', 'lon'), baja_3d)
    ds[var + '_media'] = (('time', 'lat', 'lon'), media_3d)
    ds[var + '_alta'] = (('time', 'lat', 'lon'), alta_3d)

    ds = limpiar_atributos_conflictivos(ds)
    nombre_base = generar_nombre_base(ds)

    # Guardar NetCDF con las capas fuzzy
    ruta_salida = os.path.join(carpeta_salida, f"fuzzy_{var}_{nombre_base}.nc")
    ds.to_netcdf(ruta_salida)
    ds.close()

    return {
        'archivo_salida': ruta_salida,
        'tipo_variable': var,
        'nombre_base': nombre_base,
        'mensaje': f"Capas fuzzy generadas: {var}_baja, media, alta"
    }


def calcular_indice_riesgo(pr_path, t2m_path, carpeta_salida="uploads/riesgo"):

    # Combina las capas fuzzy de pr y t2m para generar un índice
    # de riesgo hídrico entre 0 y 1. Riesgo por lluvia =
    # max(pr_baja, pr_alta), luego mezcla con t2m_alta.

    os.makedirs(carpeta_salida, exist_ok=True)

    # Abrir ambos NetCDF
    pr_ds = xr.open_dataset(pr_path, decode_times=False)
    t2m_ds = xr.open_dataset(t2m_path, decode_times=False)

    # Lee las capas pertinentes
    pr_baja = pr_ds['pr_baja'].values
    pr_alta = pr_ds['pr_alta'].values
    t2m_alta = t2m_ds['t2m_alta'].values

    # Riesgo de lluvia = cuando pr está muy bajo o muy alto
    riesgo_lluvia = np.maximum(pr_baja, pr_alta)  # entre 0 y 1

    # Mezcla lineal (60% lluvia, 40% temperatura)
    riesgo = np.clip(0.6 * riesgo_lluvia + 0.4 * t2m_alta, 0, 1)
    
    # Empaqueta en un nuevo Dataset
    coords = pr_ds.coords
    ds_riesgo = xr.Dataset({"riesgo_hidrico": (("time", "lat", "lon"), riesgo)}, coords=coords)
    ds_riesgo = limpiar_atributos_conflictivos(ds_riesgo)

    # Generar nombre y guardar
    nombre_base = generar_nombre_base(pr_ds)
    ruta_salida = os.path.join(carpeta_salida, f"riesgo_{nombre_base}.nc")

    # Cerrar datasets
    ds_riesgo.to_netcdf(ruta_salida)
    pr_ds.close()
    t2m_ds.close()
    ds_riesgo.close()

    return {
        'archivo': ruta_salida,
        'nombre_base': nombre_base,
        'mensaje': 'Índice de riesgo hídrico generado correctamente'
    }


def calcular_fecha_desde_indice(nombre_base, indice):

   # Dado un nombre_base 'YYYY-MM' y un índice (1–60),
   # calcula el mes correspondiente restando (60 - indice).

    año_final, mes_final = map(int, nombre_base.split('-'))
    fecha_final = datetime.date(año_final, mes_final, 1)

    meses_a_restar = 60 - indice
    año_inicio = fecha_final.year
    mes_inicio = fecha_final.month - meses_a_restar

    # Ajuste de año/mes si mes_inicio <= 0
    while mes_inicio <= 0:
        mes_inicio += 12
        año_inicio -= 1

    return f"{año_inicio}-{mes_inicio:02d}"


def filtrar_riesgo_por_zona(zona_gdf, ruta_riesgo):

    # Para cada paso temporal en el NetCDF de riesgo,
    # aplica una máscara rasterizada de la geometría de la zona
    # y extrae estadísticas (min, max, mean, count).

    # Asegurar CRS WGS84
    if zona_gdf.crs != "EPSG:4326":
        zona_gdf = zona_gdf.to_crs("EPSG:4326")

    ds = xr.open_dataset(ruta_riesgo, decode_times=False)
    riesgo = ds['riesgo_hidrico']
    lons = ds['lon'].values
    lats = ds['lat'].values
    time = ds['time'].values

    # Crea transform: asumo pixel size 0.05°
    transform = Affine.translation(lons[0] - 0.25, lats[0] - 0.25) * Affine.scale(0.05, 0.05)

    # Rasterizamos geometría de zona
    mascara = features.rasterize(
        ((geom, 1) for geom in zona_gdf.geometry),
        out_shape=(len(lats), len(lons)),
        transform=transform,
        fill=0,
        dtype='uint8'
    )

    resultados = []
    # Itera cada paso temporal
    for i in range(len(time)):
        capa = riesgo.isel(time=i).values
        valores_zona = capa[mascara == 1]
        valores_validos = valores_zona[~np.isnan(valores_zona)]

        if valores_validos.size > 0:
            resultados.append({
                'time_index': int(i),
                'min': float(np.min(valores_validos)),
                'max': float(np.max(valores_validos)),
                'mean': float(np.mean(valores_validos)),
                'count': int(valores_validos.size)
            })

    ds.close()

    return {
        'nombre_archivo': ruta_riesgo,
        'cantidad_tiempos': len(resultados),
        'resultados': resultados
    }


def obtener_zona_gdf(zona, valor):

    # Lee el shapefile correspondiente a la zona (comuna/provincia/región)
    # y filtra por el nombre exacto (case-insensitive).

    zona = zona.strip().lower()  # Normaliza la zona
    if zona == 'comuna':
        gdf = gpd.read_file("shapefiles/comunas/comunas.shp")
        gdf = gdf[gdf["Comuna"].str.strip().str.lower() == valor.strip().lower()]
    elif zona == 'provincia':
        gdf = gpd.read_file("shapefiles/provincias/Provincias.shp")
        gdf = gdf[gdf["Provincia"].str.strip().str.lower() == valor.strip().lower()]
    elif zona == 'region':
        gdf = gpd.read_file("shapefiles/regiones/Regional.shp")
        gdf = gdf[gdf["Region"].str.strip().str.lower() == valor.strip().lower()]
    else:
        raise ValueError("Zona inválida")

    if gdf.empty:
        raise ValueError(f"No se encontró la {zona} con nombre: {valor}")

    return gdf


def generar_geotiff_riesgo_zona(zona_gdf, ruta_riesgo, indice_tiempo): 

    # Toma la capa de riesgo en un momento dado (time=index),
    # aplica máscara de la zona y escribe un GeoTIFF en un archivo
    # temporal que luego retorna.

    ds = xr.open_dataset(ruta_riesgo, decode_times=False)
    riesgo = ds['riesgo_hidrico'].isel(time=indice_tiempo).values
    lons = ds['lon'].values
    lats = ds['lat'].values
    ds.close()

    # Asegurar orientación correcta
    if lats[0] > lats[-1]:
        lats = lats[::-1]
        riesgo = riesgo[::-1, :]
    if lons[0] > lons[-1]:
        lons = lons[::-1]
        riesgo = riesgo[:, ::-1]

    # Transform geográfico (pixel de 0.05°)
    transform = Affine.translation(lons[0], lats[-1]) * Affine.scale(0.05, -0.05)

    # Rasterización de la zona
    mascara = features.rasterize(
        ((geom, 1) for geom in zona_gdf.geometry),
        out_shape=riesgo.shape,
        transform=transform,
        fill=0,
        dtype='uint8'
    )

    # Aplicar máscara: fuera de zona → nan
    capa_filtrada = np.where(mascara == 1, riesgo, np.nan)

    # Guardar GeoTIFF en archivo temporal
    temp_file = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
    with rasterio.open(
        temp_file.name, 'w',
        driver='GTiff',
        height=capa_filtrada.shape[0],
        width=capa_filtrada.shape[1],
        count=1,
        dtype='float32',
        crs=CRS.from_epsg(4326), 
        transform=transform,
        nodata=np.nan
    ) as dst:
        dst.write(capa_filtrada.astype(np.float32), 1)

    return temp_file.name
