@echo off
REM ============================================================
REM   Iniciar Sistemas - sobe IntegraPublic + SpiderFoot
REM   Dois cliques quando voce quiser usar. Cada servico abre em
REM   sua propria janela; para PARAR, feche a janela do servico.
REM ============================================================
title Iniciar Sistemas (IntegraPublic + SpiderFoot)

echo.
echo ==============================================================
echo   Subindo os servicos em janelas separadas...
echo ==============================================================
echo.

REM --- SpiderFoot (127.0.0.1:5001) ---
netstat -ano | findstr /C:":5001" | findstr /C:"LISTENING" >nul
if %errorlevel%==0 (
    echo [OK]   SpiderFoot ja esta no ar ^(porta 5001^).
) else (
    echo [..]   Iniciando SpiderFoot...
    start "SpiderFoot (127.0.0.1:5001)" "C:\Sistemas Pronto\spiderfoot\IniciarSpiderFoot.bat"
)

REM --- IntegraPublic (:6789) ---
netstat -ano | findstr /C:":6789" | findstr /C:"LISTENING" >nul
if %errorlevel%==0 (
    echo [OK]   IntegraPublic ja esta no ar ^(porta 6789^).
) else (
    echo [..]   Iniciando IntegraPublic...
    start "IntegraPublic (porta 6789)" "C:\Sistemas Pronto\Sistema Geral Interdepartamental\IniciarIntegraPublic.bat"
)

echo.
echo --------------------------------------------------------------
echo   Acesse o sistema em:  http://10.10.1.225:6789
echo.
echo   Cada servico esta rodando na sua propria janela.
echo   Para PARAR um servico, feche a janela dele.
echo   Aguarde ~15s ate o IntegraPublic terminar de subir.
echo --------------------------------------------------------------
echo.
echo Esta janela pode ser fechada - os servicos continuam nas
echo janelas proprias.
echo.
timeout /t 8 >nul
