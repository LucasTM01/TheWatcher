@echo off
rem ============================================================
rem TheWatcher - abre o painel web local
rem O navegador abre sozinho. Esta janela precisa ficar aberta
rem enquanto o painel estiver em uso (Ctrl+C ou fechar p/ sair).
rem ============================================================
cd /d "%~dp0"
echo Subindo o painel do TheWatcher... o navegador abrira sozinho.
".venv\Scripts\python.exe" -m watcher panel
pause
