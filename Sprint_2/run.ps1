# Script de ejecución para PowerShell
$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "=========================================================================" -ForegroundColor Cyan
Write-Host "  AUTOMATIZACIÓN Y SOFTWARE DEL BAJÍO - Sistema de Tickets" -ForegroundColor White
Write-Host "=========================================================================" -ForegroundColor Cyan

$pythonCandidates = @(
    "C:\Program Files\Unity\Hub\Editor\6000.6.3f1\Editor\Data\PlaybackEngines\WebGLSupport\BuildTools\Emscripten\python\python.exe",
    "python",
    "py"
)

$workingPython = $null

foreach ($cand in $pythonCandidates) {
    if ($cand -like "*\*") {
        if (Test-Path $cand) {
            $workingPython = $cand
            break
        }
    } else {
        if (Get-Command $cand -ErrorAction SilentlyContinue) {
            $testOut = (& $cand --version 2>&1) | Out-String
            if ($LASTEXITCODE -eq 0 -and $testOut -match "Python 3") {
                $workingPython = $cand
                break
            }
        }
    }
}

if (-not $workingPython) {
    Write-Host "[ERROR] No se encontró una instalación funcional de Python en el sistema." -ForegroundColor Red
    exit 1
}

Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

Write-Host "Ejecutable Python detectado: $workingPython" -ForegroundColor Gray
Write-Host "Iniciando servidor web en: http://127.0.0.1:5000" -ForegroundColor Green
Write-Host "Presione Ctrl+C en esta ventana para detener el servidor." -ForegroundColor Yellow
Write-Host "-------------------------------------------------------------------------" -ForegroundColor Gray

& $workingPython app.py
