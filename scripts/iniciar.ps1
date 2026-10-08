# IntegraPublic - inicia o servidor na porta 6789
# Uso:  powershell -ExecutionPolicy Bypass -File .\scripts\iniciar.ps1

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

$venvPython = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Ambiente virtual nao encontrado." -ForegroundColor Red
    Write-Host "Execute primeiro: .\scripts\instalar.ps1" -ForegroundColor Yellow
    exit 1
}

# A porta 6789 e exclusiva deste sistema; outros sistemas desta maquina usam
# suas proprias portas e seus proprios ambientes virtuais.
$emUso = Get-NetTCPConnection -LocalPort 6789 -State Listen -ErrorAction SilentlyContinue
if ($emUso) {
    Write-Host "A porta 6789 ja esta em uso por outro processo (PID $($emUso[0].OwningProcess))." -ForegroundColor Yellow
    Write-Host "Se for uma instancia antiga do IntegraPublic, encerre-a antes de continuar." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "=== IntegraPublic ===" -ForegroundColor Cyan
Write-Host "Rede:  http://10.10.1.225:6789"
Write-Host "Local: http://localhost:6789"
Write-Host "Encerrar: Ctrl+C"
Write-Host ""

& $venvPython -m streamlit run app.py --server.address 0.0.0.0 --server.port 6789
