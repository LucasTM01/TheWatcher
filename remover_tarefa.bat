@echo off
rem ============================================================
rem TheWatcher - remove a tarefa agendada do Task Scheduler
rem
rem  COMO USAR: clique com o BOTAO DIREITO neste arquivo e escolha
rem             "Executar como administrador".
rem ============================================================

rem --- garante privilegio de administrador (auto-eleva) ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Solicitando privilegios de administrador...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo === Removendo a tarefa "TheWatcher" ===
schtasks /Delete /TN "TheWatcher" /F

echo.
echo Pronto. A tarefa foi removida (se existia).
pause
