import { useState, useEffect } from 'react';

function FechaSelector({ onSeleccionar, reloadFlag }) {
  const [fechasDisponibles, setFechasDisponibles] = useState([]);
  const [fecha, setFecha] = useState('');

  // Extraemos la carga de fechas en una función reutilizable
  const fetchFechas = async () => {
    try {
      const res  = await fetch('http://localhost:5000/api/fechas-disponibles', { cache: 'no-store' });
      const data = await res.json();
      setFechasDisponibles(data);

      if (data.length > 0) {
        setFecha(data[0]);
        onSeleccionar(data[0]);
      }
    } catch (error) {
      console.error("Error al obtener fechas disponibles:", error);
    }
  };

  // Se ejecuta al montar y también cada vez que cambie reloadFlag
  useEffect(() => {
    fetchFechas();
  }, [reloadFlag]);

  const manejarCambio = (e) => {
    const nuevaFecha = e.target.value;
    setFecha(nuevaFecha);
    onSeleccionar(nuevaFecha);
  };

  return (
    <div style={{ marginTop: '20px' }}>
      <label htmlFor="fecha">📅 Selecciona una fecha (año-mes): </label>
      <select id="fecha" value={fecha} onChange={manejarCambio}>
        <option value="" disabled>-- elige fecha --</option>
        {fechasDisponibles.map((f) => (
          <option key={f} value={f}>{f}</option>
        ))}
      </select>
    </div>
  );
}

export default FechaSelector;
