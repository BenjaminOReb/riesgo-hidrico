import React, { useState, useEffect } from "react";
import ReactDOM from "react-dom";
import ReactApexChart from "react-apexcharts";

export default function LinguisticModal({ isOpen, onClose, fetchUrl, title, isTemp }) {
  // Inferimos la unidad en cada render
  const unit   = isTemp ? " °C" : " mm";

  const [series, setSeries] = useState([]);
  const [options, setOptions] = useState({
    chart: { type: "line", toolbar: { show: false } },
    colors: ["#08306b", "#feb24c", "#bd0026"],
    title: { show: false },
    xaxis: {
      type: "numeric",
      tickAmount: 5,
      labels: { formatter: val => `${val.toFixed(2)}${unit}`},
      title: { text: "Unidad de medida" }
    },
    yaxis: {
      title: { text: "Grados de pertenencia" },
      min: 0, max: 1, tickAmount: 5,
      labels: { formatter: v => v.toFixed(2), }
    },
    stroke: { curve: "straight", width: 4 },
    markers: { size: 0 },
    legend: { position: "top",
              horizontalAlign: "center",
              fontSize: "25px", // más grande
              markers: { width: 16, height: 16 } },
    tooltip: {
      x: { formatter: val => `${val.toFixed(2)}${unit}` },
      y: { formatter: v => v.toFixed(2) }
    }
  });

  const letters = ["a","b","c","d"];

  useEffect(() => {
    if (!isOpen) return;

    fetch(fetchUrl)
      .then(res => {
        if (!res.ok) return res.json().then(e => { throw new Error(e.error) });
        return res.json();
      })
      .then(({ categories, baja, media, alta }) => {
        // 1) Computar índices a, b, c, d
        const computeABCD = arr => {
          const eps = 1e-6;
          const aIdx = arr.findIndex(v => v > eps);
          const dIdx = arr.length - 1 - [...arr].reverse().findIndex(v => v > eps);
          const bIdx = arr.findIndex(v => v >= 1 - eps);
          const cIdx = arr.length - 1 - [...arr].reverse().findIndex(v => v >= 1 - eps);
          return [aIdx, bIdx, cIdx, dIdx];
        };
        const lowIdxs  = computeABCD(baja);
        const medIdxs  = computeABCD(media);
        const highIdxs = computeABCD(alta);

        // 2) Generar annotations y marcadores discretos con offset
        const annotations = [];
        const discreteMarkers = [];

        [[lowIdxs, "#08306b"], [medIdxs, "#feb24c"], [highIdxs, "#bd0026"]]
          .forEach(([idxs, color], seriesIndex) => {
            idxs.forEach((dpIdx, i) => {
              const x = categories[dpIdx];
              // desplazamiento vertical según la posición en [a,b,c,d]
              const offsetY = (i *40) + 30;

              annotations.push({
                x,
                borderColor: color,
                strokeDashArray: 4,
                label: {
                  text: `${letters[i]}=${x.toFixed(2)}${unit}`,
                  style: { color, background: "#fff", fontSize: "21px" },
                  orientation: "horizontal",
                  position: "top",
                  offsetY
                }
              });

              discreteMarkers.push({
                seriesIndex,
                dataPointIndex: dpIdx,
                fillColor: color,
                strokeColor: color,
                size: 6
              });
            });
          });

        // 3) Fijar series y actualizar opciones
        setSeries([
          { name: "Baja",  data: categories.map((c, i) => [c, baja[i]]) },
          { name: "Media", data: categories.map((c, i) => [c, media[i]]) },
          { name: "Alta",  data: categories.map((c, i) => [c, alta[i]]) }
        ]);

        setOptions(o => ({
          ...o,
          xaxis: {
            ...o.xaxis,
            min: categories[0],
            max: categories[categories.length - 1]
          },
          annotations: { xaxis: annotations },
          markers: { ...o.markers, discrete: discreteMarkers }
        }));
      })
      .catch(err => console.error("Error stats fuzzy:", err.message));
  }, [isOpen, fetchUrl, unit]);

  if (!isOpen) return null;

  return ReactDOM.createPortal(
    <div className="modal-overlay">
      <div
        className="modal-content"
        style={{
          maxWidth: '90vw',
          width: '1060px',
          padding: '1rem'
        }}
      >
        <button className="modal-close" onClick={onClose}>✕</button>
        <h2 style={{ textAlign: 'center' }}>
          {title.charAt(0).toUpperCase() + title.slice(1)}
        </h2>
        <ReactApexChart
          options={options}
          series={series}
          type="line"
          height={540}
          width="100%"
        />
      </div>
    </div>,
    document.body
  );
}
