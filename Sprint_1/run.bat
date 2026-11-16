@echo off
setlocal
cd /d "%~dp0"
echo =========================================================================
echo   AUTOMATIZACION Y SOFTWARE DEL BAJIO - Sistema de Tickets
echo =========================================================================

set "PYTHON_EXE="

if exist "C:\Program Files\Unity\Hub\Editor\6000.6.3f1\Editor\Data\PlaybackEngines\WebGLSupport\BuildTools\Emscripten\python\python.exe" (
    set "PYTHON_EXE=C:\Program Files\Unity\Hub\Editor\6000.6.3f1\Editor\Data\PlaybackEngines\WebGLSupport\BuildTools\Emscripten\python\python.exe"
    goto found
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_EXE=py"
    goto found
)

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_EXE=python"
    goto found
)

:notfound
echo [ERROR] No se encontro Python instalado en el sistema.
pause
exit /b 1

:found
echo Liberando puerto 5000 de sesiones previas...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5000 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>nul
echo Ejecutable Python detectado: "%PYTHON_EXE%"
echo Iniciando aplicacion web en http://127.0.0.1:5000 ...
echo Presione CTRL+C para detener el servidor.
echo -------------------------------------------------------------------------
"%PYTHON_EXE%" app.py
pause
