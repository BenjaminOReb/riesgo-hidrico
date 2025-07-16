import geopandas as gpd

def validar_shapefile(ruta, tipo):
    print(f"\n🔍 Validando shapefile de {tipo} ({ruta})")

    try:
        gdf = gpd.read_file(ruta)
        print("✅ Shapefile cargado correctamente.")
        print(f"🗺️ Sistema de coordenadas (CRS): {gdf.crs}")
        print(f"📌 Columnas disponibles: {list(gdf.columns)}")

        campo = tipo.capitalize()
        if campo not in gdf.columns:
            print(f"❌ La columna '{campo}' no existe en el shapefile.")
        else:
            print(f"📍 Ejemplos de {tipo}s:")
            print(gdf[campo].dropna().unique()[:10])
    except Exception as e:
        print(f"❌ Error al leer shapefile de {tipo}: {e}")

# Validar comunas
validar_shapefile("shapefiles/comunas/comunas.shp", "comuna")

# Validar provincias
validar_shapefile("shapefiles/provincias/Provincias.shp", "provincia")

# Validar regiones
validar_shapefile("shapefiles/regiones/Regional.shp", "region")
