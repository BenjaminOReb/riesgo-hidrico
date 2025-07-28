# scripts/reparar_shapefiles_inplace.py

import geopandas as gpd
import os
from pathlib import Path

SHAPE_DIR = Path("shapefiles/regiones")
EXTS = ['.shp', '.shx', '.dbf', '.prj', '.cpg']

for shp_path in SHAPE_DIR.glob("*.shp"):
    print(f"Procesando {shp_path.name}…")
    # 1) Leer y sanear
    gdf = gpd.read_file(shp_path)
    gdf["geometry"] = gdf.geometry.buffer(0)           # corrige self‑intersections
    gdf = gdf.to_crs(epsg=4326)                        # reproyecta a lon/lat

    # 2) Eliminar archivos antiguos
    for ext in EXTS:
        f = shp_path.with_suffix(ext)
        if f.exists():
            f.unlink()

    # 3) Escribir de nuevo en EPSG:4326
    gdf.to_file(shp_path, driver="ESRI Shapefile")
    inv = int((~gdf.is_valid).sum())
    bounds = [round(x,3) for x in gdf.total_bounds]
    print(f" → {shp_path.name}: CRS={gdf.crs.to_string()}, invalid={inv}, bounds={bounds}\n")
