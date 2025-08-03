import os
from pathlib import Path

import xarray as xr
import numpy as np

archivos = [
    "uploads/crisp/CR2MET_pr_v2.0_mon_1979_2019_005deg.nc",
    "uploads/crisp/CR2MET_t2m_v2.0_mon_1979_2019_005deg.nc",
    "uploads/recortado/pr_2019-05_recortado.nc",
    "uploads/recortado/t2m_2019-05_recortado.nc",
    "uploads/riesgo_crisp/riesgo_crisp_2019-05.nc",
    "uploads/fuzzy/fuzzy_pr_2019-05.nc",
    "uploads/fuzzy/fuzzy_t2m_2019-05.nc",
    "uploads/riesgo_fuzzy/riesgo_fuzzy_2019-05.nc"
]

# Sufijos que identifican las variables de interés
sufijos = ("pr", "t2m", "_baja", "_media", "_alta", "riesgo_fuzzy", "riesgo_crisp")

for ruta_str in archivos:
    ruta = Path(ruta_str)
    print(f"\n📄 Revisando: {ruta}")
    try:
        if not ruta.exists():
            raise FileNotFoundError(f"No se encontró el archivo: {ruta}")

        # Usamos context manager para asegurar el cierre del dataset
        with xr.open_dataset(ruta, decode_times=False) as ds:
            vars_all = list(ds.data_vars)
            print("🔍 Variables disponibles:", vars_all)

            dims = dict(ds.dims)
            print("📏 Dimensiones:", dims)

            if "time" in ds:
                t0, tN = ds["time"].values[[0, -1]]
                print(f"🕒 Rango de fechas: {t0} → {tN} ({dims['time']} pasos de tiempo)")

            # Solo analizamos las variables que contengan alguno de los sufijos
            for var in vars_all:
                if any(var.endswith(s) or s in var for s in sufijos):
                    datos = ds[var].values.astype(float)
                    minv = np.nanmin(datos)
                    maxv = np.nanmax(datos)
                    meanv = np.nanmean(datos)
                    print(f"📊 {var:15s}: min={minv:.3f}, max={maxv:.3f}, mean={meanv:.3f}")

    except Exception as e:
        print(f"❌ Error con {ruta}: {e}")
