@echo off
setlocal EnableDelayedExpansion

:: ============================================================
::  ProdMon - Preparar Maquina (Bootstrap)
::  Execute como Administrador em maquinas SEM Python
::
::  O que este script faz automaticamente:
::  1. Verifica se ja tem Python instalado
::  2. Se nao tiver, baixa e instala Python 3.11 silenciosamente
::  3. Copia o instalador para C:\Temp\ProdMonInstall (evita bloqueio de rede)
::  4. Executa o install.bat automaticamente
:: ============================================================

echo.
echo  ============================================================
echo   ProdMon - Preparacao da Maquina
echo  ============================================================
echo   Este script instala Python (se necessario) e prepara
echo   a maquina para receber o agente ProdMon.
echo  ============================================================
echo.

:: ── Verificar privilegios de administrador ────────────────────
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo  [ERRO] Execute com botao direito ^> "Executar como administrador"
    pause & exit /b 1
)
echo  [OK] Executando como Administrador.

:: ── Verificar se Python ja esta instalado ────────────────────
set "PYTHONW="
for /f "delims=" %%i in ('where pythonw.exe 2^>nul') do (
    if not defined PYTHONW set "PYTHONW=%%i"
)

if defined PYTHONW (
    echo  [OK] Python ja instalado: !PYTHONW!
    goto :python_ok
)

:: ── Python nao encontrado: tentar instalar automaticamente ────
echo  [..] Python nao encontrado. Iniciando download...
echo       (Aguarde, pode demorar alguns minutos dependendo da internet)
echo.

set "PY_INSTALLER=C:\Temp\python_installer.exe"
set "PY_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"

:: Criar pasta temporaria
if not exist "C:\Temp" mkdir "C:\Temp" 2>nul

:: Tentar download com PowerShell
powershell -NoProfile -Command ^
  "try { (New-Object Net.WebClient).DownloadFile('%PY_URL%', '%PY_INSTALLER%'); Write-Host 'Download OK' } catch { Write-Host 'ERRO:' $_.Exception.Message; exit 1 }"

if %errorLevel% neq 0 (
    echo.
    echo  [ERRO] Nao foi possivel baixar o Python automaticamente.
    echo.
    echo  Por favor, instale manualmente:
    echo    1. Abra o navegador e acesse: https://www.python.org/downloads/
    echo    2. Baixe o Python 3.11 (ou superior) para Windows 64-bit
    echo    3. Na instalacao, MARQUE a opcao "Add Python to PATH"
    echo    4. Apos instalar, reinicie o computador
    echo    5. Execute este script novamente
    echo.
    pause & exit /b 1
)

echo  [OK] Download concluido. Instalando Python (modo silencioso)...

:: Instalar Python silenciosamente com todas as opcoes necessarias
"%PY_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1 Include_test=0

if %errorLevel% neq 0 (
    echo  [AVISO] Instalador retornou codigo %errorLevel%.
    echo          Tentando verificar se a instalacao foi bem-sucedida...
)

:: Atualizar PATH da sessao atual
for /f "delims=" %%i in ('where pythonw.exe 2^>nul') do (
    if not defined PYTHONW set "PYTHONW=%%i"
)

:: Se nao achou no PATH ainda, procurar nos locais padrao
if not defined PYTHONW (
    for %%p in (
        "C:\Program Files\Python311\pythonw.exe"
        "C:\Program Files\Python312\pythonw.exe"
        "C:\Program Files\Python313\pythonw.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
    ) do (
        if exist %%p (
            if not defined PYTHONW set "PYTHONW=%%~p"
        )
    )
)

if not defined PYTHONW (
    echo.
    echo  [ERRO] Python foi instalado mas nao foi encontrado no PATH.
    echo         Reinicie o computador e execute este script novamente.
    echo.
    del /f /q "%PY_INSTALLER%" 2>nul
    pause & exit /b 1
)

echo  [OK] Python instalado com sucesso: !PYTHONW!
del /f /q "%PY_INSTALLER%" 2>nul

:python_ok
echo.

:: ── Copiar instalador para pasta local (evita bloqueio de rede) ───
echo  [..] Copiando arquivos para C:\Temp\ProdMonInstall...
echo       (Necessario pois scripts de pasta de rede podem ser bloqueados)

set "LOCAL_INSTALL=C:\Temp\ProdMonInstall"
if exist "!LOCAL_INSTALL!" rmdir /s /q "!LOCAL_INSTALL!" 2>nul
mkdir "!LOCAL_INSTALL!" 2>nul

:: Copiar tudo desta pasta para o local temporario
robocopy "%~dp0" "!LOCAL_INSTALL!" /E /XD ".git" "dashboard_env" "__pycache__" /XF "preparar_maquina.bat" /NJH /NJS /NDL >nul 2>&1

echo  [OK] Arquivos copiados para !LOCAL_INSTALL!

:: ── Executar o install.bat a partir da pasta local ────────────
echo.
echo  [..] Iniciando o instalador ProdMon...
echo  ============================================================
echo.

:: Passa o controle para o install.bat local
call "!LOCAL_INSTALL!\install.bat"
set "INSTALL_RESULT=%errorLevel%"

echo.
echo  ============================================================

if %INSTALL_RESULT% equ 0 (
    echo   Instalacao concluida com sucesso!
) else (
    echo   Instalacao finalizada com codigo: %INSTALL_RESULT%
)

:: Limpar pasta temporaria
echo  [..] Limpando arquivos temporarios...
rmdir /s /q "!LOCAL_INSTALL!" 2>nul
echo  [OK] Limpeza concluida.
echo  ============================================================
echo.
pause
exit /b %INSTALL_RESULT%
