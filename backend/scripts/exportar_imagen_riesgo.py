import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.procesar import exportar_imagen_riesgo

resultado = exportar_imagen_riesgo("uploads/riesgo/riesgo_riesgo_2019-05.nc")
print(resultado)
