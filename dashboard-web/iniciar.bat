@echo off
rem Inicia el dashboard y abre el navegador cuando el servidor ya esta listo.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Instalando dependencias por primera vez...
  py -3.13 -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)
start "" /min cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8765"
.venv\Scripts\python.exe -m dashboard.server
