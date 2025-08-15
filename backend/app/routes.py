from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename

import os
import json
import xarray as xr
import traceback
import datetime
import tempfile
import uuid
from shapely.geometry import box
import geopandas as gpd

from app.database import get_connection
from app.ubicaciones import (
    cargar_jerarquia_ubicaciones,
    obtener_zona_gdf)
from app.procesar import (
    recortar_ultimos_5_anos,
    generar_capas_fuzzy,
    calcular_indice_riesgo_fuzzy,
    calcular_indice_riesgo_crisp,
    calcular_fecha_desde_indice,
    generar_geotiff_zona,
    calcular_stats_fuzzy,
    limpiar_atributos_conflictivos
)

#Blueprint para organizar las rutas
routes = Blueprint('routes', __name__)

# Se define la carpeta donde se suben los NetCDF originales
UPLOAD_FOLDER = './uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@routes.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Archivo no encontrado'}), 400

    # 1) Guardar crisp
    file     = request.files['file']
    filename = secure_filename(file.filename)
    crisp_dir  = os.path.join(UPLOAD_FOLDER, 'crisp')
    os.makedirs(crisp_dir, exist_ok=True)
    crisp_path = os.path.join(crisp_dir, filename)
    file.save(crisp_path)

    try:
        conn = get_connection()
        cur  = conn.cursor()

        # 2) Recortar últimos 60 meses
        recortado_path = recortar_ultimos_5_anos(crisp_path)
        nombre_base    = os.path.basename(recortado_path).split("_")[1]  # 'YYYY-MM'
        tipo_rec       = os.path.basename(recortado_path).split("_")[0]  # 'pr' o 't2m'

        # 2a) Registrar recortado si no existe
        cur.execute("SELECT 1 FROM archivos WHERE ruta=%s", (recortado_path,))
        if not cur.fetchone():
            fecha_ini = calcular_fecha_desde_indice(nombre_base, 1)
            fecha_fin = calcular_fecha_desde_indice(nombre_base, 60)
            cur.execute("""
                INSERT INTO archivos (
                  nombre, ruta, variables, tipo_archivo,
                  nombre_base, fecha_subida,
                  fecha_inicial_datos, fecha_final_datos,
                  es_riesgo_final
                ) VALUES (%s,%s,%s,%s,%s,NOW(),%s,%s,%s)
            """, (
                os.path.basename(recortado_path),
                recortado_path,
                tipo_rec,
                tipo_rec,
                nombre_base,
                fecha_ini,
                fecha_fin,
                False
            ))
            conn.commit()

        # 3) Generar riesgo_crisp si ya existen ambos recortados
        carpeta_rec = os.path.dirname(recortado_path)
        otra_var    = 't2m' if tipo_rec == 'pr' else 'pr'
        otro_rec    = os.path.join(carpeta_rec, f"{otra_var}_{nombre_base}_recortado.nc")

        if os.path.exists(otro_rec):
            pr_rec  = recortado_path if tipo_rec == 'pr' else otro_rec
            t2m_rec = recortado_path if tipo_rec == 't2m' else otro_rec

            cur.execute("""
                SELECT ruta FROM archivos
                WHERE tipo_archivo = 'riesgo_crisp'
                  AND nombre_base   = %s
            """, (nombre_base,))
            fila_crisp = cur.fetchone()

            if fila_crisp:
                ruta_crisp_bd = fila_crisp[0]
                if not os.path.exists(ruta_crisp_bd):
                    res_crisp = calcular_indice_riesgo_crisp(pr_rec, t2m_rec)
                    cur.execute("""
                        UPDATE archivos
                        SET ruta=%s
                        WHERE tipo_archivo='riesgo_crisp' AND nombre_base=%s
                    """, (res_crisp['archivo'], nombre_base))
                    conn.commit()
                ruta_crisp = ruta_crisp_bd
            else:
                res_crisp = calcular_indice_riesgo_crisp(pr_rec, t2m_rec)
                ruta_crisp = res_crisp['archivo']
                fecha_ini = calcular_fecha_desde_indice(nombre_base, 1)
                fecha_fin = calcular_fecha_desde_indice(nombre_base, 60)
                cur.execute("""
                    INSERT INTO archivos (
                      nombre, ruta, variables, tipo_archivo,
                      nombre_base, fecha_subida,
                      fecha_inicial_datos, fecha_final_datos,
                      es_riesgo_final
                    ) VALUES (%s,%s,%s,%s,%s,NOW(),%s,%s,%s)
                """, (
                    os.path.basename(ruta_crisp),
                    ruta_crisp,
                    'riesgo_crisp',
                    'riesgo_crisp',
                    nombre_base,
                    fecha_ini,
                    fecha_fin,
                    True
                ))
                conn.commit()
        else:
            ruta_crisp = None

        # 4) Generar capas fuzzy
        resultado_fuzzy = generar_capas_fuzzy(recortado_path)
        ruta_fuzzy      = resultado_fuzzy['archivo_salida']
        tipo            = resultado_fuzzy['tipo_variable']
        nombre_base     = resultado_fuzzy['nombre_base']

        fecha_ini_fuzzy = calcular_fecha_desde_indice(nombre_base, 1)
        fecha_fin_fuzzy = calcular_fecha_desde_indice(nombre_base, 60)

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
                False
            ))
            conn.commit()

        # 5) Generar riesgo_fuzzy cuando existan ambas fuzzy
        fuzzy_dir = os.path.dirname(ruta_fuzzy)
        otro_var  = 't2m' if tipo == 'pr' else 'pr'
        comp_path = os.path.join(fuzzy_dir, f"fuzzy_{otro_var}_{nombre_base}.nc")

        if os.path.exists(comp_path):
            pr_fuzzy  = ruta_fuzzy if tipo == 'pr' else comp_path
            t2m_fuzzy = ruta_fuzzy if tipo == 't2m' else comp_path

            cur.execute("""
                SELECT ruta FROM archivos
                WHERE tipo_archivo='riesgo_fuzzy' AND nombre_base=%s
            """, (nombre_base,))
            fila = cur.fetchone()

            if fila:
                riesgo_fuzzy_path = fila[0]
                if not os.path.exists(riesgo_fuzzy_path):
                    res_riesgo = calcular_indice_riesgo_fuzzy(pr_fuzzy, t2m_fuzzy)
                    cur.execute("""
                        UPDATE archivos
                        SET ruta=%s
                        WHERE tipo_archivo='riesgo_fuzzy' AND nombre_base=%s
                    """, (res_riesgo['archivo'], nombre_base))
                    conn.commit()
            else:
                res_riesgo = calcular_indice_riesgo_fuzzy(pr_fuzzy, t2m_fuzzy)
                riesgo_fuzzy_path = res_riesgo['archivo']
                fecha_ini_r = calcular_fecha_desde_indice(nombre_base, 1)
                fecha_fin_r = calcular_fecha_desde_indice(nombre_base, 60)
                with xr.open_dataset(riesgo_fuzzy_path, decode_times=False) as ds_r:
                    variables_en_archivo = ",".join(ds_r.data_vars.keys())
                cur.execute("""
                    INSERT INTO archivos (
                      nombre, ruta, variables, tipo_archivo,
                      nombre_base, fecha_subida,
                      fecha_inicial_datos, fecha_final_datos,
                      es_riesgo_final
                    ) VALUES (%s,%s,%s,%s,%s,NOW(),%s,%s,%s)
                """, (
                    os.path.basename(riesgo_fuzzy_path),
                    riesgo_fuzzy_path,
                    variables_en_archivo,
                    'riesgo_fuzzy',
                    nombre_base,
                    fecha_ini_r,
                    fecha_fin_r,
                    True
                ))
                conn.commit()
        else:
            riesgo_fuzzy_path = None

        cur.close()
        conn.close()

        # 6) Respuesta con todos los nombres generados
        return jsonify({
            'mensaje'        : 'Archivos procesados correctamente',
            'nombre_base'    : nombre_base,
            'recortado'      : os.path.basename(recortado_path),
            'riesgo_crisp'     : ruta_crisp and os.path.basename(ruta_crisp),
            'fuzzy'          : os.path.basename(ruta_fuzzy),
            'riesgo_fuzzy'   : riesgo_fuzzy_path and os.path.basename(riesgo_fuzzy_path)
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@routes.route('/api/ubicaciones', methods=['GET'])
def obtener_ubicaciones():

    # Devuelve la jerarquía de regiones/provincias/comunas como JSON.

    try:
        jerarquia = cargar_jerarquia_ubicaciones()
        return jsonify(jerarquia)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@routes.route('/api/riesgo-fuzzy-geotiff', methods=['GET'])
def servir_riesgo_fuzzy_geotiff():

    # Devuelve un GeoTIFF recortado al área de la zona y al mes solicitado.
    # Busca en BD el NetCDF que cubra la fecha, calcula el índice de tiempo
    # y genera el TIFF.

    zona = request.args.get('zona')
    valor = request.args.get('valor')
    fecha = request.args.get('fecha')  # esperaremos un string "YYYY-MM"

    if not zona or not valor or not fecha:
        return jsonify({'error': 'Faltan parámetros'}), 400

    try:
        # Normalizar la fecha a "YYYY-MM"
        fecha_texto = fecha.strip()

        # Busca en la BD el archivo de riesgo_fuzzy que cubra ese mes
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT ruta, nombre_base, fecha_inicial_datos
            FROM archivos
            WHERE tipo_archivo   = 'riesgo_fuzzy'
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
                'error': f'No se encontró un archivo de riesgo_fuzzy que abarque {fecha_texto}'
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
        ruta_tif = generar_geotiff_zona(zona_gdf, ruta_riesgo, meses_diferencia,'riesgo_fuzzy')

        return send_file(ruta_tif, mimetype='image/tiff')

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@routes.route('/api/riesgo-crisp-geotiff', methods=['GET'])
def servir_riesgo_crisp_geotiff():

    # Devuelve un GeoTIFF recortado al área de la zona y al mes solicitado.
    # Busca en BD el NetCDF que cubra la fecha, calcula el índice de tiempo
    # y genera el TIFF.

    zona  = request.args.get('zona')
    valor = request.args.get('valor')
    fecha = request.args.get('fecha')  # "YYYY-MM"
    if not zona or not valor or not fecha:
        return jsonify({'error': 'Faltan parámetros'}), 400

    # 1) Buscar en BD el NetCDF de riesgo_crisp que cubra esa fecha
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT ruta, nombre_base, fecha_inicial_datos
        FROM archivos
        WHERE tipo_archivo = 'riesgo_crisp'
          AND fecha_inicial_datos <= %s
          AND fecha_final_datos   >= %s
        ORDER BY fecha_final_datos DESC
        LIMIT 1
    """, (fecha, fecha))
    fila = cur.fetchone()
    cur.close(); conn.close()

    if not fila:
        return jsonify({'error': f'No se encontró un archivo de riesgo_crisp que abarque {fecha}'}), 404

    ruta_crisp, nombre_base, fecha_ini = fila

    # 2) Calcular el índice de tiempo (0–59)
    fecha_pedida  = datetime.datetime.strptime(fecha, "%Y-%m").date().replace(day=1)
    fecha_inicial = datetime.datetime.strptime(fecha_ini[:7], "%Y-%m").date().replace(day=1)
    meses_index   = (fecha_pedida.year - fecha_inicial.year) * 12 + (fecha_pedida.month - fecha_inicial.month)
    if meses_index < 0 or meses_index >= 60:
        return jsonify({'error': 'Índice de tiempo fuera de rango (0–59)'}), 400

    # 3) Generar y devolver el GeoTIFF
    zona_gdf = obtener_zona_gdf(zona, valor).to_crs(epsg=4326)
    ruta_tif = generar_geotiff_zona(zona_gdf, ruta_crisp, meses_index, 'riesgo_crisp')

    return send_file(ruta_tif, mimetype='image/tiff')

@routes.route('/api/precipitacion-geotiff', methods=['GET'])
def servir_precipitacion_geotiff():

    # 1) Leer parámetros de consulta
    zona  = request.args.get('zona')
    valor = request.args.get('valor')
    fecha = request.args.get('fecha')  # formato "YYYY-MM"
    if not zona or not valor or not fecha:
        # Si falta alguno, devolvemos error 400
        return jsonify({'error': 'Faltan parámetros'}), 400

    # 2) Buscar en la BD el NetCDF de precipitación que cubra la fecha
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT ruta, nombre_base, fecha_inicial_datos
        FROM archivos
        WHERE tipo_archivo = 'pr'
          AND fecha_inicial_datos <= %s
          AND fecha_final_datos   >= %s
        ORDER BY fecha_final_datos DESC
        LIMIT 1
    """, (fecha, fecha))
    fila = cur.fetchone()
    cur.close(); conn.close()

    if not fila:
        # No existe archivo para ese mes
        return jsonify({'error': f'No hay datos de precipitación para {fecha}'}), 404
    
    # 3) Desempaquetar ruta y fechas
    ruta_pr, nombre_base, fecha_ini = fila

    # 4) Calcular índice temporal dentro del NetCDF:cuántos meses hay entre fecha_ini y fecha_pedida
    fecha_pedida  = datetime.datetime.strptime(fecha, "%Y-%m").date().replace(day=1)
    fecha_inicial = datetime.datetime.strptime(fecha_ini[:7], "%Y-%m").date().replace(day=1)
    meses_index   = (fecha_pedida.year - fecha_inicial.year) * 12 + (fecha_pedida.month - fecha_inicial.month)

    # 5) Obtener geometría de la zona y generar GeoTIFF recortado
    zona_gdf = obtener_zona_gdf(zona, valor).to_crs(epsg=4326)
    ruta_tif = generar_geotiff_zona(zona_gdf, ruta_pr, meses_index, 'pr') # nombre de la variable en el NetCDF

    # 6) Devolver el archivo GeoTIFF como respuesta
    return send_file(ruta_tif, mimetype='image/tiff')

@routes.route('/api/precipitacion-baja-fuzzy-geotiff', methods=['GET'])
def servir_precipitacion_baja_fuzzy_geotiff():
    # 1) Leer parámetros de consulta
    zona  = request.args.get('zona')
    valor = request.args.get('valor')
    fecha = request.args.get('fecha')
    if not zona or not valor or not fecha:
        return jsonify({'error': 'Faltan parámetros'}), 400

    # 2) Buscar en BD el NetCDF fuzzy de precipitación (capas _baja/_media/_alta)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT ruta, nombre_base, fecha_inicial_datos
        FROM archivos
        WHERE tipo_archivo = 'pr'                          -- buscamos archivos fuzzy de pr
          AND nombre       LIKE 'fuzzy_pr_%%'               -- prefijo fuzzy_pr_
          AND fecha_inicial_datos <= %s
          AND fecha_final_datos   >= %s
        ORDER BY fecha_final_datos DESC
        LIMIT 1
    """, (fecha, fecha))
    fila = cur.fetchone()
    cur.close()
    conn.close()

    if not fila:
        return jsonify({'error': f'No hay datos fuzzy de precipitación para {fecha}'}), 404

    # 3) Desempaquetar resultados
    ruta_fuzzy_pr, nombre_base, fecha_ini = fila

    # 4) Calcular índice temporal
    fecha_pedida  = datetime.datetime.strptime(fecha, "%Y-%m").date().replace(day=1)
    fecha_inicial = datetime.datetime.strptime(fecha_ini[:7], "%Y-%m").date().replace(day=1)
    meses_index   = (
        (fecha_pedida.year  - fecha_inicial.year) * 12 +
        (fecha_pedida.month - fecha_inicial.month)
    )

    # 5) Generar GeoTIFF de la capa “_baja” recortado a la zona
    zona_gdf = obtener_zona_gdf(zona, valor).to_crs(epsg=4326)
    ruta_tif = generar_geotiff_zona(
        zona_gdf,
        ruta_fuzzy_pr,
        meses_index,
        'pr_baja'  # nombre de la variable de grado de pertenencia baja
    )

    # 6) Enviar el TIFF al cliente
    return send_file(ruta_tif, mimetype='image/tiff')

@routes.route('/api/precipitacion-media-fuzzy-geotiff', methods=['GET'])
def servir_precipitacion_media_fuzzy_geotiff():
    # 1) Leer parámetros de la query string
    zona  = request.args.get('zona')
    valor = request.args.get('valor')
    fecha = request.args.get('fecha')  # formato "YYYY-MM"
    if not zona or not valor or not fecha:
        # Falta alguno de los parámetros obligatorios
        return jsonify({'error': 'Faltan parámetros'}), 400

    # 2) Consultar en la BD el NetCDF fuzzy de precipitación (cualquiera de pr_baja/pr_media/pr_alta)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT ruta, nombre_base, fecha_inicial_datos
        FROM archivos
        WHERE tipo_archivo = 'pr'
          AND nombre       LIKE 'fuzzy_pr_%%'     -- archivos generados por generar_capas_fuzzy
          AND fecha_inicial_datos <= %s           -- que incluyan la fecha solicitada
          AND fecha_final_datos   >= %s
        ORDER BY fecha_final_datos DESC           -- tomar el más reciente
        LIMIT 1
    """, (fecha, fecha))
    fila = cur.fetchone()
    cur.close()
    conn.close()

    if not fila:
        # No hay ningún NetCDF fuzzy para esa fecha
        return jsonify({'error': f'No hay datos fuzzy de precipitación para {fecha}'}), 404

    # 3) Extraer ruta y rangos de fecha desde la fila
    ruta_fuzzy_pr, nombre_base, fecha_ini = fila

    # 4) Calcular el índice de tiempo: diferencia en meses entre fecha_ini y la solicitada
    fecha_pedida  = datetime.datetime.strptime(fecha, "%Y-%m").date().replace(day=1)
    fecha_inicial = datetime.datetime.strptime(fecha_ini[:7], "%Y-%m").date().replace(day=1)
    meses_index   = (
        (fecha_pedida.year  - fecha_inicial.year) * 12 +
        (fecha_pedida.month - fecha_inicial.month)
    )

    # 5) Cargar la geometría de la zona y generar el GeoTIFF de la capa "pr_media"
    zona_gdf = obtener_zona_gdf(zona, valor).to_crs(epsg=4326)
    ruta_tif = generar_geotiff_zona(
        zona_gdf,
        ruta_fuzzy_pr,
        meses_index,
        'pr_media'  # variable de salida dentro del NetCDF
    )

    # 6) Enviar el GeoTIFF resultante
    return send_file(ruta_tif, mimetype='image/tiff')

@routes.route('/api/precipitacion-alta-fuzzy-geotiff', methods=['GET'])
def servir_precipitacion_alta_fuzzy_geotiff():
    # 1) Leer parámetros de la query string
    zona  = request.args.get('zona')
    valor = request.args.get('valor')
    fecha = request.args.get('fecha')
    if not zona or not valor or not fecha:
        return jsonify({'error': 'Faltan parámetros'}), 400

    # 2) Consultar en la BD el NetCDF fuzzy de precipitación
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT ruta, nombre_base, fecha_inicial_datos
        FROM archivos
        WHERE tipo_archivo = 'pr'
          AND nombre       LIKE 'fuzzy_pr_%%'
          AND fecha_inicial_datos <= %s
          AND fecha_final_datos   >= %s
        ORDER BY fecha_final_datos DESC
        LIMIT 1
    """, (fecha, fecha))
    fila = cur.fetchone()
    cur.close()
    conn.close()

    if not fila:
        return jsonify({'error': f'No hay datos fuzzy de precipitación para {fecha}'}), 404

    # 3) Desempaquetar ruta y fecha inicial del NetCDF
    ruta_fuzzy_pr, nombre_base, fecha_ini = fila

    # 4) Calcular índice temporal dentro del NetCDF
    fecha_pedida  = datetime.datetime.strptime(fecha, "%Y-%m").date().replace(day=1)
    fecha_inicial = datetime.datetime.strptime(fecha_ini[:7], "%Y-%m").date().replace(day=1)
    meses_index   = (
        (fecha_pedida.year  - fecha_inicial.year) * 12 +
        (fecha_pedida.month - fecha_inicial.month)
    )

    # 5) Generar GeoTIFF de la capa "pr_alta" recortado a la zona
    zona_gdf = obtener_zona_gdf(zona, valor).to_crs(epsg=4326)
    ruta_tif = generar_geotiff_zona(
        zona_gdf,
        ruta_fuzzy_pr,
        meses_index,
        'pr_alta'  # variable de grado de pertenencia alta
    )

    # 6) Retornar el GeoTIFF
    return send_file(ruta_tif, mimetype='image/tiff')

@routes.route('/api/temperatura-geotiff', methods=['GET'])
def servir_temperatura_geotiff():
    # 1) Leer parámetros de la query string: zona (comuna/provincia/región), valor (nombre)
    #    y fecha en formato "YYYY-MM".
    zona  = request.args.get('zona')
    valor = request.args.get('valor')
    fecha = request.args.get('fecha')
    if not zona or not valor or not fecha:
        # Si falta alguno, devolvemos error 400 Bad Request.
        return jsonify({'error': 'Faltan parámetros'}), 400

    # 2) Conectar a la base de datos y buscar el NetCDF de temperatura (t2m)
    #    que cubra la fecha solicitada.
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT ruta, nombre_base, fecha_inicial_datos
        FROM archivos
        WHERE tipo_archivo = 't2m'
          AND fecha_inicial_datos <= %s
          AND fecha_final_datos   >= %s
        ORDER BY fecha_final_datos DESC
        LIMIT 1
    """, (fecha, fecha))
    fila = cur.fetchone()
    cur.close()
    conn.close()

    if not fila:
        # Si no hay un archivo t2m que abarque esa fecha, devolvemos 404.
        return jsonify({'error': f'No hay datos de temperatura para {fecha}'}), 404

    # 3) Extraer la ruta del NetCDF, el nombre_base y la fecha inicial de datos
    ruta_t2m, nombre_base, fecha_ini = fila

    # 4) Calcular el índice de tiempo dentro del NetCDF:
    #    cuántos meses han pasado desde fecha_ini hasta fecha solicitada.
    fecha_pedida  = datetime.datetime.strptime(fecha, "%Y-%m").date().replace(day=1)
    fecha_inicial = datetime.datetime.strptime(fecha_ini[:7], "%Y-%m").date().replace(day=1)
    meses_index   = (
        (fecha_pedida.year  - fecha_inicial.year) * 12 +
        (fecha_pedida.month - fecha_inicial.month)
    )

    # 5) Obtener el GeoDataFrame de la zona y reproyectarlo a WGS84 (EPSG:4326).
    zona_gdf = obtener_zona_gdf(zona, valor).to_crs(epsg=4326)

    #    Generar el GeoTIFF recortado a la zona y al time‐step calculado,
    #    extrayendo la variable "t2m" del NetCDF.
    ruta_tif = generar_geotiff_zona(
        zona_gdf,
        ruta_t2m,
        meses_index,
        't2m'  # nombre de la variable a extraer del NetCDF
    )

    # 6) Devolver el GeoTIFF resultante con el MIME type apropiado.
    return send_file(ruta_tif, mimetype='image/tiff')

@routes.route('/api/temperatura-baja-fuzzy-geotiff', methods=['GET'])
def servir_temperatura_baja_fuzzy_geotiff():
    # 1) Leer parámetros de la query: zona (comuna/provincia/región), valor y fecha "YYYY-MM"
    zona  = request.args.get('zona')
    valor = request.args.get('valor')
    fecha = request.args.get('fecha')
    if not zona or not valor or not fecha:
        # Si falta alguno, devolvemos 400 Bad Request
        return jsonify({'error': 'Faltan parámetros'}), 400

    # 2) Buscar en la base de datos el archivo fuzzy de temperatura (t2m_baja) que cubra ese mes
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT ruta, nombre_base, fecha_inicial_datos
        FROM archivos
        WHERE tipo_archivo = 't2m'
          AND nombre       LIKE 'fuzzy_t2m_%%'
          AND fecha_inicial_datos <= %s
          AND fecha_final_datos   >= %s
        ORDER BY fecha_final_datos DESC
        LIMIT 1
    """, (fecha, fecha))
    fila = cur.fetchone()
    cur.close()
    conn.close()

    if not fila:
        # Si no existe, devolvemos 404 Not Found
        return jsonify({'error': f'No hay datos fuzzy de temperatura para {fecha}'}), 404

    # 3) Desempaquetar ruta al NetCDF fuzzy, nombre_base y fecha inicial
    ruta_fuzzy_t2m, nombre_base, fecha_ini = fila

    # 4) Calcular el índice de tiempo (mes) dentro del NetCDF
    fecha_pedida  = datetime.datetime.strptime(fecha, "%Y-%m").date().replace(day=1)
    fecha_inicial = datetime.datetime.strptime(fecha_ini[:7], "%Y-%m").date().replace(day=1)
    meses_index   = (
        (fecha_pedida.year  - fecha_inicial.year) * 12 +
        (fecha_pedida.month - fecha_inicial.month)
    )

    # 5) Obtener la geometría de la zona y asegurar CRS WGS84
    zona_gdf = obtener_zona_gdf(zona, valor).to_crs(epsg=4326)

    # 6) Generar el GeoTIFF recortado usando la variable 't2m_baja' en el índice calculado
    ruta_tif = generar_geotiff_zona(
        zona_gdf,
        ruta_fuzzy_t2m,
        meses_index,
        't2m_baja'  # nombre de la banda fuzzy baja de temperatura
    )

    # 7) Devolver el archivo GeoTIFF al cliente
    return send_file(ruta_tif, mimetype='image/tiff')

@routes.route('/api/temperatura-media-fuzzy-geotiff', methods=['GET'])
def servir_temperatura_media_fuzzy_geotiff():
    # 1) Leer parámetros de la petición
    zona  = request.args.get('zona')
    valor = request.args.get('valor')
    fecha = request.args.get('fecha')
    if not zona or not valor or not fecha:
        # Parámetros obligatorios faltantes  400 Bad Request
        return jsonify({'error': 'Faltan parámetros'}), 400

    # 2) Consultar en BD el NetCDF fuzzy de temperatura que cubre la fecha
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT ruta, nombre_base, fecha_inicial_datos
        FROM archivos
        WHERE tipo_archivo = 't2m'
          AND nombre       LIKE 'fuzzy_t2m_%%'
          AND fecha_inicial_datos <= %s
          AND fecha_final_datos   >= %s
        ORDER BY fecha_final_datos DESC
        LIMIT 1
    """, (fecha, fecha))
    fila = cur.fetchone()
    cur.close()
    conn.close()

    if not fila:
        # Si no hay resultado  404 Not Found
        return jsonify({'error': f'No hay datos fuzzy de temperatura para {fecha}'}), 404

    # 3) Desempaquetar resultados: ruta al archivo, nombre_base, fecha inicial
    ruta_fuzzy_t2m, nombre_base, fecha_ini = fila

    # 4) Calcular índice temporal (0–59) dentro del NetCDF
    fecha_pedida  = datetime.datetime.strptime(fecha, "%Y-%m").date().replace(day=1)
    fecha_inicial = datetime.datetime.strptime(fecha_ini[:7], "%Y-%m").date().replace(day=1)
    meses_index   = (
        (fecha_pedida.year  - fecha_inicial.year) * 12 +
        (fecha_pedida.month - fecha_inicial.month)
    )

    # 5) Obtener geometría de la zona y asegurar CRS EPSG:4326
    zona_gdf = obtener_zona_gdf(zona, valor).to_crs(epsg=4326)

    # 6) Generar GeoTIFF recortado usando la variable 't2m_media'
    ruta_tif = generar_geotiff_zona(
        zona_gdf,
        ruta_fuzzy_t2m,
        meses_index,
        't2m_media'  # grado de pertenencia media
    )

    # 7) Enviar el GeoTIFF resultante al cliente
    return send_file(ruta_tif, mimetype='image/tiff')

@routes.route('/api/temperatura-alta-fuzzy-geotiff', methods=['GET'])
def servir_temperatura_alta_fuzzy_geotiff():
    # 1) Leer parámetros de la petición
    zona  = request.args.get('zona')
    valor = request.args.get('valor')
    fecha = request.args.get('fecha')
    if not zona or not valor or not fecha:
        return jsonify({'error': 'Faltan parámetros'}), 400

    # 2) Consultar en BD el NetCDF fuzzy de temperatura que cubre la fecha
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT ruta, nombre_base, fecha_inicial_datos
        FROM archivos
        WHERE tipo_archivo = 't2m'
          AND nombre       LIKE 'fuzzy_t2m_%%'
          AND fecha_inicial_datos <= %s
          AND fecha_final_datos   >= %s
        ORDER BY fecha_final_datos DESC
        LIMIT 1
    """, (fecha, fecha))
    fila = cur.fetchone()
    cur.close()
    conn.close()

    if not fila:
        # Sin datos disponibles  404
        return jsonify({'error': f'No hay datos fuzzy de temperatura para {fecha}'}), 404

    # 3) Desempaquetar ruta, nombre_base y fecha inicial
    ruta_fuzzy_t2m, nombre_base, fecha_ini = fila

    # 4) Calcular índice de tiempo dentro del NetCDF
    fecha_pedida  = datetime.datetime.strptime(fecha, "%Y-%m").date().replace(day=1)
    fecha_inicial = datetime.datetime.strptime(fecha_ini[:7], "%Y-%m").date().replace(day=1)
    meses_index   = (
        (fecha_pedida.year  - fecha_inicial.year) * 12 +
        (fecha_pedida.month - fecha_inicial.month)
    )

    # 5) Obtener y reproyectar geometría de la zona
    zona_gdf = obtener_zona_gdf(zona, valor).to_crs(epsg=4326)

    # 6) Generar GeoTIFF recortado con la variable 't2m_alta'
    ruta_tif = generar_geotiff_zona(
        zona_gdf,
        ruta_fuzzy_t2m,
        meses_index,
        't2m_alta'  # grado de pertenencia alta
    )

    # 7) Devolver el GeoTIFF generado
    return send_file(ruta_tif, mimetype='image/tiff')

@routes.route('/api/geojson', methods=['GET'])
def geojson_zona():
    """
    Devuelve el GeoJSON de la zona indicada (comuna, provincia, región,
    macro-zona norte/centro/sur o país).
    """
    comuna    = request.args.get('comuna')
    provincia = request.args.get('provincia')
    region    = request.args.get('region')
    pais      = request.args.get('pais')
    norte     = request.args.get('norte')
    centro    = request.args.get('centro')
    sur       = request.args.get('sur')

    try:
        # Leemos todas las regiones y pasamos a EPSG:4326
        regiones = gpd.read_file("shapefiles/regiones/Regional.shp") \
                      .to_crs(epsg=4326)

        if comuna:
            gdf = obtener_zona_gdf('comuna', comuna)
        elif provincia:
            gdf = obtener_zona_gdf('provincia', provincia)
        elif region:
            gdf = obtener_zona_gdf('region', region)
        elif pais is not None:
            # Todo Chile: usamos el bounding‐box completo
            minx, miny, maxx, maxy = regiones.total_bounds
            bbox = box(minx, miny, maxx, maxy)
            gdf = gpd.GeoDataFrame(
                {'geometry': [bbox]},
                geometry='geometry',
                crs="EPSG:4326"
            )
        elif norte is not None:
            # Norte: Arica/Coquimbo
            norte_list = [
              "Región de Arica y Parinacota",
              "Región de Tarapacá",
              "Región de Antofagasta",
              "Región de Atacama",
              "Región de Coquimbo"
            ]
            sel = regiones[regiones["Region"].isin(norte_list)]
            union = sel.geometry.unary_union
            gdf = gpd.GeoDataFrame(
                {'geometry': [union]},
                geometry='geometry',
                crs="EPSG:4326"
            )
        elif centro is not None:
            # Centro: Valparaíso/Ñuble/Bío-Bío
            centro_list = [
              "Región de Valparaíso",
              "Región Metropolitana de Santiago",
              "Región del Libertador Bernardo O'Higgins",
              "Región del Maule",
              "Región de Ñuble",
              "Región del Bío-Bío"
            ]
            sel = regiones[regiones["Region"].isin(centro_list)]
            union = sel.geometry.unary_union
            gdf = gpd.GeoDataFrame(
                {'geometry': [union]},
                geometry='geometry',
                crs="EPSG:4326"
            )
        elif sur is not None:
            # Sur: La Araucanía/Magallanes
            sur_list = [
              "Región de La Araucanía",
              "Región de Los Ríos",
              "Región de Los Lagos",
              "Región de Aysén del Gral.Ibañez del Campo",
              "Región de Magallanes y Antártica Chilena"
            ]
            sel = regiones[regiones["Region"].isin(sur_list)]
            union = sel.geometry.unary_union
            gdf = gpd.GeoDataFrame(
                {'geometry': [union]},
                geometry='geometry',
                crs="EPSG:4326"
            )
        else:
            return jsonify({
                'error': 'Falta un parámetro: comuna, provincia, region, pais, norte, centro o sur'
            }), 400

        # Serializamos el GeoDataFrame resultante a GeoJSON
        geojson_str = gdf.to_crs(epsg=4326).to_json()
        return jsonify(json.loads(geojson_str))

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@routes.route('/api/fechas-disponibles', methods=['GET'])
def fechas_disponibles():

    # Devuelve la lista de meses (YYYY-MM) para los cuales hay archivos
    # de riesgo_fuzzy disponibles en BD.

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT fecha_inicial_datos, fecha_final_datos
            FROM archivos
            WHERE tipo_archivo = 'riesgo_fuzzy' AND es_riesgo_final = TRUE
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

@routes.route('/api/promedio-riesgo-fuzzy-zona', methods=['GET'])
def promedio_riesgo_fuzzy_zona():
    
    # Calcula el promedio del índice 'riesgo_alto' (últimos 24 pasos temporales)
    # para la zona seleccionada y devuelve un GeoTIFF.
    
    zona = request.args.get('zona')
    valor = request.args.get('valor')

    if not zona or not valor:
        return jsonify({'error': 'Faltan parámetros'}), 400

    try:
        # Obtener el último archivo de riesgo_fuzzy (que ahora contiene las 9 variables)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT ruta, fecha_final_datos
            FROM archivos
            WHERE tipo_archivo = 'riesgo_fuzzy'
              AND es_riesgo_final = TRUE
            ORDER BY fecha_final_datos DESC
            LIMIT 1
        """)
        resultado = cur.fetchone()
        cur.close()
        conn.close()

        if not resultado:
            return jsonify({'error': 'No se encontró archivo de riesgo_fuzzy'}), 404

        ruta_riesgo, fecha_final = resultado

        # Abrir el dataset (decode_times=False si se usa ese esquema en el proyecto)
        ds = xr.open_dataset(ruta_riesgo, decode_times=False)

        var_name = 'riesgo_fuzzy' 
        if var_name not in ds.data_vars:
            ds.close()
            return jsonify({'error': f"La variable '{var_name}' no está presente en {os.path.basename(ruta_riesgo)}"}), 500

        # Extraer y promediar los últimos 24 pasos temporales
        riesgo_var = ds[var_name]
        if riesgo_var.sizes.get('time', 0) < 1:
            ds.close()
            return jsonify({'error': 'No hay dimensión temporal válida en el archivo de riesgo'}), 500

        # Tomar hasta 24 últimos, si hay menos toma todos
        n = min(24, riesgo_var.sizes['time'])
        riesgo_promedio = riesgo_var[-n:, :, :].mean(dim='time', keep_attrs=True)

        # Crear dataset temporal con dimensión time para compatibilidad con la generación de GeoTIFF
        temp_ds = xr.Dataset({var_name: riesgo_promedio.expand_dims(time=[0])})
        temp_ds = limpiar_atributos_conflictivos(temp_ds)

        temp_filename = f"promedio_{var_name}_{uuid.uuid4().hex}.nc"
        temp_path = os.path.join(tempfile.gettempdir(), temp_filename)
        temp_ds.to_netcdf(temp_path)
        temp_ds.close()
        ds.close()

        # Obtener geometría de recorte y generar el GeoTIFF
        zona_gdf = obtener_zona_gdf(zona, valor).to_crs(epsg=4326)
        ruta_tif = generar_geotiff_zona(zona_gdf, temp_path, 0, var_name)

        return send_file(ruta_tif, mimetype='image/tiff')

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@routes.route('/api/promedio-riesgo-crisp-zona', methods=['GET'])
def promedio_riesgo_crisp_zona():

    # Calcula el promedio del índice de riesgo_crisp de los últimos 24 meses
    # para la zona seleccionada y devuelve un GeoTIFF.

    zona = request.args.get('zona')
    valor = request.args.get('valor')

    if not zona or not valor:
        return jsonify({'error': 'Faltan parámetros'}), 400

    try:
        # Obtiene el último archivo de riesgo_crisp subido
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT ruta, fecha_final_datos
            FROM archivos
            WHERE tipo_archivo = 'riesgo_crisp'
              AND es_riesgo_final = TRUE
            ORDER BY fecha_final_datos DESC
            LIMIT 1
        """)
        resultado = cur.fetchone()
        cur.close()
        conn.close()

        if not resultado:
            return jsonify({'error': 'No se encontró archivo de riesgo_crisp'}), 404

        ruta_riesgo, fecha_final = resultado

        # Abrir el dataset con decode_times=False por el problema de "months since"
        ds = xr.open_dataset(ruta_riesgo, decode_times=False)
        riesgo_crisp = ds['riesgo_crisp'] 

        # Calcular promedio de los últimos 24 meses
        riesgo_promedio = riesgo_crisp[-24:, :, :].mean(dim='time', keep_attrs=True)

        # Crear un nuevo NetCDF temporal para reutilizar la lógica de GeoTIFF
        temp_ds = xr.Dataset({'riesgo_crisp': riesgo_promedio.expand_dims(time=[0])})
        temp_filename = f"promedio_riesgo_{uuid.uuid4().hex}.nc"
        temp_path = os.path.join(tempfile.gettempdir(), temp_filename)
        temp_ds.to_netcdf(temp_path)

        # Obtener geometría y generar TIFF
        zona_gdf = obtener_zona_gdf(zona, valor).to_crs(epsg=4326)
        ruta_tif = generar_geotiff_zona(zona_gdf, temp_path, 0, 'riesgo_crisp')

        return send_file(ruta_tif, mimetype='image/tiff')

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    
@routes.route('/api/precipitacion-fuzzy-stats', methods=['GET'])
def api_precipitacion_fuzzy_stats():
    zona  = request.args.get('zona')
    valor = request.args.get('valor')
    fecha = request.args.get('fecha')  # formato "YYYY-MM"
    if not zona or not valor or not fecha:
        return jsonify({'error': 'Faltan parámetros: zona, valor, fecha'}), 400

    # 1) Buscar el NetCDF de precipitación que cubra esa fecha
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT ruta, fecha_inicial_datos
        FROM archivos
        WHERE tipo_archivo = 'pr'
          AND fecha_inicial_datos <= %s
          AND fecha_final_datos   >= %s
        ORDER BY fecha_final_datos DESC
        LIMIT 1
    """, (fecha, fecha))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({'error': f'No hay datos de precipitación para {fecha}'}), 404

    ruta_nc, fecha_ini = row

    # 2) Calcular índice de tiempo (meses desde fecha_ini hasta fecha)
    f_req = datetime.datetime.strptime(fecha,     "%Y-%m").date().replace(day=1)
    f_ini = datetime.datetime.strptime(fecha_ini[:7], "%Y-%m").date().replace(day=1)
    idx = (f_req.year - f_ini.year) * 12 + (f_req.month - f_ini.month)
    if idx < 0:
        return jsonify({'error': 'Fecha solicitada anterior al inicio de datos'}), 400

    # 3) Obtener la geometría de la zona y reproyectar
    zona_gdf = obtener_zona_gdf(zona, valor).to_crs(epsg=4326)

    # 4) Calcular stats fuzzy
    try:
        stats = calcular_stats_fuzzy(zona_gdf, ruta_nc, idx, 'pr')
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@routes.route('/api/temperatura-fuzzy-stats', methods=['GET'])
def api_temperatura_fuzzy_stats():
    zona  = request.args.get('zona')
    valor = request.args.get('valor')
    fecha = request.args.get('fecha')  # formato "YYYY-MM"
    if not zona or not valor or not fecha:
        return jsonify({'error': 'Faltan parámetros: zona, valor, fecha'}), 400

    # 1) Buscar el NetCDF de temperatura que cubra esa fecha
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT ruta, fecha_inicial_datos
        FROM archivos
        WHERE tipo_archivo = 't2m'
          AND fecha_inicial_datos <= %s
          AND fecha_final_datos   >= %s
        ORDER BY fecha_final_datos DESC
        LIMIT 1
    """, (fecha, fecha))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({'error': f'No hay datos de temperatura para {fecha}'}), 404

    ruta_nc, fecha_ini = row

    # 2) Calcular índice de tiempo (meses desde fecha_ini hasta fecha)
    f_req = datetime.datetime.strptime(fecha,     "%Y-%m").date().replace(day=1)
    f_ini = datetime.datetime.strptime(fecha_ini[:7], "%Y-%m").date().replace(day=1)
    idx = (f_req.year - f_ini.year) * 12 + (f_req.month - f_ini.month)
    if idx < 0:
        return jsonify({'error': 'Fecha solicitada anterior al inicio de datos'}), 400

    # 3) Obtener la geometría de la zona y reproyectar
    zona_gdf = obtener_zona_gdf(zona, valor).to_crs(epsg=4326)

    # 4) Calcular stats fuzzy
    try:
        stats = calcular_stats_fuzzy(zona_gdf, ruta_nc, idx, 't2m')
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 400