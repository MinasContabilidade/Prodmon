@echo off
setlocal EnableDelayedExpansion

:: ============================================================
::  ProdMon Agent - Desinstalacao
::  Execute como Administrador
:: ============================================================

set "PRODMON_DIR=C:\ProgramData\ProdMon"
set "REG_KEY=HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
set "REG_NAME=ProdMonAgent"

echo.
echo  ============================================================
echo   ProdMon Agent - Desinstalacao
echo  ============================================================
echo.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo  [ERRO] Execute como Administrador.
    pause & exit /b 1
)

:: ── Parar o agente pelo PID salvo ─────────────────────────────
set "PID_FILE=%PRODMON_DIR%\prodmon.pid"
if exist "%PID_FILE%" (
    set /p AGENT_PID=<"%PID_FILE%"
    echo  [..] Encerrando agente (PID: !AGENT_PID!)...
    taskkill /pid !AGENT_PID! /f >nul 2>&1
    timeout /t 2 >nul
) else (
    echo  [..] Arquivo PID nao encontrado, buscando processo prodmon_agent...
    for /f "tokens=2 delims==" %%p in ('wmic process where "name='pythonw.exe' and commandline like '%%prodmon_agent%%'" get processid /value 2^>nul ^| findstr ProcessId') do (
        echo  [..] Encontrado ProdMon (PID: %%p), encerrando...
        taskkill /pid %%p /f >nul 2>&1
    )
    timeout /t 2 >nul
)

:: ── Remover entrada de startup ────────────────────────────────
echo  [..] Removendo entrada de startup...
reg delete "%REG_KEY%" /v "%REG_NAME%" /f >nul 2>&1
echo  [OK] Entrada removida do registro.

:: ── Remover arquivos (pergunta antes) ─────────────────────────
echo.
set /p "CONFIRM=Remover todos os dados locais em %PRODMON_DIR%? [S/N]: "
if /i "%CONFIRM%" == "S" (
    attrib -h -s "%PRODMON_DIR%" >nul 2>&1
    rd /s /q "%PRODMON_DIR%" >nul 2>&1
    echo  [OK] Pasta removida.
) else (
    echo  [OK] Dados locais mantidos em %PRODMON_DIR%
)

echo.
echo  Desinstalacao concluida.
echo.
pause
exit /b 0
