@echo off
rem CyberShield AI Defense - arranque en Windows (CMD o PowerShell). Doble clic o: .\ejecutar.bat
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo [x] No se encontro Python. Instalalo desde https://www.python.org/downloads/
  pause
  exit /b 1
)
echo [i] Comprobando dependencias...
python -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo [x] Fallo la instalacion de dependencias.
  pause
  exit /b 1
)
where ollama >nul 2>nul
if errorlevel 1 echo [!] Ollama no esta en el PATH: la batalla real y el manual REAL no funcionaran ^(la simulacion si^).
echo [OK] Arrancando... abre http://localhost:8000  ^(Ctrl+C para detener^)
python server\app.py
pause
