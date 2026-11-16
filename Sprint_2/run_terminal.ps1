# Script para ejecutar la consola interactiva en PowerShell
$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

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
    Write-Host "[ERROR] No se encontro una instalacion funcional de Python en el sistema." -ForegroundColor Red
    exit 1
}

& $workingPython terminal_app.py

