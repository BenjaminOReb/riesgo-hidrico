import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import GeoRasterLayer from "georaster-layer-for-leaflet";
import georaster from "georaster";

/*
 * Componente que renderiza un mapa Leaflet y muestra:
 * - El GeoTIFF de riesgo hídrico (o su promedio de los últimos 2 años).
 * - El contorno de la zona seleccionada (región/provincia/comuna).
 * - Una leyenda de colores.
 */

function MapaImagen({ zona, valor, fecha }) {
  // Referencia al objeto mapa de Leaflet, para no volver a inicializarlo en cada render
  const mapRef = useRef(null); 
  // Estado que indica si mostrar el promedio de los últimos 2 años en lugar de un mes concreto
  const [verPromedio, setVerPromedio] = useState(false); 

  useEffect(() => {
    // Función asíncrona para cargar y dibujar el GeoTIFF en el mapa
    const loadGeoTIFF = async () => {
      console.log("🧩 Parámetros recibidos:", zona, valor, fecha);

      try {
        // Construir la URL según si queremos el promedio o la capa mensual
        const url = verPromedio
          ? `http://localhost:5000/api/promedio-riesgo-zona?zona=${zona}&valor=${valor}`
          : `http://localhost:5000/api/riesgo-geotiff?zona=${zona}&valor=${valor}&fecha=${fecha}`;

        // Solicitar el GeoTIFF al backend  
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error("No se pudo cargar el archivo GeoTIFF");
        }

        // Leer el ArrayBuffer y convertirlo a GeoRaster
        const arrayBuffer = await response.arrayBuffer();
        const raster = await georaster(arrayBuffer);

        console.log("📏 pixelWidth:", raster.pixelWidth);
        console.log("📏 pixelHeight:", raster.pixelHeight);
        console.log("🧭 projection:", raster.projection);

        // Si el mapa no existe, inicializarlo con configuración base
        if (!mapRef.current) {
          mapRef.current = L.map("map", {
            zoomControl: true,
            maxZoom: 13,
            minZoom: 4,
          }).setView([-30, -70], 5);

          // Capa base de OpenStreetMap
          L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "© OpenStreetMap contributors",
          }).addTo(mapRef.current);
        } else {
          // Si ya existe el mapa, eliminar capas anteriores (salvo la base)
          mapRef.current.eachLayer((layer) => {
            if (!(layer instanceof L.TileLayer)) {
              mapRef.current.removeLayer(layer);
            }
          });
        }

        // Crear y añadir la capa raster del GeoTIFF con una función de color (gradiente azul→rojo)
        const layer = new GeoRasterLayer({
          georaster: raster,
          opacity: 0.8,
          resolution: 256,
          pixelValuesToColorFn: (val) => {
            if (val === null || isNaN(val)) return null;
            if (val < 0.1) return "#08306b";     // azul muy oscuro
            if (val < 0.2) return "#2171b5";     // azul medio
            if (val < 0.3) return "#6baed6";     // celeste
            if (val < 0.4) return "#bae4b3";     // verde muy claro
            if (val < 0.5) return "#ffffcc";     // amarillo muy claro
            if (val < 0.6) return "#fed976";     // amarillo
            if (val < 0.7) return "#feb24c";     // naranja claro
            if (val < 0.8) return "#fd8d3c";     // naranja
            if (val < 0.9) return "#fc4e2a";     // rojo claro
            if (val <= 1.0) return "#bd0026";    // rojo intenso
            return null;
          },
        });
        layer.addTo(mapRef.current);

        // Construir parámetro de zona para la petición GeoJSON
        const zonaParam =
          zona === "comuna"
            ? `comuna=${valor}`
            : zona === "provincia"
            ? `provincia=${valor}`
            : zona === "region"
            ? `region=${valor}`
            : "";

        // Cargar el GeoJSON que define el contorno de la zona
        const geojsonRes = await fetch(`http://localhost:5000/api/geojson?${zonaParam}`);
        const geojson = await geojsonRes.json();

        // Añadir la capa GeoJSON al mapa (solo contorno, sin relleno)
        const zonaLayer = L.geoJSON(geojson, {
          style: {
            color: "#3f3f40",
            weight: 0.8,
            fillOpacity: 0,
          },
        }).addTo(mapRef.current);

        // Ajustar el zoom para encuadrar la zona seleccionada
        const bounds = zonaLayer.getBounds();
        if (bounds.isValid()) {
          mapRef.current.fitBounds(bounds, {
            padding: [20, 20],
            maxZoom: 10,
            animate: true,
          });
        }

      } catch (error) {
        console.error("❌ Error al cargar el mapa o la zona:", error);
      }
    };

    // Ejecutar la carga sólo si tenemos zona/valor y (fecha o promedio)
    if (zona && valor && (fecha || verPromedio)) {
      loadGeoTIFF();
    }
  }, [zona, valor, fecha, verPromedio]);

  return (
    <div style={{ position: "relative" }}>
      <div style={{ marginBottom: "10px" }}>
        <label>
          <input
            type="checkbox"
            checked={verPromedio}
            onChange={() => setVerPromedio(!verPromedio)}
          />
          Ver promedio últimos 2 años
        </label>
      </div>

      <div
        id="map"
        style={{ height: "600px", width: "100%", marginTop: "1rem" }}
      ></div>

      <div className="leyenda-mapa">
        <h4>Riesgo Hídrico</h4>
        <div><span style={{ background: "#08306b" }}></span> 0.0 – 0.1</div>
        <div><span style={{ background: "#2171b5" }}></span> 0.1 – 0.2</div>
        <div><span style={{ background: "#6baed6" }}></span> 0.2 – 0.3</div>
        <div><span style={{ background: "#bae4b3" }}></span> 0.3 – 0.4</div>
        <div><span style={{ background: "#ffffcc" }}></span> 0.4 – 0.5</div>
        <div><span style={{ background: "#fed976" }}></span> 0.5 – 0.6</div>
        <div><span style={{ background: "#feb24c" }}></span> 0.6 – 0.7</div>
        <div><span style={{ background: "#fd8d3c" }}></span> 0.7 – 0.8</div>
        <div><span style={{ background: "#fc4e2a" }}></span> 0.8 – 0.9</div>
        <div><span style={{ background: "#bd0026" }}></span> 0.9 – 1.0</div>
      </div>
    </div>
  );
}

export default MapaImagen;
