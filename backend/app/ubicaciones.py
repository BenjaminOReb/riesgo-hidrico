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

import geopandas as gpd

def obtener_zona_gdf(zona, valor):
    """
    Lee el shapefile correspondiente a la zona (comuna/provincia/región/pais/norte/centro/sur)
    y devuelve un GeoDataFrame con la(s) geometría(s) filtrada(s).
    """
    z = zona.strip().lower()

    # 1) Casos puntuales: país, zonas
    if z == 'pais':
        # Unimos todas las regiones
        regiones = gpd.read_file("shapefiles/regiones/Regional.shp").to_crs(epsg=4326)
        union_geom = regiones.geometry.unary_union
        return gpd.GeoDataFrame(
            {'geometry': [union_geom]},
            geometry='geometry',
            crs="EPSG:4326"
        )

    # Definimos listas de nombres de región para cada “zona”
    REG_NORTE = [
        "Región de Arica y Parinacota",
        "Región de Tarapacá",
        "Región de Antofagasta",
        "Región de Atacama",
        "Región de Coquimbo"
    ]
    REG_CENTRO = [
        "Región de Valparaíso",
        "Región Metropolitana de Santiago",
        "Región del Libertador Bernardo O'Higgins",
        "Región del Maule",
        "Región de Ñuble",
        "Región del Bío-Bío",
    ]
    REG_SUR = [
        "Región de La Araucanía",
        "Región de Los Ríos",
        "Región de Los Lagos",
        "Región de Aysén del Gral.Ibañez del Campo",
        "Región de Magallanes y Antártica Chilena",
        "Zona sin demarcar"
    ]

    if z in ('norte', 'centro', 'sur'):
        regiones = gpd.read_file("shapefiles/regiones/Regional.shp").to_crs(epsg=4326)
        if z == 'norte':
            sel = regiones[regiones["Region"].isin(REG_NORTE)]
        elif z == 'centro':
            sel = regiones[regiones["Region"].isin(REG_CENTRO)]
        else:  # sur
            sel = regiones[regiones["Region"].isin(REG_SUR)]

        if sel.empty:
            raise ValueError(f"No se encontraron regiones para la zona '{zona}'")

        union_geom = sel.geometry.unary_union
        return gpd.GeoDataFrame(
            {'geometry': [union_geom]},
            geometry='geometry',
            crs="EPSG:4326"
        )

    # 2) Casos por nombre: comuna, provincia, región
    if z == 'comuna':
        shp = "shapefiles/comunas/comunas.shp"
        campo = "Comuna"
    elif z == 'provincia':
        shp = "shapefiles/provincias/Provincias.shp"
        campo = "Provincia"
    elif z == 'region':
        shp = "shapefiles/regiones/Regional.shp"
        campo = "Region"
    else:
        raise ValueError(f"Zona inválida: {zona}")

    gdf = gpd.read_file(shp)
    mask = gdf[campo].str.strip().str.lower() == valor.strip().lower()
    gdf = gdf[mask]

    if gdf.empty:
        raise ValueError(f"No se encontró {zona} con nombre '{valor}'")

    return gdf.to_crs(epsg=4326)

