@echo off
rem ============================================================
rem TheWatcher - motor headless (alvo do Windows Task Scheduler)
rem Roda um ciclo de checagens e encerra. Sem janela de interacao.
rem Logs em data\logs\watcher.log e no painel (aba Logs).
rem ============================================================
cd /d "%~dp0"
".venv\Scripts\python.exe" -m watcher run
