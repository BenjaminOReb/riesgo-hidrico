import React, { useState, useEffect } from "react";
import ReactDOM from "react-dom";
import ReactApexChart from "react-apexcharts";

export default function LinguisticModal({ isOpen, onClose, fetchUrl, title }) {
  // Inferimos la unidad en cada render
  const isTemp = /temperatura/i.test(fetchUrl);
  const unit   = isTemp ? " °C" : " mm";

  const [series, setSeries] = useState([]);
  const [options, setOptions] = useState({
    chart: { type: "line", toolbar: { show: false } },
    title: { show: false },
    xaxis: {
      type: "numeric",
      tickAmount: 5,
      labels: { formatter: val => `${val.toFixed(2)}${unit}` },
      title: { text: "Unidad de medida" }
    },
    yaxis: {
      title: { text: "Grados de pertenencia" },
      min: 0, max: 1, tickAmount: 5,
      labels: { formatter: v => v.toFixed(2) }
    },
    stroke: { curve: "straight", width: 4 },
    markers: { size: 0 },
    legend: { position: "top" },
    tooltip: {
      x: { formatter: val => `${val.toFixed(2)}${unit}` },
      y: { formatter: v => v.toFixed(2) }
    }
  });

  // 1) Si cambia la unidad (i.e. fetchUrl), actualizamos los formatters
  useEffect(() => {
    if (!isOpen) return;
    setOptions(o => ({
      ...o,
      xaxis: {
        ...o.xaxis,
        labels: { formatter: val => `${val.toFixed(2)}${unit}` }
      },
      tooltip: {
        ...o.tooltip,
        x: { formatter: val => `${val.toFixed(2)}${unit}` }
      }
    }));
  }, [unit, isOpen]);

  // 2) Efecto de carga de datos (igual que antes), pero ahora options ya escucha unit
  useEffect(() => {
    if (!isOpen) return;
    fetch(fetchUrl)
      .then(res => {
        if (!res.ok) return res.json().then(e => { throw new Error(e.error) });
        return res.json();
      })
      .then(({ categories, baja, media, alta }) => {
        setSeries([
          { name: "Baja",  data: categories.map((c,i) => [c, baja[i]]) },
          { name: "Media", data: categories.map((c,i) => [c, media[i]]) },
          { name: "Alta",  data: categories.map((c,i) => [c, alta[i]]) }
        ]);
        setOptions(o => ({
          ...o,
          xaxis: {
            ...o.xaxis,
            min: categories[0],
            max: categories[categories.length-1]
          }
        }));
      })
      .catch(err => console.error("Error stats fuzzy:", err.message));
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
