@echo off
REM ============================================================
REM   IntegraPublic - iniciar o sistema (duplo clique)
REM   Faz uma partida LIMPA: encerra qualquer servidor anterior,
REM   apaga o bytecode em cache (__pycache__) e entao sobe.
REM   Assim voce nunca fica com uma versao velha rodando.
REM ============================================================
setlocal
title IntegraPublic - servidor (nao feche enquanto estiver usando)
cd /d "%~dp0"

set "PYEXE=.venv\Scripts\python.exe"

REM 1) Ambiente virtual precisa existir
if not exist "%PYEXE%" (
    echo.
    echo [ERRO] Ambiente virtual nao encontrado em .venv
    echo Rode a instalacao uma vez, no PowerShell, nesta pasta:
    echo     powershell -ExecutionPolicy Bypass -File .\scripts\instalar.ps1
    echo.
    pause
    exit /b 1
)

REM 2) Encerra QUALQUER servidor anterior na porta 6789 (evita "zombie")
echo [..] Encerrando instancia anterior (se houver)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":6789" ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1

REM 3) Apaga o bytecode em cache das pastas de codigo (forca recompilar do zero)
for %%d in (core paginas services scripts) do if exist "%%d\__pycache__" rd /s /q "%%d\__pycache__" 2>nul

echo.
echo ==============================================================
echo   IntegraPublic esta subindo (partida limpa)...
echo.
echo   Na rede:  http://10.10.1.225:6789
echo   Local:    http://localhost:6789
echo.
echo   Primeiro acesso: usuario "admin" / senha "mudar@123"
echo   Para encerrar o servidor: feche esta janela ou tecle Ctrl+C
echo ==============================================================
echo.

REM 4) Sobe o servidor (endereco e porta vem de .streamlit\config.toml)
"%PYEXE%" -m streamlit run app.py

echo.
echo O servidor do IntegraPublic foi encerrado.
pause
endlocal
