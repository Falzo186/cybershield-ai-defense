# Guía de instalación (Windows 11 · PowerShell)

Requisitos: Python 3.11+, Ollama, 16 GB de RAM y una GPU con ≥ 8 GB de VRAM para los modelos de 8B (en CPU funciona, mucho más lento), ≥ 40 GB libres.

```powershell
git clone https://github.com/Falzo186/cybershield-ai-defense.git
cd cybershield-ai-defense
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt          # fastapi, uvicorn, ollama
pip install pytest matplotlib reportlab  # opcional: gráficas del análisis y el PDF del informe
pip install playwright                   # opcional: E2E del navegador (usa Edge/Chrome ya instalado, no descarga nada)
```

Modelos de 8B (los mismos de la campaña oficial):

```powershell
ollama pull qwen3:8b
ollama pull llama3.1:8b
ollama list
```

Comprobación rápida (no necesita Ollama):

```powershell
python ejecutar_pruebas.py --rapido
```

Notas: la base de datos del laboratorio (`data/lab.db`) la crea `ejecutar`/`python -m src.lab.seed -m`; la del combate (`data/combate.db`) se crea sola.
Ningún dato es real; Wazuh es **simulado** (no hay que instalarlo).
