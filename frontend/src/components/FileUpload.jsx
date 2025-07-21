import React, { useState } from 'react';
import axios from 'axios';

/*
  Permite al usuario seleccionar y subir exactamente dos archivos NetCDF (.nc)
  al servidor, muestra el estado de cada subida y, tras un upload exitoso,
  invoca onUploadSuccess() para que el selector de fechas se recargue.
*/

function FileUpload({ onUploadSuccess }) {
  const [status, setStatus] = useState("");

  const handleUpload = async (event) => {
    const files = event.target.files;

    if (files.length !== 2) {
      setStatus("Por favor selecciona exactamente 2 archivos NetCDF (.nc)");
      return;
    }

    setStatus("Subiendo archivos...");

    let allOk = true;
    for (let i = 0; i < files.length; i++) {
      const formData = new FormData();
      formData.append('file', files[i]);

      try {
        const res = await axios.post(
          'http://localhost:5000/upload', 
          formData, 
          { headers: { 'Content-Type': 'multipart/form-data' } }
        );
        setStatus(prev => prev + `\n✅ ${files[i].name} subido correctamente`);
      } catch (error) {
        console.error(`❌ Error al subir ${files[i].name}:`, error);
        setStatus(prev => prev + `\n❌ Error al subir ${files[i].name}`);
        allOk = false;
      }
    }

    if (allOk) {
      setStatus(prev => prev + `\n🎉 Ambos archivos fueron procesados con éxito.`);
      // Disparamos la recarga de fechas en App.jsx
      onUploadSuccess();
    }
  };

  return (
    <div style={{ padding: '1rem' }}>
      <h2>Subir Archivos NetCDF</h2>
      <input
        type="file"
        accept=".nc"
        multiple
        onChange={handleUpload}
      />
      <pre style={{ whiteSpace: 'pre-wrap', marginTop: '1rem' }}>
        {status}
      </pre>
    </div>
  );
}

export default FileUpload;
