@echo off
setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo.
echo  === CyberShield AI Defense - arranque ===
echo.

rem --- 1. Python (si falta, intenta instalarlo con winget) ---
set "PY="
where python >nul 2>nul && python -c "import sys;sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul && set "PY=python"
if not defined PY where py >nul 2>nul && py -3 -c "import sys;sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY (
  echo [!] No hay Python 3.9+. Intentando instalarlo con winget...
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
  echo.
  echo [i] Si se instalo, CIERRA esta ventana y vuelve a ejecutar ejecutar.bat.
  echo     Si no, instala Python desde https://www.python.org/downloads/ ^(marca "Add python.exe to PATH"^).
  pause
  exit /b 1
)

rem --- 2. Entorno virtual + dependencias (solo descarga lo que falta) ---
if not exist ".venv\Scripts\python.exe" (
  echo [i] Creando entorno virtual .venv ...
  %PY% -m venv .venv
  if errorlevel 1 ( echo [x] No se pudo crear .venv & pause & exit /b 1 )
)
set "VPY=.venv\Scripts\python.exe"
echo [i] Instalando/comprobando librerias ^(la primera vez descarga; requiere internet^)...
"%VPY%" -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo [x] Fallo la instalacion de librerias. Revisa tu conexion a internet.
  pause
  exit /b 1
)

rem --- 3. Firewall: permitir el puerto 8000 para el companero (solo si hay permisos de administrador) ---
net session >nul 2>nul
if not errorlevel 1 (
  netsh advfirewall firewall show rule name="CyberShield 8000" >nul 2>nul
  if errorlevel 1 (
    netsh advfirewall firewall add rule name="CyberShield 8000" dir=in action=allow protocol=TCP localport=8000 >nul
    echo [OK] Regla de firewall creada para el puerto 8000.
  )
) else (
  echo [i] Sin permisos de administrador: si el companero no puede entrar, ejecuta una vez este .bat con
  echo     clic derecho ^> "Ejecutar como administrador" ^(abre el puerto 8000 en el firewall^).
)

rem --- 4. Ollama (opcional: sin el, la IA va en modo SIMULADO) ---
where ollama >nul 2>nul
if errorlevel 1 (echo [i] Ollama no instalado: la IA funciona en modo SIMULADO ^(suficiente para presentar^).) else (echo [i] Ollama detectado: se enciende desde el panel del Administrador solo si lo necesitas.)

echo [OK] Arrancando servidor... ^(Ctrl+C para detener^)
"%VPY%" server\app.py
pause
