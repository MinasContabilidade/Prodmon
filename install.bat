@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
color 0A

:: ================================================================
::  ProdMon Installer v2.0
::  Instalacao Guiada - Minas Contabilidade
:: ================================================================

cls
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║          PRODMON  -  Sistema de Produtividade           ║
echo  ║                   Minas Contabilidade                   ║
echo  ║                    Instalador v2.0                      ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

:: ── Verificar privilegios de administrador ─────────────────────
net session >nul 2>&1
if %errorLevel% neq 0 (
    color 0C
    echo  [ERRO] Este instalador precisa de privilegios de Administrador.
    echo.
    echo  Feche esta janela e abra novamente com:
    echo     Botao direito no arquivo ^> "Executar como administrador"
    echo.
    pause & exit /b 1
)

echo  [OK] Executando com privilegios de Administrador.
echo.

:: ── ETAPA 1: Verificar / Instalar Python ───────────────────────
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║  ETAPA 1/5 - Verificando Python                         ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

set "PYTHONW="
for /f "delims=" %%i in ('where pythonw.exe 2^>nul') do (
    if not defined PYTHONW set "PYTHONW=%%i"
)

if defined PYTHONW (
    echo  [OK] Python ja instalado: !PYTHONW!
    goto :python_ok
)

echo  [..] Python nao encontrado nesta maquina.
echo  [..] Iniciando download e instalacao automatica do Python 3.11...
echo       (Aguarde — pode levar 2 a 5 minutos conforme a velocidade da internet)
echo.

set "PY_INSTALLER=%TEMP%\python_installer_prodmon.exe"
set "PY_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"

powershell -NoProfile -Command ^
  "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; try { $wc = New-Object Net.WebClient; $wc.DownloadFile('%PY_URL%','%PY_INSTALLER%'); Write-Host '[OK] Download concluido.' } catch { Write-Host '[ERRO] Falha no download: ' + $_.Exception.Message; exit 1 }"

if %errorLevel% neq 0 (
    color 0C
    echo.
    echo  [ERRO] Nao foi possivel baixar o Python automaticamente.
    echo.
    echo  Instale manualmente e reinicie o instalador:
    echo.
    echo    1. Abra: https://www.python.org/downloads/
    echo    2. Baixe Python 3.11 (Windows, 64-bit)
    echo    3. IMPORTANTE: Marque "Add Python to PATH" durante a instalacao
    echo    4. Apos instalar, reinicie o computador
    echo    5. Execute novamente este instalador
    echo.
    pause & exit /b 1
)

echo  [..] Instalando Python silenciosamente...
"%PY_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1 Include_test=0
del /f /q "%PY_INSTALLER%" 2>nul

:: Procurar nos locais padrao caso PATH ainda nao tenha atualizado
for %%p in (
    "C:\Program Files\Python311\pythonw.exe"
    "C:\Program Files\Python312\pythonw.exe"
    "C:\Program Files\Python313\pythonw.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
) do (
    if exist %%p if not defined PYTHONW set "PYTHONW=%%~p"
)

if not defined PYTHONW (
    color 0E
    echo  [AVISO] Python instalado, mas e necessario REINICIAR o computador.
    echo          Apos reiniciar, execute este instalador novamente.
    echo.
    pause & exit /b 0
)
echo  [OK] Python instalado: !PYTHONW!

:python_ok
echo.

:: ── ETAPA 2: Modo de instalacao ────────────────────────────────
cls
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║  ETAPA 2/5 - O que instalar nesta maquina?             ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
echo   Esta maquina sera usada para...
echo.
echo   [1] AGENTE (Funcionario)
echo       Instala o monitor de atividade silencioso neste computador.
echo       O funcionario NAO vera nenhuma janela — roda em segundo plano.
echo       Use em TODOS os computadores da equipe.
echo.
echo   [2] DASHBOARD (Gestor / RH)
echo       Instala o painel de BI para visualizar relatorios e controle
echo       de ponto. Use NO COMPUTADOR DO GESTOR ou do RH.
echo.
echo   [3] AMBOS (Agente + Dashboard)
echo       Instala os dois. Util se o proprio gestor tambem sera monitorado.
echo.

:ask_mode
set /p "INSTALL_CHOICE=  Qual opcao deseja instalar? [1]: "
if not defined INSTALL_CHOICE set "INSTALL_CHOICE=1"

set "INSTALL_AGENT=false"
set "INSTALL_DASHBOARD=false"
set "INSTALL_MODE_TXT=client"

if "%INSTALL_CHOICE%"=="1" ( set "INSTALL_AGENT=true" & set "INSTALL_MODE_TXT=client" & goto :mode_ok )
if "%INSTALL_CHOICE%"=="2" ( set "INSTALL_DASHBOARD=true" & set "INSTALL_MODE_TXT=server" & goto :mode_ok )
if "%INSTALL_CHOICE%"=="3" ( set "INSTALL_AGENT=true" & set "INSTALL_DASHBOARD=true" & set "INSTALL_MODE_TXT=both" & goto :mode_ok )

echo  [!] Opcao invalida. Digite 1, 2 ou 3.
goto :ask_mode

:mode_ok
echo  [OK] Modo selecionado: %INSTALL_MODE_TXT%

:: ── ETAPA 3: Nome do operador (se for agente) ──────────────────
if not "%INSTALL_AGENT%"=="true" (
    set "OPERATOR_NAME=Servidor"
    goto :etapa4
)

cls
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║  ETAPA 3/5 - Identificacao do Colaborador               ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
echo   Digite o nome COMPLETO da pessoa que usa este computador.
echo   Este nome aparecera nos relatorios de produtividade e no
echo   controle de ponto. Escreva exatamente como deve aparecer.
echo.
echo   Exemplos: Ana Souza  |  Carlos Mendes  |  Maria Oliveira
echo.

:ask_name
set /p "OPERATOR_NAME=  Nome do colaborador: "
if not defined OPERATOR_NAME (
    echo  [!] O nome nao pode ser vazio. Tente novamente.
    goto :ask_name
)

:: Sanitizar o nome
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

echo  [OK] Colaborador identificado: !SAFE_NAME!

:etapa4
:: ── ETAPA 4: Configuracoes avancadas (Agente) ─────────────────
if not "%INSTALL_AGENT%"=="true" goto :etapa5

cls
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║  ETAPA 4/5 - Configuracoes do Agente de Monitoramento   ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
echo  ─────────────────────────────────────────────────────────
echo   4a. INICIALIZACAO AUTOMATICA COM O WINDOWS
echo  ─────────────────────────────────────────────────────────
echo.
echo   Define se o agente sera iniciado automaticamente toda vez
echo   que o funcionario ligar o computador, sem precisar de
echo   nenhuma acao manual.
echo.
echo   [1] SIM — Iniciar com o Windows automaticamente  (RECOMENDADO)
echo             O agente comeca a monitorar desde o primeiro login.
echo.
echo   [2] NAO — Somente quando acionar manualmente
echo             Sera criado um atalho na area de trabalho para
echo             iniciar o agente manualmente quando necessario.
echo.

:ask_autostart
set /p "AUTOSTART_CHOICE=  Autostart ao ligar o PC? [1]: "
if not defined AUTOSTART_CHOICE set "AUTOSTART_CHOICE=1"
if "%AUTOSTART_CHOICE%"=="1" ( set "AUTOSTART=true" & goto :autostart_ok )
if "%AUTOSTART_CHOICE%"=="2" ( set "AUTOSTART=false" & goto :autostart_ok )
echo  [!] Digite 1 ou 2.
goto :ask_autostart
:autostart_ok
echo  [OK] Autostart: !AUTOSTART!
echo.

echo  ─────────────────────────────────────────────────────────
echo   4b. MODO DEBUG (JANELA DE ACOMPANHAMENTO)
echo  ─────────────────────────────────────────────────────────
echo.
echo   Define se o agente exibe uma pequena janela de status
echo   no canto da tela mostrando o estado atual: ATIVO / OCIOSO
echo   / BLOQUEADO e os cronometros do dia.
echo.
echo   [1] SILENCIOSO — Sem janela visivel  (RECOMENDADO para producao)
echo                    O funcionario nao sabe que esta sendo monitorado.
echo                    Use este modo ao instalar definitivamente.
echo.
echo   [2] TESTE — Exibe janela de acompanhamento ao vivo
echo               Util para testar se o agente esta funcionando
echo               corretamente antes do deploy final. O funcionario
echo               vera a janela no canto da tela.
echo.

:ask_debug
set /p "DEBUG_CHOICE=  Modo de execucao? [1]: "
if not defined DEBUG_CHOICE set "DEBUG_CHOICE=1"
if "%DEBUG_CHOICE%"=="1" ( set "DEBUG_MODE=false" & goto :debug_ok )
if "%DEBUG_CHOICE%"=="2" ( set "DEBUG_MODE=true" & goto :debug_ok )
echo  [!] Digite 1 ou 2.
goto :ask_debug
:debug_ok
echo  [OK] Modo debug: !DEBUG_MODE!
echo.

echo  ─────────────────────────────────────────────────────────
echo   4c. TEMPO DE OCIOSIDADE
echo  ─────────────────────────────────────────────────────────
echo.
echo   Quantos minutos sem mexer no mouse ou teclado para o sistema
echo   considerar que o funcionario saiu da mesa (ocioso)?
echo.
echo   Recomendado: 5 minutos (padrao ideal para a maioria dos casos)
echo   Valores menores = mais sensivel  |  Maiores = menos sensivel
echo.

:ask_idle
set /p "IDLE_MINUTES=  Tempo de ociosidade em minutos [5]: "
if not defined IDLE_MINUTES set "IDLE_MINUTES=5"

:: Verificar se e um numero valido
set "IDLE_TEST=!IDLE_MINUTES!"
for /f "delims=0123456789" %%i in ("!IDLE_TEST!") do (
    echo  [!] Digite apenas numeros (ex: 5).
    set "IDLE_MINUTES="
    goto :ask_idle
)
if !IDLE_MINUTES! LSS 1 ( echo  [!] Minimo e 1 minuto. & set "IDLE_MINUTES=" & goto :ask_idle )
if !IDLE_MINUTES! GTR 60 ( echo  [!] Maximo recomendado e 60 minutos. & set "IDLE_MINUTES=" & goto :ask_idle )
echo  [OK] Ociosidade apos: !IDLE_MINUTES! minutos

:etapa5
:: ── ETAPA 5: Confirmar e instalar ─────────────────────────────
cls
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║  ETAPA 5/5 - Resumo da Instalacao                      ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
echo   Revise as configuracoes antes de instalar:
echo.
echo   Componentes:
if "%INSTALL_AGENT%"=="true"     echo     [X] Agente de monitoramento (funcionario)
if "%INSTALL_DASHBOARD%"=="true" echo     [X] Dashboard BI (gestor / RH)
echo.
if "%INSTALL_AGENT%"=="true" (
    echo   Configuracoes do Agente:
    echo     Colaborador  : !SAFE_NAME!
    echo     Autostart    : !AUTOSTART!
    if "!DEBUG_MODE!"=="true" (
        echo     Modo         : TESTE ^(janela visivel^)
    ) else (
        echo     Modo         : SILENCIOSO ^(producao^)
    )
    echo     Ociosidade   : !IDLE_MINUTES! minutos
    echo.
)
echo   Pasta de rede  : N:\MINAS CONTABILIDADE\SISTEMA - PRODMON
echo   Pasta local    : C:\ProgramData\ProdMon
echo.

:ask_confirm
set /p "CONFIRM=  Confirmar e iniciar a instalacao? [S/N]: "
if /i "%CONFIRM%"=="S" goto :install_start
if /i "%CONFIRM%"=="N" (
    echo.
    echo  Instalacao cancelada pelo usuario.
    echo.
    pause & exit /b 0
)
echo  [!] Digite S para confirmar ou N para cancelar.
goto :ask_confirm

:install_start
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║  Instalando...                                          ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

set "PRODMON_DIR=C:\ProgramData\ProdMon"
set "SCRIPT_DIR=%~dp0"
set "REG_KEY=HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
set "REG_NAME=ProdMonAgent"
set "LAUNCHER=%PRODMON_DIR%\start_prodmon.vbs"

:: ── Criar estrutura de diretorios ─────────────────────────────
echo  [..] Criando diretorios...
for %%d in (data logs) do (
    if not exist "%PRODMON_DIR%\%%d" mkdir "%PRODMON_DIR%\%%d" 2>nul
)

:: ── Copiar arquivos ────────────────────────────────────────────
echo  [..] Copiando arquivos do agente...
if "%INSTALL_AGENT%"=="true" (
    if not exist "%SCRIPT_DIR%prodmon_agent.py" (
        color 0C
        echo  [ERRO] prodmon_agent.py nao encontrado em %SCRIPT_DIR%
        pause & exit /b 1
    )
    copy /Y "%SCRIPT_DIR%prodmon_agent.py" "%PRODMON_DIR%\prodmon_agent.py" >nul
)

if not exist "%PRODMON_DIR%\config.py" (
    copy /Y "%SCRIPT_DIR%config.py" "%PRODMON_DIR%\config.py" >nul
    echo  [OK] config.py copiado.
) else (
    echo  [OK] config.py ja existe — mantido sem alteracoes.
)

if "%INSTALL_DASHBOARD%"=="true" (
    echo  [..] Copiando Dashboard...
    if not exist "%PRODMON_DIR%\dashboard" mkdir "%PRODMON_DIR%\dashboard" 2>nul
    robocopy "%SCRIPT_DIR%dashboard" "%PRODMON_DIR%\dashboard" /E /NJH /NJS /NDL >nul 2>&1
    echo  [OK] Dashboard copiado.
)

:: ── Gravar configuracoes no config.py ─────────────────────────
echo  [..] Gravando configuracoes...
set "CFG_FILE=%PRODMON_DIR%\config.py"

powershell -NoProfile -Command "(Get-Content '!CFG_FILE!') -replace '^install_mode\s*=.*', 'install_mode = ''!INSTALL_MODE_TXT!''' | Set-Content '!CFG_FILE!'" >nul 2>&1
powershell -NoProfile -Command "(Get-Content '!CFG_FILE!') -replace '^operator_name\s*=.*', 'operator_name = ''!SAFE_NAME!''' | Set-Content '!CFG_FILE!'" >nul 2>&1

if "%INSTALL_AGENT%"=="true" (
    powershell -NoProfile -Command "(Get-Content '!CFG_FILE!') -replace '^autostart\s*=.*', 'autostart = !AUTOSTART!' | Set-Content '!CFG_FILE!'" >nul 2>&1
    powershell -NoProfile -Command "(Get-Content '!CFG_FILE!') -replace '^debug_mode\s*=.*', 'debug_mode = !DEBUG_MODE!' | Set-Content '!CFG_FILE!'" >nul 2>&1
    powershell -NoProfile -Command "(Get-Content '!CFG_FILE!') -replace '^idle_threshold_minutes\s*=.*', 'idle_threshold_minutes = !IDLE_MINUTES!' | Set-Content '!CFG_FILE!'" >nul 2>&1
)

:: ── Proteger config.py ────────────────────────────────────────
icacls "%PRODMON_DIR%\config.py" /inheritance:r /grant:r "SYSTEM:(F)" "Administrators:(F)" "BUILTIN\Users:(R)" >nul 2>&1
echo  [OK] Permissoes do config.py restringidas.

:: ── Instalar dependencias Python ──────────────────────────────
echo  [..] Instalando dependencias Python...
set "PIP_CMD="
for /f "delims=" %%i in ('where pip.exe 2^>nul') do (
    if not defined PIP_CMD set "PIP_CMD=%%i"
)
if not defined PIP_CMD set "PIP_CMD=%PYTHONW% -m pip"

if "%INSTALL_AGENT%"=="true" (
    %PIP_CMD% install pywin32 --quiet --no-warn-script-location 2>nul
    if %errorLevel% equ 0 ( echo  [OK] pywin32 instalado. ) else ( echo  [AVISO] Falha ao instalar pywin32 — hook de desligamento nao ativo. )
)

if "%INSTALL_DASHBOARD%"=="true" (
    echo  [..] Instalando dependencias do Dashboard (pode demorar)...
    if exist "%PRODMON_DIR%\dashboard\requirements.txt" (
        %PIP_CMD% install -r "%PRODMON_DIR%\dashboard\requirements.txt" --quiet --no-warn-script-location >nul 2>&1
        echo  [OK] Dependencias do Dashboard instaladas.
    )
)

:: ── Ocultar pasta ProdMon ─────────────────────────────────────
attrib +h +s "%PRODMON_DIR%" >nul 2>&1

:: ── Configurar timeout de tela ────────────────────────────────
if "%INSTALL_AGENT%"=="true" (
    echo  [..] Configurando tempo de ociosidade da tela (%IDLE_MINUTES% min)...
    powercfg /change monitor-timeout-ac %IDLE_MINUTES% >nul 2>&1
    powercfg /change monitor-timeout-dc %IDLE_MINUTES% >nul 2>&1
    echo  [OK] Tela configurada para desligar apos %IDLE_MINUTES% min.
)

:: ── Startup / Launcher ────────────────────────────────────────
if "%INSTALL_AGENT%"=="true" (
    if /i "!AUTOSTART!"=="true" (
        echo  [..] Registrando no startup do Windows...
        reg add "%REG_KEY%" /v "%REG_NAME%" /t REG_SZ /d "\"%PYTHONW%\" \"%PRODMON_DIR%\prodmon_agent.py\"" /f >nul
        if %errorLevel% equ 0 ( echo  [OK] Agente registrado no startup. ) else ( echo  [AVISO] Falha ao registrar startup. )
    ) else (
        reg delete "%REG_KEY%" /v "%REG_NAME%" /f >nul 2>&1
        echo  [..] Criando launcher start_prodmon.vbs...
        (
            echo Set oShell = CreateObject^("WScript.Shell"^)
            echo oShell.Run """!PYTHONW!""" ^& " " ^& """%PRODMON_DIR%\prodmon_agent.py""", 0, False
        ) > "%LAUNCHER%"
        copy /Y "%LAUNCHER%" "%PUBLIC%\Desktop\Iniciar ProdMon.vbs" >nul 2>&1
        echo  [OK] Atalho criado: Iniciar ProdMon.vbs na area de trabalho.
    )
)

if "%INSTALL_DASHBOARD%"=="true" (
    echo  [..] Criando atalho do Dashboard...
    set "VBS_DASH=%PRODMON_DIR%\start_dashboard.vbs"
    echo Set WshShell = CreateObject^("WScript.Shell"^) > "!VBS_DASH!"
    :: --server.address=127.0.0.1 restringe ao localhost (segurança)
    echo WshShell.Run "cmd.exe /c cd /d """%PRODMON_DIR%\dashboard""" ^& streamlit run app.py --server.address=127.0.0.1 --server.headless=true", 0, False >> "!VBS_DASH!"
    set "LNK_DASH=%PUBLIC%\Desktop\Abrir Dashboard ProdMon.lnk"
    powershell -NoProfile -Command "$ws=$env:PUBLIC+'\Desktop\Abrir Dashboard ProdMon.lnk'; $wsh=New-Object -ComObject WScript.Shell; $sc=$wsh.CreateShortcut($ws); $sc.TargetPath='%PRODMON_DIR%\start_dashboard.vbs'; $sc.Description='Abre o painel BI ProdMon'; $sc.Save()" >nul 2>&1
    echo  [OK] Atalho do Dashboard criado na area de trabalho.
)

:: ── Iniciar agente imediatamente ──────────────────────────────
if "%INSTALL_AGENT%"=="true" (
    echo  [..] Iniciando agente...
    start "" /D "%PRODMON_DIR%" "%PYTHONW%" "%PRODMON_DIR%\prodmon_agent.py"
    timeout /t 2 >nul
    echo  [OK] Agente em execucao.
)

:: ── Conclusao ─────────────────────────────────────────────────
cls
color 0A
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║              INSTALACAO CONCLUIDA COM SUCESSO!           ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
if "%INSTALL_AGENT%"=="true" (
    echo   [X] AGENTE DE MONITORAMENTO ATIVO
    echo       Colaborador : !SAFE_NAME!
    if "!AUTOSTART!"=="true" (
        echo       Status      : Rodando e configurado para iniciar com o Windows
    ) else (
        echo       Status      : Rodando agora. Use o atalho para iniciar nas proximas vezes.
    )
    if "!DEBUG_MODE!"=="true" (
        echo       Modo        : TESTE - janela de depuracao visivel na tela
    ) else (
        echo       Modo        : SILENCIOSO - invisivel para o usuario
    )
    echo.
)
if "%INSTALL_DASHBOARD%"=="true" (
    echo   [X] DASHBOARD BI INSTALADO
    echo       Use o atalho "Abrir Dashboard ProdMon" na area de trabalho.
    echo       (O primeiro acesso pode demorar alguns segundos)
    echo.
)
echo   Pasta de rede : N:\MINAS CONTABILIDADE\SISTEMA - PRODMON
echo   Pasta local   : C:\ProgramData\ProdMon
echo.
echo  ╚══════════════════════════════════════════════════════════╝
echo.
pause
exit /b 0
