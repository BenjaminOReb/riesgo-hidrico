import os
import xarray as xr
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
from rasterio import features
from affine import Affine

# --- Configuración de archivos y variables ---
# Ajusta estas rutas si tus archivos están en otras carpetas
files = [
    ("uploads/riesgo_crisp/riesgo_crisp_2019-05.nc", "riesgo_crisp",    "Riesgo Crisp"),
    ("uploads/riesgo_fuzzy/riesgo_fuzzy_2019-05.nc", "riesgo_fuzzy", "Riesgo Fuzzy"),
    #("uploads/recortado/t2m_2019-05_recortado.nc",   "t2m",          "Temperatura"),
    #("uploads/fuzzy/fuzzy_t2m_2019-05.nc",           "t2m_baja",    "Temperatura Fuzzy (baja)"),
    #("uploads/fuzzy/fuzzy_t2m_2019-05.nc",           "t2m_media",    "Temperatura Fuzzy (moderada)"),
    #("uploads/fuzzy/fuzzy_t2m_2019-05.nc",           "t2m_alta",    "Temperatura Fuzzy (alta)"),
    #("uploads/recortado/pr_2019-05_recortado.nc",    "pr",           "Precipitación"),
    #("uploads/fuzzy/fuzzy_pr_2019-05.nc",            "pr_baja",     "Precipitación Fuzzy (baja)"),
    #("uploads/fuzzy/fuzzy_pr_2019-05.nc",            "pr_media",     "Precipitación Fuzzy (moderada)"),
    #("uploads/fuzzy/fuzzy_pr_2019-05.nc",            "pr_alta",     "Precipitación Fuzzy (alta)")
]

time_index = 59 # índice temporal a plotear (0 a 59 en tu caso)

regiones = (
    gpd.read_file("shapefiles/regiones/Regional.shp")
       .to_crs(epsg=4326)
)

region_names = [
    #Norte
    #"Región de Arica y Parinacota",
    #"Región de Tarapacá",
    #"Región de Antofagasta",
    #"Región de Atacama",
    #"Región de Coquimbo",
    #Centro
    "Región de Valparaíso",
    "Región Metropolitana de Santiago",
    "Región del Libertador Bernardo O'Higgins",
    "Región del Maule",
    "Región de Ñuble",
    "Región del Bío-Bío",
    #Sur
    #"Región de La Araucanía",
    #"Región de Los Ríos",
    #"Región de Los Lagos",
    #"Región de Aysén del Gral.Ibañez del Campo",
    #"Región de Magallanes y Antártica Chilena",
    #"Zona sin demarcar",
]

seleccion = regiones[regiones["Region"].isin(region_names)]
if seleccion.empty:
    raise RuntimeError("Ninguna región coincide con tu lista.")

# --- 2) Unir todas las geometrías en una sola ---
union_geom = seleccion.geometry.unary_union
minx, miny, maxx, maxy = union_geom.bounds

# 3) Leer lats/lons del primer NetCDF para el grid
ds0 = xr.open_dataset(files[0][0], decode_times=False)
lons = ds0["lon"].values
lats = ds0["lat"].values
ds0.close()
dx = float(lons[1] - lons[0])
dy = float(lats[1] - lats[0])
transform = Affine.translation(lons.min() - dx/2, lats.max() + dy/2) * Affine.scale(dx, -dy)


# --- 4) Rasterizar la geometría unida (1 dentro, 0 fuera) ---
mask2d = features.rasterize(
    [(union_geom, 1)],
    out_shape=(len(lats), len(lons)),
    transform=transform,
    fill=0,
    dtype="uint8"
)

# 5) Dibujar una columna por archivo
fig, axes = plt.subplots(nrows=1, ncols=len(files), figsize=(6*len(files), 8))
axes = np.atleast_1d(axes).flatten()

for ax, (ruta, var, titulo) in zip(axes, files):
    ds = xr.open_dataset(ruta, decode_times=False)
    da = ds[var].isel(time=time_index)
    data = da.values.copy()
    ds.close()

    # invertir latitudes si es necesario
    if lats[0] < lats[-1]:
        data = data[::-1, :]
        lat_plot = lats[::-1]
    else:
        lat_plot = lats

    # 6) Aplicar máscara
    data_masked = np.where(mask2d == 1, data, np.nan)

    # 7) pcolormesh
    Lon, Lat = np.meshgrid(lons, lat_plot)
    pcm = ax.pcolormesh(Lon, Lat, data_masked, cmap="plasma", shading="auto")

    ax.set_title(titulo, fontsize=14)
    ax.set_xlabel("Longitud")
    ax.set_ylabel("Latitud")

    # ---> aquí recorto los ejes a la zona unida:
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    # opcional: sólo 5 ticks en Y
    ax.set_yticks(np.linspace(miny, maxy, 5))

    plt.colorbar(pcm, ax=ax, orientation="vertical", label=var)

fig.suptitle(
    f"Mapa Zona Centro",
    fontsize=16
)
plt.tight_layout(rect=[0, 0, 1, 0.94])
plt.show()