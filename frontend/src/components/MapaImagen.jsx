import React, { useEffect, useState, useRef, useMemo } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import GeoRasterLayer from "georaster-layer-for-leaflet";
import georaster from "georaster";
import LinguisticModal from "./LinguisticModal";

const API_BASE = "http://localhost:5000";

// Paleta de 10 colores
const colorRamp = [
  "#08306b", "#2171b5", "#6baed6", "#bae4b3", "#ffffcc",
  "#fed976", "#feb24c", "#fd8d3c", "#fc4e2a", "#bd0026"
];

export default function MapaImagen({ tipo, zona, valor, fecha }) {
  const [verPromedio, setVerPromedio] = useState(false);
  const [modalOpen,  setModalOpen]  = useState(false);
  const mapRefs = useRef({}); // { key: { map, legend } }

  // 1) Limpiar mapas cuando cambie el tipo
  useEffect(() => {
    Object.values(mapRefs.current).forEach(({ map, legend }) => {
      legend && map.removeControl(legend);
      map.remove();
    });
    mapRefs.current = {};
  }, [tipo]);

  // 2) Colorfn genérico 0–1
  const pixelValuesToColorFn = v => {
    if (v == null || isNaN(v)) return null;
    return colorRamp[Math.min(9, Math.floor(v*10))];
  };

  // 3) URLs de capas
  const capas = useMemo(() => {
    const enc = encodeURIComponent;
    const urls = [];
    if (tipo === "riesgo") {
      if (verPromedio) {
        urls.push({ key:"normal", url:`${API_BASE}/api/promedio-riesgo-crisp-zona?zona=${zona}&valor=${enc(valor)}` });
        urls.push({ key:"fuzzy",  url:`${API_BASE}/api/promedio-riesgo-fuzzy-zona?zona=${zona}&valor=${enc(valor)}` });
      } else {
        urls.push({ key:"normal", url:`${API_BASE}/api/riesgo-crisp-geotiff?zona=${zona}&valor=${enc(valor)}&fecha=${fecha}` });
        urls.push({ key:"fuzzy",  url:`${API_BASE}/api/riesgo-fuzzy-geotiff?zona=${zona}&valor=${enc(valor)}&fecha=${fecha}` });
      }
    }
    if (tipo === "precipitacion"|| tipo==="temperatura") {
      const base = tipo==="precipitacion"? "precipitacion" : "temperatura";
      urls.push({ key:"normal", url:`${API_BASE}/api/${base}-geotiff?zona=${zona}&valor=${enc(valor)}&fecha=${fecha}` });
      ["baja","media","alta"].forEach(level => {
        urls.push({
          key: level,
          url: `${API_BASE}/api/${base}-${level}-fuzzy-geotiff?zona=${zona}&valor=${enc(valor)}&fecha=${fecha}`
        });
      });
    }
    return urls;
  }, [tipo, zona, valor, fecha, verPromedio]);

  // 4) Etiquetas
  const labelMap = useMemo(() => {
    if (tipo === "riesgo") return { normal:"Riesgo crisp", fuzzy:"Riesgo fuzzy" };
    if (tipo === "precipitacion") return {
      normal:"Precipitación (mm)",
      baja:  "GP Prec. Baja",
      media: "GP Prec. Media",
      alta:  "GP Prec. Alta"
    };
    if (tipo === "temperatura") return {
      normal:"Temperatura (°C)",
      baja:  "GP Temp. Baja",
      media: "GP Temp. Media",
      alta:  "GP Temp. Alta"
    };
    return {};
  }, [tipo]);

  // 5) Renderizar cada capa
  useEffect(() => {
    if (!capas.length) return;

    capas.forEach(({ key, url }) => {
      (async () => {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`No se pudo cargar ${url}`);
        const buf = await res.arrayBuffer();
        const raster = await georaster(buf);

        // colorfn dinámico si no es riesgo crisp
        let colorFn = pixelValuesToColorFn;
        if (key==="normal" && tipo!=="riesgo") {
          const [min,max] = [raster.mins[0], raster.maxs[0]];
          colorFn = v => {
            if (v==null||isNaN(v)) return null;
            return colorRamp[Math.min(9,Math.floor((v-min)/(max-min)*10))];
          };
        }

        // init / limpiar mapa
        let entry = mapRefs.current[key];
        if (!entry) {
          const map = L.map(`map-${key}`, { zoomControl:true, maxZoom:13, minZoom:4 })
                     .setView([-30,-70],5);
          L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "© OpenStreetMap contributors"
          }).addTo(map);
          entry = mapRefs.current[key] = { map, legend:null };
        } else {
          entry.map.eachLayer(l => { if (!(l instanceof L.TileLayer)) entry.map.removeLayer(l) });
        }

        // añadir raster
        new GeoRasterLayer({
          georaster:            raster,
          opacity:              0.8,
          resolution:           64,
          pixelValuesToColorFn: colorFn
        }).addTo(entry.map);

        // Parámetro geojson según zona
        const zonaParam =
          zona==="pais"      ? `pais=${encodeURIComponent(valor)}` :
          zona==="norte"     ? `norte=${encodeURIComponent(valor)}` :
          zona==="centro"    ? `centro=${encodeURIComponent(valor)}` :
          zona==="sur"       ? `sur=${encodeURIComponent(valor)}` :
          zona==="comuna"    ? `comuna=${encodeURIComponent(valor)}` :
          zona==="provincia"? `provincia=${encodeURIComponent(valor)}` :
                              `region=${encodeURIComponent(valor)}`;

        // fetch geojson y dibujar contorno
        const gj = await fetch(`${API_BASE}/api/geojson?${zonaParam}`).then(r=>r.json());
        const zoneLayer = L.geoJSON(gj, {
          style:{ color:"#3f3f40", weight:0.8, fillOpacity:0 }
        }).addTo(entry.map);
        if (zoneLayer.getBounds().isValid()) {
          entry.map.fitBounds(zoneLayer.getBounds(), { padding:[20,20], maxZoom:10 });
        }

        // leyenda
        if (entry.legend) { entry.map.removeControl(entry.legend); entry.legend=null; }
        const legend = L.control({ position:"bottomright" });
        legend.onAdd = () => {
          const div = L.DomUtil.create("div","info legend");
          Object.assign(div.style,{
            background:"rgba(255,255,255,0.8)",
            padding:"6px",
            borderRadius:"4px",
            boxShadow:"0 0 15px rgba(0,0,0,0.2)",
            lineHeight:"1.2em",
            fontSize:"0.9em"
          });
          div.innerHTML = `<strong style="display:block;text-align:center;margin-bottom:4px;">
                             ${labelMap[key]}
                           </strong>`;
          if (key==="normal" && tipo==="precipitacion") {
            const [min,max] = [raster.mins[0], raster.maxs[0]];
            const step = (max-min)/10;
            for (let i=0;i<10;i++){
              const f=(min+step*i).toFixed(1),
                    t=(min+step*(i+1)).toFixed(1);
              div.innerHTML +=
                `<i style="background:${colorRamp[i]};width:18px;height:8px;display:inline-block;margin-right:4px"></i>
                 ${f}–${t} mm<br>`;
            }
          }
          else if (key==="normal" && tipo==="temperatura") {
            const [min,max] = [raster.mins[0], raster.maxs[0]];
            const step = (max-min)/10;
            for (let i=0;i<10;i++){
              const f=(min+step*i).toFixed(1),
                    t=(min+step*(i+1)).toFixed(1);
              div.innerHTML +=
                `<i style="background:${colorRamp[i]};width:18px;height:8px;display:inline-block;margin-right:4px"></i>
                 ${f}–${t} °C<br>`;
            }
          }
          else {
            for (let i=0;i<10;i++){
              const f=(i/10).toFixed(1),
                    t=((i+1)/10).toFixed(1);
              div.innerHTML +=
                `<i style="background:${colorRamp[i]};width:18px;height:8px;display:inline-block;margin-right:4px"></i>
                 ${f}–${t}<br>`;
            }
          }
          return div;
        };
        legend.addTo(entry.map);
        entry.legend = legend;

      })().catch(err => console.error(`Error capa ${key}:`, err));
    });
  }, [capas, tipo, zona, valor]);

  // 6) Botón de stats fuzzy
  const showFuzzy = tipo==="precipitacion"||tipo==="temperatura";
  const statsUrl = `${API_BASE}/api/${
    tipo==="precipitacion"?"precipitacion":"temperatura"
  }-fuzzy-stats?zona=${zona}&valor=${encodeURIComponent(valor)}&fecha=${fecha}`;

  return (
    <div>
      {tipo==="riesgo" && (
        <div style={{ marginBottom:10 }}>
          <label>
            <input
              type="checkbox"
              checked={verPromedio}
              onChange={()=>setVerPromedio(v=>!v)}
            />{' '}
            Ver promedio últimos 2 años
          </label>
        </div>
      )}

      <div style={{
        display:   "flex",
        flexWrap:  "nowrap",
        gap:       "0.5rem",
        overflowX: "auto"
      }}>
        {capas.map(({ key })=>(
          <div
            key={key}
            id={`map-${key}`}
            style={{
              flex:      "1 1 calc(25% - 0.5rem)",
              minWidth:  "200px",
              height:    "650px",
              border:    "1px solid #ddd",
              boxSizing: "border-box"
            }}
          />
        ))}
      </div>

      {showFuzzy && (
        <div className="mt-4 text-center">
          <button
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            onClick={()=>setModalOpen(true)}
          >
            Ver variables lingüísticas
          </button>
        </div>
      )}

      <LinguisticModal
        key={tipo /* o key={unit} */}
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        fetchUrl={statsUrl}
        isTemp={tipo === "temperatura"}
        title={`${tipo === "precipitacion" ? "Precipitación" : "Temperatura"} — ${valor} (${fecha})`}
      />
    </div>
  );
}
