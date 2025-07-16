import geopandas as gpd

# Ruta al shapefile de comunas (ajusta si tienes otro nombre)
shapefile_path = "shapefiles/comunas/comunas.shp"

try:
    gdf = gpd.read_file(shapefile_path)

    print("✅ Shapefile cargado correctamente.")
    print(f"🗺️ Número de comunas: {len(gdf)}")
    print("📌 Columnas disponibles:")
    print(gdf.columns)

    print("\n📍 Ejemplo de nombres:")
    print(gdf[['REGION', 'PROVINCIA', 'COMUNA']].head())

except Exception as e:
    print("\n📍 Ejemplo de nombres:")
for col in gdf.columns:
    print(f" - {col}")

# Verificar presencia de columnas clave
for col in ['Region', 'Provincia', 'Comuna']:
    if col not in gdf.columns:
        raise ValueError(f"Columna '{col}' no encontrada")

print(gdf[['Region', 'Provincia', 'Comuna']].head())
