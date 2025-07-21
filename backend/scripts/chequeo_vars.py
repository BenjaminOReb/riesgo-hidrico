import xarray as xr
import numpy as np
import glob

def resumen_variables(nc_path):
    print(f"\n📄 Archivo: {nc_path}")
    ds = xr.open_dataset(nc_path, decode_times=False)
    for var in ds.data_vars:
        arr = ds[var].values.astype(float)
        print(f"  • {var:12s} → min={np.nanmin(arr):.3f}, max={np.nanmax(arr):.3f}, mean={np.nanmean(arr):.3f}")
    ds.close()

# Ajusta la ruta a donde tengas los .nc:
for ruta in glob.glob("uploads/**/*.nc", recursive=True):
    resumen_variables(ruta)
