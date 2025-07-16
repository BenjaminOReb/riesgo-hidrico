import rasterio

with rasterio.open("uploads/tiff/tmp8ajvkm55.tif") as src:
    print(src.crs)
    print(src.transform)
