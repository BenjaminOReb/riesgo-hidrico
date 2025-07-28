import xarray as xr

ds = xr.open_dataset("uploads/fuzzy/fuzzy_pr_2019-05.nc", decode_times=False)
print("lat[0], lat[-1] →", ds.lat.values[0], ds.lat.values[-1])
print("lon[0], lon[-1] →", ds.lon.values[0], ds.lon.values[-1])
ds.close()