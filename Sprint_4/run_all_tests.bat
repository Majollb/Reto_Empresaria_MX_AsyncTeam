@echo off
setlocal
cd /d "%~dp0"
echo =========================================================================
echo   AUTOMATIZACION Y SOFTWARE DEL BAJIO - Pruebas Integrales de Sprints
echo   Sprint 1 (HU-01..03) + Sprint 2 (HU-04..06) + Sprint 3 (HU-07..09) + Sprint 4 (HU-10..12)
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
"%PYTHON_EXE%" tests/run_all_tests.py
pause

