@echo off
setlocal
cd /d "%~dp0"

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
"%PYTHON_EXE%" terminal_app.py
pause

