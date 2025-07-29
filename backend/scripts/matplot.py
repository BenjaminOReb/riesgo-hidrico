import os
import xarray as xr
import matplotlib.pyplot as plt
import numpy as np

# --- Configuración de archivos y variables ---
# Ajusta estas rutas si tus archivos están en otras carpetas
files = [
    ("uploads/riesgo_raw/riesgo_raw_2019-05.nc", "riesgo_raw",    "Riesgo Crudo"),
    ("uploads/riesgo_fuzzy/riesgo_fuzzy_2019-05.nc", "riesgo_fuzzy", "Riesgo Fuzzy"),
    ("uploads/recortado/t2m_2019-05_recortado.nc",   "t2m",          "Temperatura Cruda (t2m)"),
    ("uploads/fuzzy/fuzzy_t2m_2019-05.nc",           "t2m_alta",    "Temperatura Fuzzy (alta)"),
    ("uploads/recortado/pr_2019-05_recortado.nc",    "pr",           "Precipitación Cruda (pr)"),
    ("uploads/fuzzy/fuzzy_pr_2019-05.nc",            "pr_baja",     "Precipitación Fuzzy (baja)")
]

time_index = 55 # índice temporal a plotear (0 a 59 en tu caso)

# --- Crear figura con 2 filas x 3 columnas ---
fig, axes = plt.subplots(nrows=2, ncols=3, figsize=(18, 10), 
                         subplot_kw={"projection": None})
axes = axes.flatten()

for ax, (ruta, var, titulo) in zip(axes, files):
    # 1) Abrir dataset
    ds = xr.open_dataset(ruta, decode_times=False)
    
    if var not in ds.data_vars:
        raise KeyError(f"Variable '{var}' no encontrada en {ruta}")
    
    # 2) Extraer capa t x lat x lon
    da = ds[var].isel(time=time_index)
    data = da.values
    lons = ds["lon"].values
    lats = ds["lat"].values
    ds.close()
    
    # 3) Asegurar orientación: latitudes descendentes para pcolormesh
    if lats[0] < lats[-1]:
        lats = lats[::-1]
        data = data[::-1, :]
    
    # 4) Dibujar con pcolormesh
    #    Creamos la malla de coordenadas
    Lon, Lat = np.meshgrid(lons, lats)
    pcm = ax.pcolormesh(Lon, Lat, data,
                        cmap="viridis", shading="auto")
    
    ax.set_title(titulo, fontsize=14)
    ax.set_xlabel("Longitud")
    ax.set_ylabel("Latitud")
    plt.colorbar(pcm, ax=ax, orientation="vertical", label=var)
    
# Ajustes finales
plt.tight_layout()
plt.show()
