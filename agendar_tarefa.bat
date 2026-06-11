@echo off
rem ============================================================
rem TheWatcher - cria a tarefa agendada no Windows Task Scheduler
rem
rem  Horario: segunda a sexta, das 07:00 a meia-noite, a cada 1 hora
rem  Conta:   SYSTEM -> roda LOGADA OU NAO, SEM precisar de senha.
rem
rem  COMO USAR: clique com o BOTAO DIREITO neste arquivo e escolha
rem             "Executar como administrador". NAO pede senha.
rem             A JANELA FICA ABERTA no final (mostra sucesso ou erro)
rem             - so fecha quando voce apertar uma tecla.
rem ============================================================

rem --- auto-eleva para administrador ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Solicitando privilegios de administrador...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

rem --- elevado: executa o agendador em PowerShell ---
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_agendar.ps1"

echo.
echo ------------------------------------------------------------
echo (Esta janela ficou aberta de proposito. Leia a mensagem
echo  acima. Pressione uma tecla para fechar.)
pause >nul
