import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.procesar import generar_capas_fuzzy

ruta_archivo = "uploads/recortado/recortado_CR2MET_pr_v2.0_mon_1979_2019_005deg.nc"
# ruta_archivo = "uploads/recortado/recortado_CR2MET_t2m_v2.0_mon_1979_2019_005deg.nc"

resultado = generar_capas_fuzzy(ruta_archivo)
print("✅ FUNCIONÓ:")
print(resultado)
