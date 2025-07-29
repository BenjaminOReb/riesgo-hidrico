import { useState, useEffect } from 'react';

/**
 * ZonaSelector
 * Permite al usuario elegir el nivel geográfico (comuna, provincia o región)
 * y luego seleccionar el valor específico dentro de ese nivel.
 *
 * Props:
 *  - onSeleccionar: función callback que recibe un objeto { zona, valor }
 *                   cuando se hace clic en "Ver en mapa".
 */

function ZonaSelector({ onSeleccionar }) {
  // Estado para el nivel de zona seleccionado (comuna/provincia/región/país)
  const [zona, setZona] = useState('pais');
  // Estado para almacenar la jerarquía completa de ubicaciones obtenida del backend
  const [ubicaciones, setUbicaciones] = useState({});
  // Estado para la lista de opciones (nombres) según el nivel 'zona'
  const [valores, setValores] = useState([]);
  // Estado para el valor concreto seleccionado dentro de 'valores'
  const [valorSeleccionado, setValorSeleccionado] = useState('');

  // Al montar el componente, cargar la jerarquía de ubicaciones desde la API
  useEffect(() => {
    fetch('http://localhost:5000/api/ubicaciones')
      .then(res => res.json())
      .then(data => setUbicaciones(data))
      .catch(err => console.error('Error al cargar ubicaciones:', err));
  }, []);

  // Cada vez que cambian 'zona' o 'ubicaciones', recalcular la lista de valores disponibles
  useEffect(() => {
    const nuevasOpciones = [];

    if (zona === 'pais') {
      nuevasOpciones.push("Chile");
    }
    else if (zona === 'region') {
      nuevasOpciones.push(...Object.keys(ubicaciones));
    }
    else if (zona === 'provincia') {
      Object.values(ubicaciones).forEach(provinciasObj => {
        nuevasOpciones.push(...Object.keys(provinciasObj));
      });
    }
    else if (zona === 'comuna') {
      Object.values(ubicaciones).forEach(provObj => {
        Object.values(provObj).forEach(comunasArray => {
          nuevasOpciones.push(...comunasArray);
        });
      });
    }

    // Ordenar y actualizar la lista de valores
    setValores(nuevasOpciones.sort());

    // Sólo preseleccionamos "Chile" si estamos en zona "pais"
    if (zona === 'pais') {
      setValorSeleccionado('Chile');
    } 
  }, [zona, ubicaciones]);


  // Al pulsar el botón, notificar al componente padre de la selección
  const handleEnviar = () => {
    if (valorSeleccionado) {
      onSeleccionar({ zona, valor: valorSeleccionado });
    }
  };

  return (
    <div style={{ marginBottom: '1rem' }}>
      <label>
        Zona:&nbsp;
        <select value={zona} onChange={e => setZona(e.target.value)}>
          <option value="pais">Chile</option>
          <option value="comuna">Comuna</option>
          <option value="provincia">Provincia</option>
          <option value="region">Región</option>
        </select>
      </label>
      &nbsp;&nbsp;
      <label>
        Valor:&nbsp;
        {zona === 'pais' ? (
          // Cuando es país, no hay lista: solo mostramos el texto
          <input type="text" readOnly value="Chile" style={{ width: '8rem' }} />
        ) : (
          // Para cualquier otra zona, el dropdown habitual
          <select
            value={valorSeleccionado}
            onChange={e => setValorSeleccionado(e.target.value)}
          >
            <option value="">-- Seleccionar --</option>
            {valores.map((v, idx) => (
              <option key={idx} value={v}>
                {v}
              </option>
            ))}
          </select>
        )}
      </label>
      &nbsp;&nbsp;
      <button
        onClick={handleEnviar}
        // Si es país, siempre hay valor (Chile); en otro caso debe elegirse uno
        disabled={zona !== 'pais' && !valorSeleccionado}
      >
        Ver en mapa
      </button>
    </div>
  );
}

export default ZonaSelector;
