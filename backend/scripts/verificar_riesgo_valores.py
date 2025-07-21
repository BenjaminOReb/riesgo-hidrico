import xarray as xr
import numpy as np

# Abre sin decodificar tiempo
#ds = xr.open_dataset('uploads/riesgo_fuzzy/riesgo_2019-05.nc', decode_times=False)
#riesgo_fuzzy = ds['riesgo_hidrico_fuzzy']

#print("✅ Variable cargada correctamente.")
#print("📉 Valor mínimo:", float(riesgo_fuzzy.min().values))
#print("📈 Valor máximo:", float(riesgo_fuzzy.max().values))
#print("📊 Promedio:", float(riesgo_fuzzy.mean().values))
#print(riesgo_fuzzy.min().values, riesgo_fuzzy.max().values, riesgo_fuzzy.mean().values)

archivo = 'uploads/riesgo_fuzzy/riesgo_2019-05.nc'

try:
    ds = xr.open_dataset(archivo, decode_times=False)
    print(f"📄 Archivo: {archivo}")
    print("🔍 Variables:", list(ds.data_vars))
    print("📏 Dimensiones:", dict(ds.dims))

    if 'riesgo_hidrico_fuzzy' in ds.data_vars:
        riesgo_fuzzy = ds['riesgo_hidrico_fuzzy']
        print(f"🧪 riesgo_fuzzy hídrico - shape: {riesgo_fuzzy.shape}")
        print(f"🕒 Tiempo: {riesgo_fuzzy.sizes['time']} pasos")

        # Mostrar estadísticas del último paso de tiempo
        valores = riesgo_fuzzy.isel(time=-1).values
        print(f"📉 Mínimo: {np.nanmin(valores):.3f}")
        print(f"📈 Máximo: {np.nanmax(valores):.3f}")
        print(f"📊 Promedio: {np.nanmean(valores):.3f}")
    else:
        print("⚠️ No se encontró la variable 'riesgo_hidrico_fuzzy'.")

    ds.close()
except Exception as e:
    print(f"❌ Error: {e}")
