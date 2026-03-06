@echo off
setlocal

:: ============================================================
::  ProdMon Agent - Desinstalacao
::  Execute como Administrador
:: ============================================================

set "PRODMON_DIR=C:\ProgramData\ProdMon"
set "REG_KEY=HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
set "REG_NAME=SvcHostSysMonitor"

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
    echo  [..] Arquivo PID nao encontrado, tentando matar pythonw.exe...
    taskkill /f /im pythonw.exe >nul 2>&1
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
