#  Proyecto Riesgo Hídrico

Herramienta web para calcular y visualizar índices de riesgo hídrico (sequía e inundación) a partir de datos NetCDF en Chile. Incluye:

- **Backend** (Flask + PostgreSQL):  
  - Procesamiento de NetCDF (recortes, capas fuzzy, cálculo de índice hídrico).  
  - Servicios REST para servir GeoTIFF recortados por zona y promedio de últimos 2 años.  
  - Almacenamiento de metadatos en base de datos y reuse de archivos procesados.  

- **Frontend** (React + Leaflet):  
  - Subida de pares de archivos NetCDF (`pr` y `t2m`).  
  - Selector jerárquico de Región / Provincia / Comuna.  
  - Selector de fecha (mensual) — solo meses disponibles.  
  - Visualización de mapa con GeoTIFF superpuesto y contorno de la zona.  
  - Opción de “Ver promedio últimos 2 años”.  
  - Leyenda de gradiente de riesgo (azul → rojo).  

  ---

##  Estructura\/backend

├─ app/
│ ├─ routes.py
│ ├─ procesar.py
│ ├─ ubicaciones.py
│ └─ database.py
├─ uploads/ # directorio de NetCDF, GeoTIFF, recortes, fuzzy, índices
├─ shapefiles/ # archivos .shp de regiones/provincias/comunas
├─ requirements.txt
└─ server.py

/frontend
├─ public/
├─ src/
│ ├─ components/
│ │ ├─ FileUpload.jsx
│ │ ├─ ZonaSelector.jsx
│ │ ├─ FechaSelector.jsx
│ │ └─ MapaImagen.jsx
│ ├─ assets/
│ │ ├─ escudo-ubb.png
│ │ └─ logo-face.png
│ ├─ App.jsx
│ ├─ App.css
│ └─ main.jsx
├─ package.json
└─ vite.config.js

---

##  Requisitos

- Python 3.8+ / Node 16+  
- PostgreSQL  
- Git LFS para grandes archivos NetCDF y shapefiles  
- Variables de entorno (en `.env`):
  ```bash
  DATABASE_URL=postgresql://usuario:clave@host:puerto/dbname
  FLASK_ENV=development

---

##  Instalación

- **Backend**
  - cd backend
  - python -m venv venv
  - # Windows PowerShell:
  - venv\Scripts\activate
  - pip install -r requirements.txt
  - python server.py

- **Frontend**
  - cd frontend
  - npm install
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

 - **Visualización**
  - El mapa ajusta el zoom a la zona mostrando el GeoTIFF y el contorno administrativo.

  ---

## API Endpoints
**Ruta**	                        **Método**	            **Descripción**
/upload	                              POST                  Subir 1 archivo NetCDF (recorta, fuzzy, riesgo).
/api/ubicaciones	                  GET	                Jerarquía Región→Provincia→Comuna.
/api/lista-zonas?zona=<tipo>          GET	                Listado de nombres según `zona=region
/api/fechas-disponibles	              GET	                Lista de YYYY-MM disponibles.
/api/riesgo-zona?...	              GET	                Estadísticas (min/max/mean) de riesgo por zona y fecha.
/api/riesgo-geotiff?...	              GET	                GeoTIFF recortado para mostrar en mapa.
/api/promedio-riesgo-zona?...	      GET	                GeoTIFF promedio últimos 24 meses.
/api/geojson?...	                  GET	                GeoJSON de la zona administrativa.
/descargas/geotiff/<nombre>	          GET	                Servir GeoTIFF guardado en /uploads/riesgo/geotiff/.

 ---

 ## Tecnologías
- Backend: Flask, Xarray, NetCDF4, scikit-fuzzy, GeoPandas, Rasterio, psycopg2

- Frontend: React, Vite, Leaflet, georaster-layer-for-leaflet

- Datos: NetCDF (CR2MET), shapefiles (Biblioteca del Congreso Nacional de Chile)

