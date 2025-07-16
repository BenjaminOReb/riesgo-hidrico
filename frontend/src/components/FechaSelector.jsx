import { useState, useEffect } from 'react';

function FechaSelector({ onSeleccionar }) {
  // Estado para almacenar la lista de fechas disponibles que trae el servidor
  const [fechasDisponibles, setFechasDisponibles] = useState([]);
  // Estado para la fecha actualmente seleccionada en el <select>
  const [fecha, setFecha] = useState('');

  // useEffect con [] como dependencia: se ejecuta una sola vez al montar el componente
  useEffect(() => {
    // Función asíncrona que consulta al backend las fechas disponibles
    const fetchFechas = async () => {
      try {
        const res = await fetch('http://localhost:5000/api/fechas-disponibles');
        const data = await res.json();
        // Guarda en el estado la lista de fechas recuperadas
        setFechasDisponibles(data);

        // Si hay al menos una fecha, se usa como selección inicial
        if (data.length > 0) {
          setFecha(data[0]);          // Mostrar la primera fecha en el select
          onSeleccionar(data[0]);     // Notificar al componente padre de la selección inicial
        }
      } catch (error) {
        console.error("Error al obtener fechas disponibles:", error);
      }
    };

    // Lanza la petición al servidor
    fetchFechas();
  }, []);

  // Manejador cuando el usuario cambia la opción seleccionada
  const manejarCambio = (e) => {
    const nuevaFecha = e.target.value;
    setFecha(nuevaFecha);             // Actualiza el estado local
    onSeleccionar(nuevaFecha);        // Informa al padre de la nueva selección 
  };

  return (
    <div style={{ marginTop: '20px' }}>
      <label htmlFor="fecha">📅 Selecciona una fecha (año-mes): </label>
      {/* Usa un <select> en lugar de <input type="month"> para restringir
          al usuario a las fechas que realmente existen en nuestro backend */}
      <select id="fecha" value={fecha} onChange={manejarCambio}>
         {/* Rellenamos las opciones dinámicamente desde el estado */}
        {fechasDisponibles.map((f) => (
          <option key={f} value={f}>
            {f}
          </option>
        ))}
      </select>
    </div>
  );
}

export default FechaSelector;
