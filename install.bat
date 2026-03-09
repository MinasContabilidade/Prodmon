@echo off
setlocal EnableDelayedExpansion

:: ============================================================
::  ProdMon Agent v1.3 - Script de Instalacao
::  Execute como Administrador
:: ============================================================

set "PRODMON_DIR=C:\ProgramData\ProdMon"
set "SCRIPT_DIR=%~dp0"
set "REG_KEY=HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
set "REG_NAME=ProdMonAgent"
set "LAUNCHER=%PRODMON_DIR%\start_prodmon.vbs"

echo.
echo  ============================================================
echo   ProdMon Agent - Instalacao
echo  ============================================================
echo.

:: ── Verificar privilegios de administrador ────────────────────
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo  [ERRO] Execute este script com botao direito ^> "Executar como administrador"
    pause & exit /b 1
)

:: ── Ler opcao autostart do config.py ──────────────────────────
:: Ler config usando Python temporário
for /f "tokens=2 delims==" %%i in ('%PYTHONW% -c "import configparser; c=configparser.ConfigParser(); c.read(r'%PRODMON_DIR%\config.py'); print('AUTO='+c['install'].get('autostart', 'true').lower())" 2^>nul') do (
    set "AUTOSTART=%%i"
)
if not defined AUTOSTART set "AUTOSTART=true"
:: Se a instalacao nao incluir agente, forcamos autostart=false para os passos abaixo
if "%INSTALL_AGENT%"=="false" set "AUTOSTART=false"
echo  [OK] autostart = %AUTOSTART%

:: ── Ler idle_threshold_minutes do config.py ──────────────────
set "IDLE_MINUTES=5"
for /f "tokens=1,* delims==" %%a in ('findstr /i "^idle_threshold_minutes" "%SCRIPT_DIR%config.py" 2^>nul') do (
    set "IDLE_RAW=%%b"
)
if defined IDLE_RAW (
    for /f "tokens=*" %%v in ("!IDLE_RAW!") do set "IDLE_MINUTES=%%v"
)
echo  [OK] idle_threshold_minutes = %IDLE_MINUTES%

:: ── Perguntar modo de instalacao ────────────────────────────────
echo.
echo  O que voce deseja instalar nesta maquina?
echo  [1] Cliente (Apenas o Agente Invisivel)
echo  [2] Servidor (Apenas o Dashboard BI)
echo  [3] Ambos (Agente + Dashboard)
echo.
set /p "INSTALL_CHOICE=  Digite 1, 2 ou 3 [1]: "
if not defined INSTALL_CHOICE set "INSTALL_CHOICE=1"

set "INSTALL_AGENT=false"
set "INSTALL_DASHBOARD=false"

if "%INSTALL_CHOICE%"=="1" (
    set "INSTALL_AGENT=true"
    set "INSTALL_MODE_TXT=client"
) else if "%INSTALL_CHOICE%"=="2" (
    set "INSTALL_DASHBOARD=true"
    set "INSTALL_MODE_TXT=server"
) else if "%INSTALL_CHOICE%"=="3" (
    set "INSTALL_AGENT=true"
    set "INSTALL_DASHBOARD=true"
    set "INSTALL_MODE_TXT=both"
) else (
    echo  [ERRO] Opcao invalida. Instalacao abortada.
    pause & exit /b 1
)

:: ── Perguntar nome do operador (somente se instalar agente) ────
if "%INSTALL_AGENT%"=="true" (
    echo.
    echo  Identificacao do operador desta maquina.
    echo  (Este nome aparecera nos relatorios de produtividade)
    echo.
    set /p "OPERATOR_NAME=  Nome do operador: "
    if not defined OPERATOR_NAME (
        set "OPERATOR_NAME=Nao informado"
    )
    echo  [OK] Operador: !OPERATOR_NAME!
) else (
    set "OPERATOR_NAME=Servidor"
)
echo.

:: ── Localizar pythonw.exe ─────────────────────────────────────
for /f "delims=" %%i in ('where pythonw.exe 2^>nul') do (
    if not defined PYTHONW set "PYTHONW=%%i"
)
if not defined PYTHONW (
    echo  [ERRO] pythonw.exe nao encontrado.
    echo         Instale Python 3.8+ marcando a opcao "Add Python to PATH"
    echo         Download: https://www.python.org/downloads/
    pause & exit /b 1
)
echo  [OK] Python: %PYTHONW%

:: ── Localizar pip ─────────────────────────────────────────────
for /f "delims=" %%i in ('where pip.exe 2^>nul') do (
    if not defined PIP set "PIP=%%i"
)
if not defined PIP (
    set "PIP_CMD=%PYTHONW% -m pip"
) else (
    set "PIP_CMD=%PIP%"
)

:: ── Criar estrutura de diretorios ─────────────────────────────
echo  [..] Criando diretorios...
for %%d in (data logs) do (
    if not exist "%PRODMON_DIR%\%%d" (
        mkdir "%PRODMON_DIR%\%%d" 2>nul
    )
)

:: ── Copiar arquivos ───────────────────────────────────────────
echo  [..] Copiando arquivos...

if "%INSTALL_AGENT%"=="true" (
    if not exist "%SCRIPT_DIR%prodmon_agent.py" (
        echo  [ERRO] prodmon_agent.py nao encontrado em %SCRIPT_DIR%
        pause & exit /b 1
    )
    copy /Y "%SCRIPT_DIR%prodmon_agent.py" "%PRODMON_DIR%\prodmon_agent.py" >nul
)

:: config.py: nao sobrescreve se ja existir (preserva configuracoes)
if not exist "%PRODMON_DIR%\config.py" (
    copy /Y "%SCRIPT_DIR%config.py" "%PRODMON_DIR%\config.py" >nul
    echo  [OK] config.py copiado. Configure o caminho de rede antes de usar!
) else (
    echo  [OK] config.py ja existe - mantido sem alteracoes.
)

:: ── Copiar Dashboard (se selecionado) ─────────────────────────
if "%INSTALL_DASHBOARD%"=="true" (
    echo  [..] Copiando arquivos do Dashboard...
    if not exist "%PRODMON_DIR%\dashboard" mkdir "%PRODMON_DIR%\dashboard" 2>nul
    xcopy /Y /E /I "%SCRIPT_DIR%dashboard\*" "%PRODMON_DIR%\dashboard\" >nul 2>&1
    echo  [OK] Dashboard copiado.
)

:: ── Gravar configs variaveis no config.py instalado ────────────
echo  [..] Gravando configuracoes no config.py...
set "CFG_FILE=%PRODMON_DIR%\config.py"

:: Atualiza install_mode
powershell -NoProfile -Command "(Get-Content '!CFG_FILE!') -replace '^install_mode\s*=.*', 'install_mode = ''!INSTALL_MODE_TXT!''' | Set-Content '!CFG_FILE!'" >nul 2>&1

:: Atualiza operator_name
:: Sanitiza o nome do operador (remove caracteres perigosos para scripts)
set "SAFE_NAME=!OPERATOR_NAME!"
set "SAFE_NAME=!SAFE_NAME:'=!"
set "SAFE_NAME=!SAFE_NAME:"=!"
set "SAFE_NAME=!SAFE_NAME:&=!"
set "SAFE_NAME=!SAFE_NAME:|=!"
set "SAFE_NAME=!SAFE_NAME:>=!"
set "SAFE_NAME=!SAFE_NAME:<=!"
set "SAFE_NAME=!SAFE_NAME:;=!"
set "SAFE_NAME=!SAFE_NAME:[=!"
set "SAFE_NAME=!SAFE_NAME:]=!"
set "SAFE_NAME=!SAFE_NAME:{=!"
set "SAFE_NAME=!SAFE_NAME:}=!"
set "SAFE_NAME=!SAFE_NAME:==!"
set "SAFE_NAME=!SAFE_NAME:$=!"
:: Remove backtick (interpretado pelo PowerShell como escape)
set "SAFE_NAME=!SAFE_NAME:`=!"
:: Usa PowerShell para substituir a linha operator_name no arquivo
powershell -NoProfile -Command "(Get-Content '!CFG_FILE!') -replace '^operator_name\s*=.*', 'operator_name = ''!SAFE_NAME!''' | Set-Content '!CFG_FILE!'" >nul 2>&1
if %errorLevel% equ 0 (
    echo  [OK] Operador '!SAFE_NAME!' gravado no config.py.
) else (
    echo  [AVISO] Nao foi possivel gravar o nome do operador.
)

:: ── Proteger config.py (Admins escrevem, Users apenas leem) ──────────────────
icacls "%PRODMON_DIR%\config.py" /inheritance:r /grant:r "SYSTEM:(F)" "Administrators:(F)" "BUILTIN\Users:(R)" >nul 2>&1
if %errorLevel% equ 0 (
    echo  [OK] Permissoes do config.py restringidas a Administradores.
) else (
    echo  [AVISO] Nao foi possivel restringir permissoes do config.py.
)

:: ── Instalar dependencias Python ──────────────────────────────
echo  [..] Instalando dependencias Python (pywin32)...
%PIP_CMD% install pywin32 --quiet --no-warn-script-location 2>nul
if %errorLevel% neq 0 (
    echo  [AVISO] Falha ao instalar pywin32.
    echo          O agente funcionara, mas o hook de desligamento nao estara ativo.
    echo          Instale manualmente: pip install pywin32
) else (
    echo  [OK] pywin32 instalado.
)

:: ── Ocultar pasta ProdMon ─────────────────────────────────────
attrib +h +s "%PRODMON_DIR%" >nul 2>&1

:: ── Configurar timeout de tela do Windows (powercfg) ──────────
echo  [..] Configurando tempo de espera da tela para %IDLE_MINUTES% minutos...
powercfg /change monitor-timeout-ac %IDLE_MINUTES% >nul 2>&1
powercfg /change monitor-timeout-dc %IDLE_MINUTES% >nul 2>&1
if %errorLevel% equ 0 (
    echo  [OK] Tela configurada para desligar apos %IDLE_MINUTES% min (AC e bateria^).
) else (
    echo  [AVISO] Nao foi possivel configurar o timeout de tela via powercfg.
)

:: ── Startup: registro ou launcher dependendo do autostart ─────
if /i "!AUTOSTART!" == "true" (

    :: ── Registrar no startup do Windows ──────────────────────────
    echo  [..] Registrando no startup do Windows...
    reg add "%REG_KEY%" /v "%REG_NAME%" /t REG_SZ ^
        /d "\"%PYTHONW%\" \"%PRODMON_DIR%\prodmon_agent.py\"" /f >nul
    if %errorLevel% neq 0 (
        echo  [ERRO] Falha ao registrar no startup.
        pause & exit /b 1
    )
    echo  [OK] Registrado: HKLM\...\Run\%REG_NAME%
    echo  [OK] O agente sera iniciado automaticamente em cada login do Windows.

) else (

    :: ── Remover entrada de startup se existia ────────────────────
    reg delete "%REG_KEY%" /v "%REG_NAME%" /f >nul 2>&1

    :: ── Criar launcher VBS (inicio silencioso sem terminal) ──────
    echo  [..] Criando launcher start_prodmon.vbs...
    (
        echo Set oShell = CreateObject^("WScript.Shell"^)
        echo oShell.Run """!PYTHONW!""" ^& " " ^& """!PRODMON_DIR!\prodmon_agent.py""", 0, False
    ) > "%LAUNCHER%"
    if %errorLevel% equ 0 (
        echo  [OK] Launcher criado: %LAUNCHER%
        echo  [OK] Clique duplo em start_prodmon.vbs para iniciar o agente sem terminal.
    ) else (
        echo  [AVISO] Nao foi possivel criar o launcher VBS.
    )

    :: Cria tambem um atalho na area de trabalho publica (opcional)
    set "DESKTOP_LINK=%PUBLIC%\Desktop\Iniciar ProdMon.vbs"
    copy /Y "%LAUNCHER%" "%DESKTOP_LINK%" >nul 2>&1
    if %errorLevel% equ 0 (
        echo  [OK] Atalho criado na area de trabalho: "Iniciar ProdMon.vbs"
    )

)

if "%INSTALL_AGENT%"=="true" (
    :: ── Iniciar agente imediatamente ──────────────────────────────────
    echo  [..] Iniciando agente...
    start "" /D "%PRODMON_DIR%" "%PYTHONW%" "%PRODMON_DIR%\prodmon_agent.py"
    timeout /t 2 >nul
    echo  [OK] Agente rodando silenciosamente.
)

if "%INSTALL_DASHBOARD%"=="true" (
    :: ── Criar script de execucao do Dashboard ─────────────────────
    echo  [..] Criando atalhos do Dashboard...
    set "VBS_DASH=%PRODMON_DIR%\start_dashboard.vbs"
    echo Set WshShell = CreateObject^("WScript.Shell"^) > "!VBS_DASH!"
    :: --server.address=127.0.0.1 restringe acesso ao localhost (segurança: evita exposicao na rede)
    echo WshShell.Run "cmd.exe /c cd /d """%PRODMON_DIR%\dashboard""" ^& pip install -r requirements.txt ^& streamlit run app.py --server.address=127.0.0.1 --server.headless=true", 0, False >> "!VBS_DASH!"

    set "LNK_DASH_DESKTOP=%PUBLIC%\Desktop\Abrir Dashboard ProdMon.lnk"
    powershell -NoProfile -Command "$wshell = New-Object -ComObject WScript.Shell; $shortcut = $wshell.CreateShortcut('!LNK_DASH_DESKTOP!'); $shortcut.TargetPath = '!VBS_DASH!'; $shortcut.WorkingDirectory = '%PRODMON_DIR%'; $shortcut.Description = 'Abre o painel de BI do ProdMon'; $shortcut.Save()" >nul 2>&1
    
    echo  [OK] Atalho criado: Área de Trabalho Publica -> Abrir Dashboard ProdMon
)

:: ── Verificacao final e Ocultar pasta ─────────────────────────
echo.
echo  ============================================================
echo   Instalacao %INSTALL_MODE_TXT% Concluida com Sucesso
echo   ============================================================
echo   Pasta base    : %PRODMON_DIR%
echo   Configuracoes : %PRODMON_DIR%\config.py (Operador: %OPERATOR_NAME%)
echo   Python local  : %PYTHONW%

if "%INSTALL_AGENT%"=="true" (
    echo.
    echo   [X] Agente (Rastreador) Instalado e em Execucao.
    if "!AUTOSTART!"=="true" (
        echo       Configurado para iniciar com o Windows (autostart).
    ) else (
        echo       Autostart desativado. Use atalho 'Iniciar ProdMon' na area de trabalho.
    )
)

if "%INSTALL_DASHBOARD%"=="true" (
    echo.
    echo   [X] Dashboard (BI) Instalado.
    echo       Use o atalho 'Abrir Dashboard ProdMon' na area de trabalho.
    echo       (O primeiro uso pode demorar um pouco para instalar dependencias)
)

echo.
echo   PROXIMO PASSO: Edite o config.py e defina o caminho
echo   de rede correto em "network_dir"
echo.
pause
exit /b 0
