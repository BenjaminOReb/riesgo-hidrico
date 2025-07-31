import { useState, useEffect } from 'react';

/**
 * ZonaSelector
 * Permite al usuario elegir el nivel geográfico (país, macrozona, región, provincia o comuna)
 * y luego selecciona automáticamente el valor para macrozonas o deja elegir para los demás niveles.
 */
function ZonaSelector({ onSeleccionar }) {
  // Nivel geográfico
  const [zona, setZona] = useState('pais');
  // Jerarquía regiones→provincias→comunas
  const [ubicaciones, setUbicaciones] = useState({});
  // Lista de posibles valores (regiones/provincias/comunas) según 'zona'
  const [valores, setValores] = useState([]);
  // Valor seleccionado
  const [valorSeleccionado, setValorSeleccionado] = useState('');

  // Carga inicial de ubicaciones
  useEffect(() => {
    fetch('http://localhost:5000/api/ubicaciones')
      .then(r => r.json())
      .then(data => setUbicaciones(data))
      .catch(console.error);
  }, []);

  // Cada vez que cambia 'zona' o 'ubicaciones', actualizo 'valores' y 'valorSeleccionado'
  useEffect(() => {
    let opts = [];

    if (zona === 'pais') {
      opts = ['Chile'];
    }
    else if (zona === 'norte') {
      opts = ['Norte'];
    }
    else if (zona === 'centro') {
      opts = ['Centro'];
    }
    else if (zona === 'sur') {
      opts = ['Sur'];
    }
    else if (zona === 'region') {
      opts = Object.keys(ubicaciones);
    }
    else if (zona === 'provincia') {
      Object.values(ubicaciones).forEach(provs => {
        opts.push(...Object.keys(provs));
      });
    }
    else if (zona === 'comuna') {
      Object.values(ubicaciones).forEach(provs => {
        Object.values(provs).forEach(coms => {
          opts.push(...coms);
        });
      });
    }

    setValores(opts.sort());
    // Para macrozonas y país, preselecciono el único valor
    if (['pais','norte','centro','sur'].includes(zona)) {
      setValorSeleccionado(opts[0]);
    } else {
      setValorSeleccionado('');
    }
  }, [zona, ubicaciones]);

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
          <option value="pais">País (Chile)</option>
          <option value="norte">Zona Norte</option>
          <option value="centro">Zona Centro</option>
          <option value="sur">Zona Sur</option>
          <option value="region">Región</option>
          <option value="provincia">Provincia</option>
          <option value="comuna">Comuna</option>
        </select>
      </label>
      &nbsp;&nbsp;
      <label>
        Valor:&nbsp;
        {(['pais','norte','centro','sur'].includes(zona)) ? (
          // Para país o macrozonas, sólo muestro el valor preseleccionado
          <input
            type="text"
            readOnly
            value={valorSeleccionado}
            style={{ width: '8rem' }}
          />
        ) : (
          // Para región/provincia/comuna, dropdown normal
          <select
            value={valorSeleccionado}
            onChange={e => setValorSeleccionado(e.target.value)}
          >
            <option value="">-- Seleccionar --</option>
            {valores.map((v, i) => (
              <option key={i} value={v}>{v}</option>
            ))}
          </select>
        )}
      </label>
      &nbsp;&nbsp;
      <button
        onClick={handleEnviar}
        disabled={!valorSeleccionado}
      >
        Ver en mapa
      </button>
    </div>
  );
}

export default ZonaSelector;
