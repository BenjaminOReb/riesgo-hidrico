import React, { useState } from 'react';
import axios from 'axios';

/*
  Permite al usuario seleccionar y subir exactamente dos archivos NetCDF (.nc)
  al servidor, y muestra en pantalla el estado de cada subida y procesamiento.
*/

function FileUpload() {
  // Estado que almacena el mensaje de estado para mostrar al usuario
  const [status, setStatus] = useState("");

  /*
    – Se invoca cuando el usuario cambia la selección de archivos.
    – Valida que se hayan seleccionado exactamente 2 archivos.
    – Por cada archivo, crea un FormData y envía una petición POST a /upload.
    – Actualiza el estado con mensajes de éxito o fallo.
  */
  const handleUpload = async (event) => {
    const files = event.target.files;

    // Validación: exactamente 2 archivos
    if (files.length !== 2) {
      setStatus("Por favor selecciona exactamente 2 archivos NetCDF (.nc)");
      return;
    }

    // Mensaje inicial
    setStatus("Subiendo archivos...");

    // Sube los archivos uno a uno
    for (let i = 0; i < files.length; i++) {
      const formData = new FormData();
      formData.append('file', files[i]);

      try {
        // Petición al backend
        const res = await axios.post(
          'http://localhost:5000/upload', 
          formData, 
          { headers: { 'Content-Type': 'multipart/form-data' }
        });

        console.log(`✅ ${files[i].name} subido:`, res.data);
        // Añade en status el mensaje de éxito para este archivo
        setStatus(prev => prev + `\n✅ ${files[i].name} subido correctamente`);
      } catch (error) {
        console.error(`❌ Error al subir ${files[i].name}:`, error);
        // Añade en status el mensaje de error para este archivo
        setStatus(prev => prev + `\n❌ Error al subir ${files[i].name}`);
      }
    }

    // Mensaje final cuando ambos archivos han sido procesados
    setStatus(prev => prev + `\n✅ Ambos archivos fueron procesados.`);
  };

  return (
    <div style={{ padding: '1rem' }}>
      <h2>Subir Archivos NetCDF</h2>
      {/*
        – Input de tipo file que acepta múltiples archivos con extensión .nc
        – onChange dispara la función handleUpload
      */}
      <input
        type="file"
        accept=".nc"
        multiple
        onChange={handleUpload}
      />
      {/*
        – Preformatea el texto con <pre> para mantener saltos de línea
        – Muestra el contenido de `status` al usuario
      */}
      <pre style={{ whiteSpace: 'pre-wrap', marginTop: '1rem' }}>{status}</pre>
    </div>
  );
}

export default FileUpload;
