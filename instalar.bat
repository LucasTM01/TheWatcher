@echo off
rem ============================================================
rem TheWatcher - instalacao (rodar UMA vez, ou apos atualizar)
rem ============================================================
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao encontrado no PATH. Instale o Python 3.12+ e tente de novo.
    pause
    exit /b 1
)

echo === TheWatcher: criando ambiente virtual (.venv) ===
if not exist ".venv" python -m venv .venv

echo === Instalando dependencias ===
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet --disable-pip-version-check
".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias. Verifique sua conexao.
    pause
    exit /b 1
)

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Arquivo .env criado a partir do .env.example
)

if not exist "config\global.yaml" (
    copy "config\global.example.yaml" "config\global.yaml" >nul
    echo Arquivo config\global.yaml criado a partir do modelo
)

echo.
echo ============================================================
echo Instalacao concluida! Proximos passos (detalhes no README.md):
echo   1) Edite o arquivo .env  -^> SMTP_PASSWORD e TELEGRAM_BOT_TOKEN
echo   2) Edite config\global.yaml -^> chat_id do grupo do Telegram
echo   3) Abra o painel com abrir_painel.bat e rode "Checar tudo agora"
echo   4) Agende o run_watcher.bat no Task Scheduler (secao 6 do README)
echo ============================================================
pause
