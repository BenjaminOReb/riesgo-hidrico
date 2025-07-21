import os
import xarray as xr
import numpy as np

archivos = [
    "uploads/raw/CR2MET_pr_v2.0_mon_1979_2019_005deg.nc",
    "uploads/raw/CR2MET_t2m_v2.0_mon_1979_2019_005deg.nc",
    "uploads/recortado/pr_2019-05_recortado.nc",
    "uploads/recortado/t2m_2019-05_recortado.nc",
    "uploads/riesgo_raw/riesgo_raw_2019-05.nc",
    "uploads/fuzzy/fuzzy_pr_2019-05.nc",
    "uploads/fuzzy/fuzzy_t2m_2019-05.nc",
    "uploads/riesgo_fuzzy/riesgo_fuzzy_2019-05.nc"
]

for ruta in archivos:
    print(f"\n📄 Revisando: {ruta}")
    try:
        if not os.path.exists(ruta):
            raise FileNotFoundError(f"No se encontró el archivo: {ruta}")

        ds = xr.open_dataset(ruta, decode_times=False)  # usa cftime si es necesario

        print("🔍 Variables disponibles:", list(ds.variables))
        print("📏 Dimensiones:", dict(ds.dims))

        if "time" in ds:
            fechas = ds['time'].values
            print(f"🕒 Rango de fechas: {fechas[0]} → {fechas[-1]} ({len(fechas)} pasos de tiempo)")

        # Análisis de variables fuzzy
        for var in ds.data_vars:
            if any(suffix in var for suffix in ["_baja", "_media", "_alta", "riesgo_hidrico_fuzzy"]):
                datos = ds[var].values
                datos = np.where(np.isnan(datos), np.nan, datos)
                print(f"📊 {var}: min={np.nanmin(datos):.3f}, max={np.nanmax(datos):.3f}, mean={np.nanmean(datos):.3f}")

        ds.close()

    except Exception as e:
        print(f"❌ Error con {ruta}: {e}")
