import { useState } from 'react';
import FileUpload from './components/FileUpload';
import ZonaSelector from './components/ZonaSelector';
import FechaSelector from './components/FechaSelector';
import MapaImagen from './components/MapaImagen';

import EscudoUbb from './assets/escudo-monocromatico-oscuro.png';
import LogoFace from './assets/logo-FACE-oscuro.png';

import './App.css';

/*
 * Componente principal de la aplicación.
 * Gestiona el estado global: selección de zona, valor y fecha.
 * Renderiza la cabecera con logotipos, los controles de carga/selección,
 * el mapa (cuando haya una zona seleccionada) y el pie de página.
 */

function App() {
  // Estado para el nivel de zona seleccionada ('comuna', 'provincia' o 'region')
  const [zonaSeleccionada, setZonaSeleccionada] = useState(null);
  // Estado para el nombre concreto de la zona (por ejemplo, 'Los Alamos')
  const [valorSeleccionado, setValorSeleccionado] = useState(null);
  // Estado para la fecha mes-año seleccionada (por defecto '2019-05')
  const [fechaSeleccionada, setFechaSeleccionada] = useState('2019-05');
  
  /*
   * Callback que recibe la selección de zona desde ZonaSelector.
   * Actualiza el estado local con la zona y el valor elegidos.
   */
  const manejarSeleccionZona = ({ zona, valor }) => {
    setZonaSeleccionada(zona);
    setValorSeleccionado(valor);
  };

  /*
   * Callback que recibe la selección de fecha desde FechaSelector.
   * Actualiza el estado local con la nueva fecha.
   */
  const manejarCambioFecha = (nuevaFecha) => {
    setFechaSeleccionada(nuevaFecha);
  };

  return (
    <div className="app-container">
      {/* —–––––––––––––––––––––––––––––––––––––––––––––––– */}
      {/* Cabecera con logotipos e título */}
      {/* —–––––––––––––––––––––––––––––––––––––––––––––––– */}
      <header className="app-header">
        <img src={EscudoUbb} alt="Escudo UBB" className="logo-ubb" />
        <h1>🌧️ Proyecto Riesgo Hídrico</h1>
        <img src={LogoFace} alt="Facultad FACE" className="logo-face" />
      </header>


      {/* —–––––––––––––––––––––––––––––––––––––––––––––––– */}
      {/* Sección principal */}
      {/* —–––––––––––––––––––––––––––––––––––––––––––––––– */}
      <main>
        {/* Controles de carga de archivos y selección de zona/fecha */}
        <section className="controls">
          {/* Carga de los dos archivos NetCDF (precipitación y temperatura) */}
          <FileUpload />

          {/* Selector de nivel (comuna/provincia/región) y valor */}
          <ZonaSelector onSeleccionar={manejarSeleccionZona} />

          {/* Selector de fecha disponible */}
          <FechaSelector
            value={fechaSeleccionada}
            onSeleccionar={manejarCambioFecha}
          />
        </section>

        {/* Mapa solo si ya hay zona y valor seleccionados */}
        {zonaSeleccionada && valorSeleccionado && (
          <MapaImagen
            zona={zonaSeleccionada}
            valor={valorSeleccionado}
            fecha={fechaSeleccionada}
          />
        )}
      </main>

      {/* —–––––––––––––––––––––––––––––––––––––––––––––––– */}
      {/* Pie de página con créditos */}
      {/* —–––––––––––––––––––––––––––––––––––––––––––––––– */}  
      <footer className="app-footer">
        © {new Date().getFullYear()} Benjamín Ortega Rebolledo — Universidad del Bío-Bío — Facultad de Ciencias Empresariales
      </footer>
    </div>
  );
}

export default App;
