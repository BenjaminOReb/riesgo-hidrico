from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename

import os
import json
import xarray as xr
import traceback
import datetime
import tempfile
import uuid
import geopandas as gpd
from app.database import get_connection
from app.ubicaciones import cargar_jerarquia_ubicaciones
from app.procesar import (
    recortar_ultimos_5_anos,
    generar_capas_fuzzy,
    calcular_indice_riesgo,
    filtrar_riesgo_por_zona,
    obtener_zona_gdf,
    calcular_fecha_desde_indice,
    generar_geotiff_riesgo_zona
)

#Blueprint para organizar las rutas
routes = Blueprint('routes', __name__)

# Se define la carpeta donde se suben los NetCDF originales
UPLOAD_FOLDER = './uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@routes.route('/upload', methods=['POST'])
def upload_file():

    # Endpoint para subir dos archivos NetCDF (pr y t2m), generar sus capas fuzzy,
    # calcular el índice de riesgo hídrico y almacenar tanto los archivos resultantes
    # como sus metadatos en la base de datos, evitando duplicados y regenerando
    # automáticamente el archivo de riesgo si falta en disco.

    # 1) Valida que venga un archivo en el request
    if 'file' not in request.files:
        return jsonify({'error': 'Archivo no encontrado'}), 400

    file = request.files['file']
    filename = secure_filename(file.filename)

    # Carpeta para archivos originales raw/
    raw_dir = os.path.join(UPLOAD_FOLDER, 'raw')
    os.makedirs(raw_dir, exist_ok=True)
    raw_path = os.path.join(raw_dir, filename)
    file.save(raw_path)     # Guardar el .nc original

    try:
        # 2) Recorta los últimos 60 meses
        recortado_path = recortar_ultimos_5_anos(raw_path)

        # 3) Genera las capas fuzzy (baja, media, alta)
        resultado_fuzzy = generar_capas_fuzzy(recortado_path)
        ruta_fuzzy  = resultado_fuzzy['archivo_salida']
        tipo        = resultado_fuzzy['tipo_variable']   # 'pr' o 't2m'
        nombre_base = resultado_fuzzy['nombre_base']     # p.ej. '2019-05'

        # Fechas inicial y final para el archivo fuzzy
        fecha_ini_fuzzy = calcular_fecha_desde_indice(nombre_base, 1)
        fecha_fin_fuzzy = calcular_fecha_desde_indice(nombre_base, 60)

        conn = get_connection()
        cur  = conn.cursor()

        # 4) Inserta registro fuzzy si no existe
        cur.execute(
            "SELECT 1 FROM archivos WHERE nombre=%s OR ruta=%s",
            (os.path.basename(ruta_fuzzy), ruta_fuzzy)
        )
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO archivos (
                  nombre, ruta, variables, tipo_archivo,
                  nombre_base, fecha_subida,
                  fecha_inicial_datos, fecha_final_datos,
                  es_riesgo_final
                ) VALUES (%s,%s,%s,%s,%s,NOW(),%s,%s,%s)
            """, (
                os.path.basename(ruta_fuzzy),
                ruta_fuzzy,
                ','.join([f"{tipo}_baja", f"{tipo}_media", f"{tipo}_alta"]),
                tipo,
                nombre_base,
                fecha_ini_fuzzy,
                fecha_fin_fuzzy,
                False       # no es archivo de riesgo final
            ))
            conn.commit()

        # 5) Comprueba si existe el otro fuzzy complementario (pr vs t2m)
        fuzzy_dir   = os.path.dirname(ruta_fuzzy)
        otro_var    = 't2m' if tipo=='pr' else 'pr'
        nombre_otro = f"fuzzy_{otro_var}_{nombre_base}.nc"
        comp_path   = os.path.join(fuzzy_dir, nombre_otro)

        if os.path.exists(comp_path):
            # Determinar rutas completas para pr y t2m
            pr_path  = ruta_fuzzy   if tipo=='pr'  else comp_path
            t2m_path = ruta_fuzzy   if tipo=='t2m' else comp_path

            # 6) ¿Ya hay registro de archivo de riesgo en BD?
            cur.execute("""
                SELECT ruta FROM archivos
                WHERE tipo_archivo='riesgo' AND nombre_base=%s
            """, (nombre_base,))
            fila = cur.fetchone()

            if fila:
                riesgo_path = fila[0]
                # 7) Si el fichero no existe en disco, vuelve a generarse y actualiza BD
                if not os.path.exists(riesgo_path):
                    resultado_riesgo = calcular_indice_riesgo(pr_path, t2m_path)
                    riesgo_path      = resultado_riesgo['archivo']
                    # Actualizar la ruta en BD
                    cur.execute("""
                        UPDATE archivos
                        SET ruta=%s
                        WHERE nombre_base=%s AND tipo_archivo='riesgo'
                    """, (riesgo_path, nombre_base))
                    conn.commit()
            else:
                # 8) No había registro: calcular y guardar nuevo archivo de riesgo
                resultado_riesgo = calcular_indice_riesgo(pr_path, t2m_path)
                riesgo_path      = resultado_riesgo['archivo']
                # Obtener fechas para BD
                fecha_ini_r = calcular_fecha_desde_indice(nombre_base, 1)
                fecha_fin_r = calcular_fecha_desde_indice(nombre_base, 60)
                # Insertar el registro de riesgo
                cur.execute("""
                    INSERT INTO archivos (
                      nombre, ruta, variables, tipo_archivo,
                      nombre_base, fecha_subida,
                      fecha_inicial_datos, fecha_final_datos,
                      es_riesgo_final
                    ) VALUES (%s,%s,%s,%s,%s,NOW(),%s,%s,%s)
                """, (
                    os.path.basename(riesgo_path),
                    riesgo_path,
                    'riesgo_hidrico',
                    'riesgo',
                    nombre_base,
                    fecha_ini_r,
                    fecha_fin_r,
                    True
                ))
                conn.commit()

        cur.close()
        conn.close()

        # 9) Responder con detalles de los archivos procesados
        return jsonify({
            'mensaje'      : 'Archivos procesados correctamente',
            'nombre_base'  : nombre_base,
            'fuzzy'        : os.path.basename(ruta_fuzzy),
            # si existe riesgo_path, lo devuelve; si no, será None
            'riesgo'       : locals().get('riesgo_path', None)
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@routes.route('/api/ubicaciones', methods=['GET'])
def obtener_ubicaciones():

    # Devuelve la jerarquía de regiones→provincias→comunas como JSON.

    try:
        jerarquia = cargar_jerarquia_ubicaciones()
        return jsonify(jerarquia)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@routes.route('/api/lista-zonas', methods=['GET'])
def lista_zonas():

    # Dada una zona ('region', 'provincia' o 'comuna'), lee el shapefile correspondiente
    # y retorna la lista ordenada de nombres disponibles.

    zona = request.args.get('zona')
    if not zona:
        return jsonify({'error': 'Falta el parámetro zona'}), 400

    try:
        # Selecciona el shapefile según tipo
        if zona == 'region':
            gdf = gpd.read_file("shapefiles/regiones/Regional.shp")
            nombres = sorted(gdf["Region"].dropna().unique())
        elif zona == 'provincia':
            gdf = gpd.read_file("shapefiles/provincias/Provincias.shp")
            nombres = sorted(gdf["Provincia"].dropna().unique())
        elif zona == 'comuna':
            gdf = gpd.read_file("shapefiles/comunas/comunas.shp")
            nombres = sorted(gdf["Comuna"].dropna().unique())
        else:
            return jsonify({'error': 'Zona inválida'}), 400

        return jsonify({'zona': zona, 'nombres': nombres})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@routes.route('/api/riesgo-zona', methods=['GET'])
def riesgo_por_zona():

    # Filtra el índice de riesgo por la geometría de la zona indicada
    # y devuelve un JSON con valores puntuales.

    zona = request.args.get('zona')
    valor = request.args.get('valor')
    fecha = request.args.get('fecha')

    if not zona or not valor or not fecha:
        return jsonify({'error': 'Faltan parámetros'}), 400

    ruta_riesgo = f"uploads/riesgo/riesgo_{fecha}.nc"
    if not os.path.exists(ruta_riesgo):
        return jsonify({'error': 'Archivo no encontrado'}), 404

    try:
        zona_gdf = obtener_zona_gdf(zona, valor)
        resultado = filtrar_riesgo_por_zona(zona_gdf, ruta_riesgo)
        return jsonify(resultado)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@routes.route('/api/riesgo-geotiff', methods=['GET'])
def servir_riesgo_geotiff():

    #Devuelve un GeoTIFF recortado al área de la zona y al mes solicitado.
    #Busca en BD el NetCDF que cubra la fecha, calcula el índice de tiempo
    #y genera el TIFF.

    zona = request.args.get('zona')
    valor = request.args.get('valor')
    fecha = request.args.get('fecha')  # esperaremos un string "YYYY-MM"

    if not zona or not valor or not fecha:
        return jsonify({'error': 'Faltan parámetros'}), 400

    try:
        # Normalizar la fecha a "YYYY-MM"
        fecha_texto = fecha.strip()

        # Busca en la BD el archivo de riesgo que cubra ese mes
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT ruta, nombre_base, fecha_inicial_datos
            FROM archivos
            WHERE tipo_archivo   = 'riesgo'
              AND es_riesgo_final = TRUE
              AND fecha_inicial_datos <= %s
              AND fecha_final_datos   >= %s
            ORDER BY fecha_final_datos DESC
            LIMIT 1
        """, (fecha_texto, fecha_texto))
        resultado = cur.fetchone()
        cur.close()
        conn.close()

        if not resultado:
            return jsonify({
                'error': f'No se encontró un archivo de riesgo que abarque {fecha_texto}'
            }), 404

        ruta_riesgo, nombre_base, fecha_inicial_str = resultado

        # Calcula índice de tiempo (meses desde fecha_inicial)
        fecha_pedida   = datetime.datetime.strptime(fecha_texto, "%Y-%m").date().replace(day=1)
        fecha_inicial  = datetime.datetime.strptime(fecha_inicial_str[:7], "%Y-%m").date().replace(day=1)
        meses_diferencia = (
            (fecha_pedida.year  - fecha_inicial.year) * 12 +
            (fecha_pedida.month - fecha_inicial.month)
        )
        if meses_diferencia < 0 or meses_diferencia >= 60:
            return jsonify({'error': 'Índice de tiempo fuera de rango (0–59)'}), 400

        # Genera y devolve el GeoTIFF
        zona_gdf = obtener_zona_gdf(zona, valor).to_crs(epsg=4326)
        ruta_tif = generar_geotiff_riesgo_zona(zona_gdf, ruta_riesgo, meses_diferencia)

        return send_file(ruta_tif, mimetype='image/tiff')

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    
@routes.route('/descargas/geotiff/<nombre>')
def servir_geotiff(nombre):

    # Permite descargar directamente un GeoTIFF ya generado.

    ruta = f"uploads/riesgo/geotiff/{nombre}"
    if os.path.exists(ruta):
        return send_file(ruta, mimetype='image/tiff', as_attachment=False)
    return jsonify({'error': 'Archivo no encontrado'}), 404

@routes.route('/api/geojson', methods=['GET'])
def geojson_zona():

    # Devuelve el GeoJSON de la zona indicada (comuna, provincia o región),
    # listo para dibujar en el mapa.

    comuna = request.args.get('comuna')
    provincia = request.args.get('provincia')
    region = request.args.get('region')

    try:
        if comuna:
            gdf = obtener_zona_gdf('comuna', comuna)
        elif provincia:
            gdf = obtener_zona_gdf('provincia', provincia)
        elif region:
            gdf = obtener_zona_gdf('region', region)
        else:
            return jsonify({'error': 'Falta un parámetro: comuna, provincia o region'}), 400

        # Convierte a GeoJSON y luego a dict para jsonify
        geojson_str = gdf.to_crs(epsg=4326).to_json()
        geojson_obj = json.loads(geojson_str) 
        return jsonify(geojson_obj)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@routes.route('/api/fechas-disponibles', methods=['GET'])
def fechas_disponibles():

    # Devuelve la lista de meses (YYYY-MM) para los cuales hay archivos
    # de riesgo disponibles en BD.

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT fecha_inicial_datos, fecha_final_datos
            FROM archivos
            WHERE tipo_archivo = 'riesgo' AND es_riesgo_final = TRUE
        """)
        rangos = cur.fetchall()
        cur.close()
        conn.close()

        fechas = set()
        for inicio, fin in rangos:
            año_ini, mes_ini = map(int, inicio.split("-")[:2])
            año_fin, mes_fin = map(int, fin.split("-")[:2])
            # Genera todos los meses entre inicio y fin
            while (año_ini < año_fin) or (año_ini == año_fin and mes_ini <= mes_fin):
                fechas.add(f"{año_ini}-{mes_ini:02d}")
                mes_ini += 1
                if mes_ini > 12:
                    mes_ini = 1
                    año_ini += 1

        fechas_ordenadas = sorted(fechas)
        return jsonify(fechas_ordenadas)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@routes.route('/api/promedio-riesgo-zona', methods=['GET'])
def promedio_riesgo_zona():

    # Calcula el promedio del índice de riesgo de los últimos 24 meses
    # para la zona seleccionada y devuelve un GeoTIFF.

    zona = request.args.get('zona')
    valor = request.args.get('valor')

    if not zona or not valor:
        return jsonify({'error': 'Faltan parámetros'}), 400

    try:
        # Obtiene el último archivo de riesgo subido
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT ruta, fecha_final_datos
            FROM archivos
            WHERE tipo_archivo = 'riesgo'
              AND es_riesgo_final = TRUE
            ORDER BY fecha_final_datos DESC
            LIMIT 1
        """)
        resultado = cur.fetchone()
        cur.close()
        conn.close()

        if not resultado:
            return jsonify({'error': 'No se encontró archivo de riesgo'}), 404

        ruta_riesgo, fecha_final = resultado

        # Abrir el dataset con decode_times=False por el problema de "months since"
        ds = xr.open_dataset(ruta_riesgo, decode_times=False)
        riesgo = ds['riesgo_hidrico'] 

        # Calcular promedio de los últimos 24 meses
        riesgo_promedio = riesgo[-24:, :, :].mean(dim='time', keep_attrs=True)

        # Crear un nuevo NetCDF temporal para reutilizar la lógica de GeoTIFF
        temp_ds = xr.Dataset({'riesgo_hidrico': riesgo_promedio.expand_dims(time=[0])})
        temp_filename = f"promedio_riesgo_{uuid.uuid4().hex}.nc"
        temp_path = os.path.join(tempfile.gettempdir(), temp_filename)
        temp_ds.to_netcdf(temp_path)

        # Obtener geometría y generar TIFF
        zona_gdf = obtener_zona_gdf(zona, valor).to_crs(epsg=4326)
        ruta_tif = generar_geotiff_riesgo_zona(zona_gdf, temp_path, 0)

        return send_file(ruta_tif, mimetype='image/tiff')

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500