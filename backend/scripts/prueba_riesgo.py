import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.procesar import calcular_indice_riesgo

resultado = calcular_indice_riesgo(
    "uploads/fuzzy/fuzzy_pr_2019-05.nc",
    "uploads/fuzzy/fuzzy_t2m_2019-05.nc"
)

print("✅ OK:")
print(resultado)
