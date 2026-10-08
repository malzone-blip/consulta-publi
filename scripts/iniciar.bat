@echo off
REM IntegraPublic - atalho para iniciar o sistema com dois cliques
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtual nao encontrado.
    echo Execute primeiro: powershell -ExecutionPolicy Bypass -File .\scripts\instalar.ps1
    pause
    exit /b 1
)
echo.
echo === IntegraPublic ===
echo Rede:  http://10.10.1.225:6789
echo Local: http://localhost:6789
echo Encerrar: Ctrl+C
echo.
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 0.0.0.0 --server.port 6789
pause
