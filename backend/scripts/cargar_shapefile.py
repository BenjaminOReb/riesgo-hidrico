import os
import geopandas as gpd
from shapely.validation import explain_validity

SHAPE_DIR = "shapefiles/regiones"  # ajusta si tu carpeta es distinta

for fname in sorted(os.listdir(SHAPE_DIR)):
    if not fname.lower().endswith(".shp"):
        continue
    path = os.path.join(SHAPE_DIR, fname)
    gdf = gpd.read_file(path)

    print(f"=== {fname} ===")
    print(f"CRS: {gdf.crs}")
    print(f"Total features: {len(gdf)}")
    print("Fields:", list(gdf.columns))
    print(" Null counts per field:", gdf.isnull().sum().to_dict())

    invalid = gdf[~gdf.is_valid]
    print(f"Invalid geometries: {len(invalid)}")
    if len(invalid) > 0:
        # contamos razones de invalidez
        reasons = invalid.geometry.apply(explain_validity).value_counts().to_dict()
        print(" Invalid reasons:", reasons)

    bounds = gdf.total_bounds  # [xmin, ymin, xmax, ymax]
    print(f"Total bounds: [{bounds[0]:.3f}, {bounds[1]:.3f}, {bounds[2]:.3f}, {bounds[3]:.3f}]")
    print()
