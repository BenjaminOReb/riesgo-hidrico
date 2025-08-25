import os
import xarray as xr
import matplotlib.pyplot as plt
import numpy as np

# --- Configuración de archivos y variables ---
# Ajusta estas rutas si tus archivos están en otras carpetas
files = [
    #("uploads/recortado/t2m_2019-12_recortado.nc",   "t2m",          "Temperatura"),
    #("uploads/fuzzy/fuzzy_t2m_2019-12.nc",           "t2m_baja",    "Temperatura Fuzzy (baja)"),
    #("uploads/fuzzy/fuzzy_t2m_2019-12.nc",           "t2m_media",    "Temperatura Fuzzy (moderada)"),
    #("uploads/fuzzy/fuzzy_t2m_2019-12.nc",           "t2m_alta",    "Temperatura Fuzzy (alta)"),

    #("uploads/recortado/pr_2019-12_recortado.nc",    "pr",           "Precipitación"),
    #("uploads/fuzzy/fuzzy_pr_2019-12.nc",            "pr_baja",     "Precipitación Fuzzy (baja)"),
    #("uploads/fuzzy/fuzzy_pr_2019-12.nc",            "pr_media",     "Precipitación Fuzzy (moderada)"),
    #("uploads/fuzzy/fuzzy_pr_2019-12.nc",            "pr_alta",     "Precipitación Fuzzy (alta)"),

    #("uploads/riesgo_fuzzy/riesgo_fuzzy_2019-12.nc", "riesgo_alto_A", "Tem Alta + Pr Baja"),
    #("uploads/riesgo_fuzzy/riesgo_fuzzy_2019-12.nc", "riesgo_alto_B", "Tem Media + Pr Baja"),

    #("uploads/riesgo_fuzzy/riesgo_fuzzy_2019-12.nc", "riesgo_medio_A", "Tem Baja + Pr Baja"),
    #("uploads/riesgo_fuzzy/riesgo_fuzzy_2019-12.nc", "riesgo_medio_B", "Tem Alta + Pr Media"),
    #("uploads/riesgo_fuzzy/riesgo_fuzzy_2019-12.nc", "riesgo_medio_C", "Tem Media + Pr Media"),
    #("uploads/riesgo_fuzzy/riesgo_fuzzy_2019-12.nc", "riesgo_medio_D", "Tem Baja + Pr Media"),
    #("uploads/riesgo_fuzzy/riesgo_fuzzy_2019-12.nc", "riesgo_medio_E", "Tem Alta + Pr Alta"),

    #("uploads/riesgo_fuzzy/riesgo_fuzzy_2019-12.nc", "riesgo_bajo_A", "Tem Media + Pr Alta"),
    #("uploads/riesgo_fuzzy/riesgo_fuzzy_2019-12.nc", "riesgo_bajo_B", "Tem Baja + Pr Alta"),

    ("uploads/riesgo_crisp/riesgo_crisp_2019-12.nc", "riesgo_crisp",    "Riesgo Crisp"),

    #("uploads/riesgo_fuzzy/riesgo_fuzzy_2019-12.nc", "riesgo_alto", "Riesgo Alto A+B"),
    #("uploads/riesgo_fuzzy/riesgo_fuzzy_2019-12.nc", "riesgo_medio", "Riesgo Medio A+B+C+D+E"),
    #("uploads/riesgo_fuzzy/riesgo_fuzzy_2019-12.nc", "riesgo_bajo", "Riesgo Bajo A+B"),
    ("uploads/riesgo_fuzzy/riesgo_fuzzy_2019-12.nc", "riesgo_fuzzy", "Riesgo Fuzzy (Combinada alto, medio y bajo)"),

]

time_index = 59 # índice temporal a plotear (0 a 59 en tu caso)

# --- Crear figura con 2 filas x 3 columnas ---
fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(18, 10), 
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
                        cmap="plasma", shading="auto")
    
    ax.set_title(titulo, fontsize=14)
    ax.set_xlabel("Longitud")
    ax.set_ylabel("Latitud")
    plt.colorbar(pcm, ax=ax, orientation="vertical", label=var)
    
# Ajustes finales
plt.tight_layout()
plt.show()