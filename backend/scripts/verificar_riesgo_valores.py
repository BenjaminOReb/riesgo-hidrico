import xarray as xr
import numpy as np

# Abre sin decodificar tiempo
#ds = xr.open_dataset('uploads/riesgo/riesgo_2019-05.nc', decode_times=False)
#riesgo = ds['riesgo_hidrico']

#print("✅ Variable cargada correctamente.")
#print("📉 Valor mínimo:", float(riesgo.min().values))
#print("📈 Valor máximo:", float(riesgo.max().values))
#print("📊 Promedio:", float(riesgo.mean().values))
#print(riesgo.min().values, riesgo.max().values, riesgo.mean().values)

archivo = 'uploads/riesgo/riesgo_2019-05.nc'

try:
    ds = xr.open_dataset(archivo, decode_times=False)
    print(f"📄 Archivo: {archivo}")
    print("🔍 Variables:", list(ds.data_vars))
    print("📏 Dimensiones:", dict(ds.dims))

    if 'riesgo_hidrico' in ds.data_vars:
        riesgo = ds['riesgo_hidrico']
        print(f"🧪 Riesgo hídrico - shape: {riesgo.shape}")
        print(f"🕒 Tiempo: {riesgo.sizes['time']} pasos")

        # Mostrar estadísticas del último paso de tiempo
        valores = riesgo.isel(time=-1).values
        print(f"📉 Mínimo: {np.nanmin(valores):.3f}")
        print(f"📈 Máximo: {np.nanmax(valores):.3f}")
        print(f"📊 Promedio: {np.nanmean(valores):.3f}")
    else:
        print("⚠️ No se encontró la variable 'riesgo_hidrico'.")

    ds.close()
except Exception as e:
    print(f"❌ Error: {e}")