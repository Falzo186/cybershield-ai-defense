"""Evaluación autónoma del laboratorio.

    from src.lab.evaluacion import campana, escenarios, metricas

    r = campana.ejecutar(host="http://localhost:11434", modelo="qwen2.5:1.5b", modo="rapido")
    print(r["metricas"]["exactitud"])     # {'exitos': .., 'n': .., 'valor': .., 'bajo': .., 'alto': ..}
"""
from . import campana, escenarios, metricas  # noqa: F401
