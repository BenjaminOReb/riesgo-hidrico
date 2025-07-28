import React, { useState, useEffect } from "react";
import ReactDOM from "react-dom";
import ReactApexChart from "react-apexcharts";

export default function LinguisticModal({ isOpen, onClose, fetchUrl, title }) {
  const isTemp = fetchUrl.includes("temperatura");
  const unit   = isTemp ? "°C" : "mm";

  const [series, setSeries] = useState([]);
  const [options, setOptions] = useState({
    chart: {
      type: "line",
      toolbar: { show: false }
    },
    title: { show: false },
    xaxis: {
      title: {
        text: "Unidad de Medida",
        style: { fontSize: "0.9em", fontWeight: 500 }
      },
      type: "numeric",
      tickAmount: 5,
      labels: {
        formatter: (val) => `${val.toFixed(2)}${unit}`
      }
    },
    yaxis: {
      title: {
        text: "Grados de pertenencia",
        style: { fontSize: "0.9em", fontWeight: 500 }
      },
      min: 0,
      max: 1,
      tickAmount: 5,
      labels: {
        formatter: (v) => v.toFixed(2)
      }
    },
    stroke: { curve: "straight", width: 4 },
    markers: { size: 0 },
    legend: { position: "top" },
    tooltip: {
      x: { formatter: (val) => `${val.toFixed(2)}${unit}` },
      y: { formatter: (val) => val.toFixed(2) }
    }
  });

  useEffect(() => {
    if (!isOpen) return;

    fetch(fetchUrl)
      .then((res) => {
        if (!res.ok) return res.json().then((err) => { throw new Error(err.error); });
        return res.json();
      })
      .then(({ categories, baja, media, alta }) => {
        const s = [
          { name: "Baja",  data: categories.map((c, i) => [c, baja[i]]) },
          { name: "Media", data: categories.map((c, i) => [c, media[i]]) },
          { name: "Alta",  data: categories.map((c, i) => [c, alta[i]]) }
        ];
        setSeries(s);
        setOptions(o => ({
          ...o,
          xaxis: {
            ...o.xaxis,
            min: categories[0],
            max: categories[categories.length - 1]
          }
        }));
      })
      .catch((err) => {
        console.error("Error cargando stats fuzzy:", err.message);
      });
  }, [isOpen, fetchUrl]);

  if (!isOpen) return null;

  return ReactDOM.createPortal(
    <div className="modal-overlay">
      <div className="modal-content">
        <button className="modal-close" onClick={onClose}>✕</button>
        <h2>{title.charAt(0).toUpperCase() + title.slice(1)}</h2>
        <ReactApexChart options={options} series={series} type="line" height={350} />
      </div>
    </div>,
    document.body
  );
}
