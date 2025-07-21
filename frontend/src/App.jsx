import { useState } from 'react';
import FileUpload from './components/FileUpload';
import ZonaSelector from './components/ZonaSelector';
import FechaSelector from './components/FechaSelector';
import MapaImagen from './components/MapaImagen';

import EscudoUbb from './assets/escudo-monocromatico-oscuro.png';
import LogoFace from './assets/logo-FACE-oscuro.png';

import './App.css';

function App() {
  const [zonaSeleccionada, setZonaSeleccionada]   = useState(null);
  const [valorSeleccionado, setValorSeleccionado] = useState(null);
  const [fechaSeleccionada, setFechaSeleccionada] = useState('');
  const [tipoSeleccionado, setTipoSeleccionado]   = useState('riesgo');
  const [reloadDates, setReloadDates]             = useState(0);

  const manejarSeleccionZona = ({ zona, valor }) => {
    setZonaSeleccionada(zona);
    setValorSeleccionado(valor);
  };

  const manejarCambioFecha = (nuevaFecha) => {
    setFechaSeleccionada(nuevaFecha);
  };

  const handleUploadSuccess = () => {
    setReloadDates(n => n + 1);
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <img src={EscudoUbb} alt="Escudo UBB" className="logo-ubb" />
        <h1>Proyecto riesgo Hídrico</h1>
        <img src={LogoFace} alt="Facultad FACE" className="logo-face" />
      </header>

      <main>
        <section className="controls">
          {/* Subida de archivos */}
          <FileUpload onUploadSuccess={handleUploadSuccess} />

          {/* Selector de tipo de mapa */}
          <div className="control">
            <label htmlFor="tipo-select">Tipo de mapa:</label>
            <select
              id="tipo-select"
              value={tipoSeleccionado}
              onChange={e => setTipoSeleccionado(e.target.value)}
            >
              <option value="precipitacion">Precipitación</option>
              <option value="temperatura">Temperatura</option>
              <option value="riesgo">Riesgo</option>
            </select>
          </div>

          {/* Selector de zona geográfica */}
          <ZonaSelector onSeleccionar={manejarSeleccionZona} />

          {/* Selector de fecha */}
          <FechaSelector
            reloadFlag={reloadDates}
            value={fechaSeleccionada}
            onSeleccionar={manejarCambioFecha}
          />
        </section>

        {/* Mostrar los dos mapas (normal y fuzzy) una vez estén todos los parámetros */}
        {zonaSeleccionada && valorSeleccionado && fechaSeleccionada && (
          <MapaImagen
            tipo={tipoSeleccionado}
            zona={zonaSeleccionada}
            valor={valorSeleccionado}
            fecha={fechaSeleccionada}
          />
        )}
      </main>

      <footer className="app-footer">
        © {new Date().getFullYear()} Benjamín Ortega Rebolledo — Universidad del Bío-Bío — Facultad de Ciencias Empresariales
      </footer>
    </div>
  );
}

export default App;
