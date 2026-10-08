# IntegraPublic - instalacao do ambiente virtual
# Uso:  powershell -ExecutionPolicy Bypass -File .\scripts\instalar.ps1

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

Write-Host ""
Write-Host "=== IntegraPublic - instalacao ===" -ForegroundColor Cyan
Write-Host "Pasta do projeto: $raiz"
Write-Host ""

# --- 1. localizar o Python ---------------------------------------------------
$python = $null
foreach ($tentativa in @("py -3.11", "py -3", "python")) {
    $partes = $tentativa.Split(" ")
    $exe = $partes[0]
    if (Get-Command $exe -ErrorAction SilentlyContinue) {
        $python = $tentativa
        break
    }
}
if (-not $python) {
    Write-Host "Python nao encontrado no PATH. Instale o Python 3.11 ou superior." -ForegroundColor Red
    exit 1
}
Write-Host "[1/4] Python encontrado: $python" -ForegroundColor Green

# --- 2. criar o ambiente virtual --------------------------------------------
if (Test-Path ".venv") {
    Write-Host "[2/4] Ambiente virtual .venv ja existe - reutilizando." -ForegroundColor Yellow
} else {
    Write-Host "[2/4] Criando ambiente virtual em .venv ..."
    Invoke-Expression "$python -m venv .venv"
}

$venvPython = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Falha ao criar o ambiente virtual." -ForegroundColor Red
    exit 1
}

# --- 3. instalar dependencias ------------------------------------------------
Write-Host "[3/4] Atualizando o pip ..."
& $venvPython -m pip install --upgrade pip --quiet

Write-Host "[4/4] Instalando dependencias (streamlit, pandas, requests, openpyxl) ..."
& $venvPython -m pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "Falha ao instalar as dependencias." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Instalacao concluida." -ForegroundColor Green
Write-Host ""
Write-Host "Para iniciar o sistema:" -ForegroundColor Cyan
Write-Host "    .\scripts\iniciar.ps1"
Write-Host ""
Write-Host "Acesso na rede: http://10.10.1.225:6789"
Write-Host "Primeiro login: usuario 'admin', senha 'mudar@123'"
Write-Host ""
Write-Host "Se o acesso pela rede nao funcionar, libere a porta no firewall" -ForegroundColor Yellow
Write-Host "executando UMA VEZ, como administrador:" -ForegroundColor Yellow
Write-Host '    New-NetFirewallRule -DisplayName "IntegraPublic 6789" -Direction Inbound -Protocol TCP -LocalPort 6789 -Action Allow'
Write-Host ""
