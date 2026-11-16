@echo off
setlocal
cd /d "%~dp0"
echo =========================================================================
echo   AUTOMATIZACION Y SOFTWARE DEL BAJIO - Pruebas Automatizadas Sprint 4
echo   Historias de Usuario: HU-10, HU-11, HU-12
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
echo [ERROR] No se encontro Python en el sistema.
pause
exit /b 1

:found
"%PYTHON_EXE%" tests/run_sprint_4.py
pause
