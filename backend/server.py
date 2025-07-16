
# Importa el blueprint que contiene todas las rutas de la API
from app.routes import routes

# ImportaFlask para crear la aplicación y CORS para permitir peticiones desde el frontend
from flask import Flask
from flask_cors import CORS

# Importa load_dotenv para cargar variables de entorno desde un archivo .env
from dotenv import load_dotenv
load_dotenv()  # Carga las variables de entorno definidas en .env al entorno de ejecución

# Crea la aplicación Flask
app = Flask(__name__)

# Habilita CORS (Cross-Origin Resource Sharing) para permitir que el frontend
# (normalmente corriendo en otro puerto) pueda hacer peticiones a este servidor
CORS(app)

# Registra el blueprint definido en app/routes.py.
# Todas las rutas definidas ahí quedarán montadas en la aplicación principal.
app.register_blueprint(routes)

# Punto de entrada de la aplicación: si se ejecuta este archivo directamente,
# arranca el servidor en modo debug (con recarga automática y mensajes detallados).
if __name__ == '__main__':
    # debug=True activa el modo de desarrollo con logs más verbosos y autorecarga
    app.run(debug=True)
