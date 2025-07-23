import React, { useEffect, useState, useRef, useMemo } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import GeoRasterLayer from "georaster-layer-for-leaflet";
import georaster from "georaster";

const API_BASE = "http://localhost:5000";

// Paleta de 10 colores
const colorRamp = [
  "#08306b", "#2171b5", "#6baed6", "#bae4b3", "#ffffcc",
  "#fed976", "#feb24c", "#fd8d3c", "#fc4e2a", "#bd0026"
];

export default function MapaImagen({ tipo, zona, valor, fecha }) {
  const [verPromedio, setVerPromedio] = useState(false);

  // Cada entry en mapRefs.current es { map: LeafletMap, legend: Control }
  const mapRefs = useRef({});

  // ——— 1) Limpieza cuando cambie el tipo de mapa ———
  useEffect(() => {
    // Al cambiar 'tipo', destruimos TODOS los mapas previos
    Object.values(mapRefs.current).forEach(({ map, legend }) => {
      if (legend) map.removeControl(legend);
      map.remove();
    });
    mapRefs.current = {};
  }, [tipo]);

  // ——— 2) Función de color estándar (0–1) ———
  const pixelValuesToColorFn = val => {
    if (val == null || isNaN(val)) return null;
    const idx = Math.floor(val * 10);
    return colorRamp[Math.min(Math.max(idx, 0), 9)];
  };

  // ——— 3) Preparo array de capas según tipo y verPromedio ———
  const capas = useMemo(() => {
    const enc = encodeURIComponent;
    const urls = [];

    switch (tipo) {
      case "riesgo":
        if (verPromedio) {
          urls.push({ 
            key: "normal", 
            url: `${API_BASE}/api/promedio-riesgo-raw-zona?zona=${zona}&valor=${enc(valor)}` 
          });
          urls.push({
            key: "fuzzy",  
            url: `${API_BASE}/api/promedio-riesgo-fuzzy-zona?zona=${zona}&valor=${enc(valor)}` 
          });
        } else {
          urls.push({
            key: "normal",
            url: `${API_BASE}/api/riesgo-raw-geotiff?zona=${zona}&valor=${enc(valor)}&fecha=${fecha}`
          });
          urls.push({
            key: "fuzzy",
            url: `${API_BASE}/api/riesgo-fuzzy-geotiff?zona=${zona}&valor=${enc(valor)}&fecha=${fecha}`
          });
        }
        break;

      case "precipitacion":
        urls.push({
          key: "normal",
          url: `${API_BASE}/api/precipitacion-geotiff?zona=${zona}&valor=${enc(valor)}&fecha=${fecha}`
        });
        urls.push({
          key: "baja",
          url: `${API_BASE}/api/precipitacion-baja-fuzzy-geotiff?zona=${zona}&valor=${enc(valor)}&fecha=${fecha}`
        });
        urls.push({
          key: "media",
          url: `${API_BASE}/api/precipitacion-media-fuzzy-geotiff?zona=${zona}&valor=${enc(valor)}&fecha=${fecha}`
        });
        urls.push({
          key: "alta",
          url: `${API_BASE}/api/precipitacion-alta-fuzzy-geotiff?zona=${zona}&valor=${enc(valor)}&fecha=${fecha}`
        });
        break;

      case "temperatura":
        urls.push({
          key: "normal",
          url: `${API_BASE}/api/temperatura-geotiff?zona=${zona}&valor=${enc(valor)}&fecha=${fecha}`
        });
        urls.push({
          key: "baja",
          url: `${API_BASE}/api/temperatura-baja-fuzzy-geotiff?zona=${zona}&valor=${enc(valor)}&fecha=${fecha}`
        });
        urls.push({
          key: "media",
          url: `${API_BASE}/api/temperatura-media-fuzzy-geotiff?zona=${zona}&valor=${enc(valor)}&fecha=${fecha}`
        });
        urls.push({
          key: "alta",
          url: `${API_BASE}/api/temperatura-alta-fuzzy-geotiff?zona=${zona}&valor=${enc(valor)}&fecha=${fecha}`
        });
        break;

      default:
        console.error(`Tipo de mapa desconocido: ${tipo}`);
    }

    return urls;
  }, [tipo, zona, valor, fecha, verPromedio]);

  // ——— 4) Mapas de etiqueta por key ———
  const labelMap = useMemo(() => {
    if (tipo === "riesgo") {
      return { normal: "Riesgo crudo", fuzzy: "Riesgo fuzzy" };
    }
    if (tipo === "precipitacion") {
      return {
        normal: "Precipitación (mm)",
        baja:   "GP a Prec. Baja",
        media:  "GP a Prec. Media",
        alta:   "GP a Prec. Alta"
      };
    }
    if (tipo === "temperatura") {
      return {
        normal: "Temperatura (°C)",
        baja:   "GP a Temp. Baja",
        media:  "GP a Temp. Media",
        alta:   "GP a Temp. Alta"
      };
    }
    return {};
  }, [tipo]);

  // ——— 5) Efecto para inicializar o actualizar cada capa ———
  useEffect(() => {
    if (!capas.length) return;

    const initMapa = async ({ key, url }) => {
      // fetch + parse
      const res = await fetch(url);
      if (!res.ok) throw new Error(`No se pudo cargar ${url}`);
      const buf = await res.arrayBuffer();
      const raster = await georaster(buf);

      // elegir colorFn
      let colorFn = pixelValuesToColorFn;
      if (key === "normal" && tipo !== "riesgo") {
        // escala de min/max
        const min = raster.mins[0], max = raster.maxs[0];
        colorFn = v => {
          if (v == null || isNaN(v)) return null;
          const t = (v - min) / (max - min),
                idx = Math.floor(t * 10);
          return colorRamp[Math.min(Math.max(idx, 0), 9)];
        };
      }

      // init o limpiar mapa + leyenda
      let entry = mapRefs.current[key];
      if (!entry) {
        const map = L.map(`map-${key}`, { zoomControl: true, maxZoom: 13, minZoom: 4 })
                     .setView([-30, -70], 5);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: "© OpenStreetMap contributors"
        }).addTo(map);
        entry = mapRefs.current[key] = { map, legend: null };
      } else {
        entry.map.eachLayer(l => {
          if (!(l instanceof L.TileLayer)) entry.map.removeLayer(l);
        });
      }

      // capa raster
      new GeoRasterLayer({
        georaster:            raster,
        opacity:              0.8,
        resolution:           256,
        pixelValuesToColorFn: colorFn
      }).addTo(entry.map);

      // contorno
      const zonaParam =
        zona === "comuna"
          ? `comuna=${encodeURIComponent(valor)}`
          : zona === "provincia"
          ? `provincia=${encodeURIComponent(valor)}`
          : `region=${encodeURIComponent(valor)}`;
      const gj = await fetch(`${API_BASE}/api/geojson?${zonaParam}`).then(r => r.json());
      const zoneLayer = L.geoJSON(gj, {
        style: { color: "#3f3f40", weight: 0.8, fillOpacity: 0 }
      }).addTo(entry.map);
      if (zoneLayer.getBounds().isValid()) {
        entry.map.fitBounds(zoneLayer.getBounds(), { padding:[20,20], maxZoom:10 });
      }

      // limpiar leyenda anterior
      if (entry.legend) {
        entry.map.removeControl(entry.legend);
        entry.legend = null;
      }

      // nueva leyenda incrustada
      const legend = L.control({ position: "bottomright" });
      legend.onAdd = () => {
        const div = L.DomUtil.create("div", "info legend");
        Object.assign(div.style, {
          background:   "rgba(255,255,255,0.8)",
          padding:      "6px",
          borderRadius: "4px",
          boxShadow:    "0 0 15px rgba(0,0,0,0.2)",
          lineHeight:   "1.2em",
          fontSize:     "0.9em"
        });
        div.innerHTML = `<strong style="display:block; text-align:center; margin-bottom:4px;">
                           ${labelMap[key]}
                         </strong>`;

        if (key === "normal" && tipo === "precipitacion") {
          const min = raster.mins[0], max = raster.maxs[0], step = (max-min)/10;
          for (let i=0; i<10; i++) {
            const f = (min+step*i).toFixed(1),
                  t = (min+step*(i+1)).toFixed(1);
            div.innerHTML +=
              `<i style="
                 background:${colorRamp[i]};
                 width:18px;height:8px;
                 display:inline-block;
                 margin-right:4px;
               "></i>${f}–${t} mm<br>`;
          }
        }
        else if (key === "normal" && tipo === "temperatura") {
          const min = raster.mins[0], max = raster.maxs[0], step = (max-min)/10;
          for (let i=0; i<10; i++) {
            const f = (min+step*i).toFixed(1),
                  t = (min+step*(i+1)).toFixed(1);
            div.innerHTML +=
              `<i style="
                 background:${colorRamp[i]};
                 width:18px;height:8px;
                 display:inline-block;
                 margin-right:4px;
               "></i>${f}–${t} °C<br>`;
          }
        }
        else {
          for (let i=0; i<10; i++) {
            const f = (i/10).toFixed(1),
                  t = ((i+1)/10).toFixed(1);
            div.innerHTML +=
              `<i style="
                 background:${colorRamp[i]};
                 width:18px;height:8px;
                 display:inline-block;
                 margin-right:4px;
               "></i>${f}–${t}<br>`;
          }
        }
        return div;
      };
      legend.addTo(entry.map);
      entry.legend = legend;
    };

    capas.forEach(c =>
      initMapa(c).catch(err => console.error(`Error capa ${c.key}:`, err))
    );
  }, [capas, tipo, zona, valor]);

  return (
    <div>
      {tipo === "riesgo" && (
        <div style={{ marginBottom: 10 }}>
          <label>
            <input
              type="checkbox"
              checked={verPromedio}
              onChange={() => setVerPromedio(v => !v)}
            />{" "}
            Ver promedio últimos 2 años
          </label>
        </div>
      )}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem" }}>
        {capas.map(({ key }) => (
          <div
            key={key}
            id={`map-${key}`}
            style={{
              flex: tipo === "riesgo" ? 1 : "1 1 calc(50% - .5rem)",
              height: "400px",
              border: "1px solid #ddd"
            }}
          />
        ))}
      </div>
    </div>
  );
}
