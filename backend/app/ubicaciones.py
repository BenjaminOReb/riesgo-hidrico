import geopandas as gpd

def cargar_jerarquia_ubicaciones(ruta_shapefile='shapefiles/comunas/comunas.shp'):

    # Lee un shapefile de comunas (que incluye columnas Region, Provincia y Comuna)
    # y construye un diccionario anidado con la siguiente estructura:
    #   {
    #     "Región A": {
    #       "Provincia X": ["Comuna 1", "Comuna 2", ...],
    #       "Provincia Y": [...],
    #       ...
    #     },
    #     "Región B": { ... },
    #     ...
    #   }

    # Cargar todo el shapefile en un GeoDataFrame
    gdf = gpd.read_file(ruta_shapefile)

    # Asegurar quitar espacios en blanco en los nombres
    gdf['Region'] = gdf['Region'].str.strip()
    gdf['Provincia'] = gdf['Provincia'].str.strip()
    gdf['Comuna'] = gdf['Comuna'].str.strip()

    jerarquia = {} # Aquí construiremos el diccionario final

    # Itera fila por fila del GeoDataFrame
    for _, row in gdf.iterrows():
        region = row['Region']
        provincia = row['Provincia']
        comuna = row['Comuna']

        # Si la región aún no está en el diccionario, la inicializa
        if region not in jerarquia:
            jerarquia[region] = {}

        # Si la provincia aún no está bajo esa región, la inicializa
        if provincia not in jerarquia[region]:
            jerarquia[region][provincia] = []

        # Añade la comuna a la lista de esa provincia (evitando duplicados)
        if comuna not in jerarquia[region][provincia]:
            jerarquia[region][provincia].append(comuna)

    return jerarquia

def obtener_zona_gdf(zona, valor):
   
    # Lee el shapefile de comuna/provincia/región y filtra por valor (case-insensitive).
    
    z = zona.strip().lower()
    if z == 'comuna':
        gdf = gpd.read_file("shapefiles/comunas/comunas.shp")
        gdf = gdf[gdf["Comuna"].str.strip().str.lower() == valor.strip().lower()]
    elif z == 'provincia':
        gdf = gpd.read_file("shapefiles/provincias/Provincias.shp")
        gdf = gdf[gdf["Provincia"].str.strip().str.lower() == valor.strip().lower()]
    elif z == 'region':
        gdf = gpd.read_file("shapefiles/regiones/Regional.shp")
        gdf = gdf[gdf["Region"].str.strip().str.lower() == valor.strip().lower()]
    else:
        raise ValueError(f"Zona inválida: {zona}")
    if gdf.empty:
        raise ValueError(f"No se encontró {zona} con nombre '{valor}'")
    return gdf
