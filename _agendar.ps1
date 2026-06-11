# ============================================================
# TheWatcher - cria a tarefa agendada (chamado pelo agendar_tarefa.bat)
# Roda na conta SYSTEM -> funciona LOGADA OU NAO, sem senha.
# ============================================================
$ErrorActionPreference = 'Stop'
$taskName = 'TheWatcher'
$dir = $PSScriptRoot
$bat = Join-Path $dir 'run_watcher.bat'

Write-Host '============================================================'
Write-Host '  Agendando o TheWatcher'
Write-Host "  Programa: $bat"
Write-Host '  Horario:  seg-sex, 07:00 a meia-noite, a cada 1 hora'
Write-Host '  Conta:    SYSTEM (roda logada ou nao, sem senha)'
Write-Host '============================================================'
Write-Host ''

try {
    if (-not (Test-Path $bat)) {
        throw "Nao encontrei run_watcher.bat em $dir. Rode este arquivo de dentro da pasta do TheWatcher."
    }

    # gatilho semanal (seg-sex, 07:00) + repeticao de 1h durante 17h (ate meia-noite)
    $trigger = New-ScheduledTaskTrigger -Weekly `
        -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At 7:00am
    $trigger.Repetition = (New-ScheduledTaskTrigger -Once -At 7:00am `
        -RepetitionInterval (New-TimeSpan -Hours 1) `
        -RepetitionDuration (New-TimeSpan -Hours 17)).Repetition

    $action = New-ScheduledTaskAction -Execute $bat -WorkingDirectory $dir
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
        -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' `
        -LogonType ServiceAccount -RunLevel Highest

    Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action `
        -Settings $settings -Principal $principal -Force | Out-Null

    Write-Host 'SUCESSO! Tarefa "TheWatcher" criada.' -ForegroundColor Green
    $t = Get-ScheduledTask -TaskName $taskName
    $info = $t | Get-ScheduledTaskInfo
    Write-Host ('  Estado:           ' + $t.State)
    Write-Host ('  Roda como:        ' + $t.Principal.UserId)
    Write-Host ('  Proxima execucao: ' + $info.NextRunTime)
    Write-Host ''
    Write-Host 'Para testar agora: no Agendador de Tarefas, clique com o botao'
    Write-Host 'direito em TheWatcher -> Executar, e veja a aba Logs do painel.'
}
catch {
    Write-Host ''
    Write-Host '*** ERRO ao criar a tarefa ***' -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ''
    Write-Host 'Se persistir, crie pela interface grafica (Opcao C do README, secao 6).'
}
