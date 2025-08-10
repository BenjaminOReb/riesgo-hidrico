#  Proyecto Riesgo Hídrico

Herramienta web para calcular y visualizar índices de riesgo hídrico a partir de datos NetCDF en Chile. Incluye:

- **Backend** (Flask + PostgreSQL):  
  - **Backend** (Flask + PostgreSQL):  
  - Procesamiento de NetCDF (recortes a últimos 5 años, cálculo de índices crisp).  
  - **Generación de capas fuzzy**:  
    - Se definen tres **variables lingüísticas** para cada serie (`pr` o `t2m`): *baja*, *media*, *alta*.  
    - Para cada región se calculan sus correspondientes **funciones de pertenencia trapezoidales** (trapmf), adaptadas al rango local de valores.  
    - Combinación fuzzy del índice hídrico:  
      ```python
      riesgo_fuzzy = min(pr_baja, t2m_alta)
      ```
    - Servicios REST exponen tanto el índice crisp como el fuzzy.
  - Almacenamiento de metadatos en base de datos y reuse de archivos procesados.  

- **Frontend** (React + Leaflet + georaster-layer-for-leaflet):  
  - Subida de pares de archivos NetCDF (`pr` y `t2m`).  
  - Selector jerárquico de Región / Provincia / Comuna.  
  - Selector de fecha (mensual) — solo meses disponibles en BD.  
  - Selector de tipo de mapa (Temperatura, Precipitación o Riesgo Hídrico).  
  - Mapas dinámicos:  
    - **Riesgo**: 2 vistas (crisp / fuzzy) + “Ver promedio últimos 2 años”.  
    - **Precipitación/Temperatura**: 4 vistas (normal, fuzzy baja, media, alta).  
  - Leyendas incrustadas en cada mapa, con fondo semitransparente y etiquetas claras (mm o °C en normal, 0–1 en fuzzy). 

  ---

##  Estructura

```
backend/
├─ app/
│  ├─ routes.py
│  ├─ procesar.py
│  ├─ ubicaciones.py
│  └─ database.py
├─ uploads/        # NetCDF, GeoTIFF, recortes, fuzzy, índices
├─ shapefiles/     # .shp de regiones/provincias/comunas
├─ requirements.txt
└─ server.py

frontend/
├─ public/
├─ src/
│  ├─ components/
│  │  ├─ FileUpload.jsx
│  │  ├─ ZonaSelector.jsx
│  │  ├─ FechaSelector.jsx
│  │  └─ MapaImagen.jsx
│  ├─ assets/
│  │  ├─ escudo-ubb.png
│  │  └─ logo-face.png
│  ├─ App.jsx
│  ├─ App.css
│  └─ main.jsx
├─ package.json
└─ vite.config.js
```

---

##  Requisitos

- Python 3.8+ / Node 16+  
- PostgreSQL  
- Git LFS para grandes archivos NetCDF y shapefiles
- shapefiles: 
      - .CGP
      - .dbf
      - .prj
      - .shp
      - .shx
- Variables de entorno (en `.env`):
  ```bash
  DB_HOST=localhost
  DB_USER=nombre_usuario
  DB_PASSWORD=contraseña
  DB_NAME=nombre_db

---

##  Instalación

- **Backend**
  - cd backend
  - python -m venv venv
  - ## Windows PowerShell:
  - venv\Scripts\activate
  - pip install -r requirements.txt
  - python server.py

- **Frontend**
  - cd frontend
  - npm install
  - npm install apexcharts react-apexcharts
  - npm run dev

  Abrir en http://localhost:5173

  ---

## Uso

 - **Subir archivos**
  - En “Subir Archivos NetCDF” seleccione exactamente 2 archivos (pr y t2m) y espere.

 - **Seleccionar zona y fecha**
  - Elija Región/Provincia/Comuna y haga click en Ver en mapa.
  - El selector de fecha muestra solo los YYYY-MM disponibles.
  - Active Ver promedio últimos 2 años (checkbox).

 - **Seleccionar tipo de mapa**
  - Elija Riesgo/Temperatura/Precipitación.

 - **Visualización**
  - Se visualiza los mapas segun el tipo de mapa seleccionado.
  - El mapa ajusta el zoom a la zona mostrando el GeoTIFF y el contorno administrativo.
  - **Riesgo Hídrico fuzzy**: usa variables lingüísticas (*baja*, *media*, *alta*) y sus funciones de pertenencia trapezoidales para mapear el nivel de riesgo.  
   - El índice final fuzzy se calcula como `max(pr_baja, t2m_alta)` y se renderiza con rampas de color de 0 a 1.

  ---

## API Endpoints

| Ruta                                                         |   Método  | Descripción                                                                         |     
| ------------------------------------------------------------ | :-------: | ----------------------------------------------------------------------------------- |
| `/upload`                                                    |    POST   | Subir 1 NetCDF (recorta, fuzzy, índices crisp+fuzzy)                                  |     
| `/api/ubicaciones`                                           |    GET    | Jerarquía Región→Provincia→Comuna                                                   |     
| `/api/lista-zonas?zona={region/provincia/comuna}\`           | GET       | Listado de nombres según el tipo de zona                                            |
| `/api/riesgo-fuzzy-geotiff?zona=&valor=&fecha=`              | GET       | GeoTIFF de índice fuzzy por zona (variables lingüísticas *baja*, *media*, *alta*)   |     
| `/api/riesgo-crisp-zona?zona=&valor=&fecha=`                   |    GET    | Stats de índice crisp por zona (JSON)                                                 |     
| `/api/riesgo-fuzzy-geotiff?zona=&valor=&fecha=`              |    GET    | GeoTIFF de índice fuzzy recortado por zona (fuzzy con variables lingüísticas)       |     
| `/api/riesgo-crisp-geotiff?zona=&valor=&fecha=`                |    GET    | GeoTIFF de índice crisp recortado por zona                                            |     
| `/api/precipitacion-geotiff?zona=&valor=&fecha=`             |    GET    | GeoTIFF de precipitación (mm) recortado por zona                                    |     
| `/api/precipitacion-baja-fuzzy-geotiff?zona=&valor=&fecha=`  |    GET    | GeoTIFF de grado de pertenencia baja de precipitación                               |     
| `/api/precipitacion-media-fuzzy-geotiff?zona=&valor=&fecha=` |    GET    | GeoTIFF de grado de pertenencia media de precipitación                              |     
| `/api/precipitacion-alta-fuzzy-geotiff?zona=&valor=&fecha=`  |    GET    | GeoTIFF de grado de pertenencia alta de precipitación                               |     
| `/api/temperatura-geotiff?zona=&valor=&fecha=`               |    GET    | GeoTIFF de temperatura (°C) recortado por zona                                      |     
| `/api/temperatura-baja-fuzzy-geotiff?zona=&valor=&fecha=`    |    GET    | GeoTIFF de grado de pertenencia baja de temperatura                                 |     
| `/api/temperatura-media-fuzzy-geotiff?zona=&valor=&fecha=`   |    GET    | GeoTIFF de grado de pertenencia media de temperatura                                |     
| `/api/temperatura-alta-fuzzy-geotiff?zona=&valor=&fecha=`    |    GET    | GeoTIFF de grado de pertenencia alta de temperatura                                 |     
| `/api/geojson?region/provincia/comuna=`                      | GET       | GeoJSON de la zona indicada                                                         |
| `/api/fechas-disponibles`                                    |    GET    | Listado de meses (`YYYY-MM`) disponibles para riesgo fuzzy final                    |     
| `/api/promedio-riesgo-fuzzy-zona?zona=&valor=`               |    GET    | GeoTIFF de promedio de índice fuzzy de los últimos 24 meses (sin parámetro `fecha`) |     
| `/api/promedio-riesgo-crisp-zona?zona=&valor=`                 |    GET    | GeoTIFF de promedio de índice crisp de los últimos 24 meses (sin parámetro `fecha`)   |     
| `/descargas/geotiff/<nombre>`                                |    GET    | Descarga directa de GeoTIFF ya generado (en `uploads/.../geotiff/`)                 |     


 ---

 ## Tecnologías
- Backend: Flask, Xarray, NetCDF4, scikit-fuzzy, GeoPandas, Rasterio, psycopg2

- Frontend: React, Vite, Leaflet, georaster-layer-for-leaflet

- Datos: NetCDF (CR2MET), shapefiles (Biblioteca del Congreso Nacional de Chile)

