#!/usr/bin/env bash
# ============================================================
# TheWatcher - agenda o motor no cron (Ubuntu/Linux).
# Equivalente ao agendar_tarefa.bat + _agendar.ps1 do Windows.
#
# Roda no cron do usuario ATUAL (nao precisa de root). Idempotente:
# pode rodar de novo para atualizar o horario sem duplicar a tarefa.
#   bash agendar_cron.sh
# ============================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---- configuracao (edite se quiser mudar horario/fuso) ----
TZ_NAME="America/Sao_Paulo"
# seg-sex, de hora em hora, das 05:00 a 01:00 (horas 0,1 e 5..23)
SCHEDULE="0 0-1,5-23 * * 1-5"
# -----------------------------------------------------------

BEGIN="# >>> TheWatcher >>>"
END="# <<< TheWatcher <<<"
CMD="/bin/bash $DIR/run_watcher.sh >> $DIR/data/logs/cron.log 2>&1"

# o cron redireciona a saida para este arquivo; a pasta precisa existir
mkdir -p "$DIR/data/logs"

# crontab atual SEM o nosso bloco antigo (se existir) — remove entre os marcadores
current="$( { crontab -l 2>/dev/null || true; } | awk -v b="$BEGIN" -v e="$END" '
    $0==b {skip=1; next}
    $0==e {skip=0; next}
    !skip {print}
')"

{
    # preserva as demais linhas do usuario
    if [ -n "$current" ]; then printf '%s\n' "$current"; fi
    # nosso bloco vai por ULTIMO para o CRON_TZ nao afetar outras tarefas
    printf '%s\n' "$BEGIN"
    printf 'CRON_TZ=%s\n' "$TZ_NAME"
    printf '%s %s\n' "$SCHEDULE" "$CMD"
    printf '%s\n' "$END"
} | crontab -

echo "============================================================"
echo "SUCESSO! TheWatcher agendado no cron do usuario '$(whoami)'."
echo "  Horario:  seg-sex, de hora em hora, das 05:00 a 01:00 ($TZ_NAME)"
echo "  Cron:     $SCHEDULE"
echo "  Programa: $DIR/run_watcher.sh"
echo "  Log cron: $DIR/data/logs/cron.log"
echo "============================================================"
echo
echo "Para testar agora, sem esperar o horario:"
echo "  bash $DIR/run_watcher.sh"
echo
echo "crontab atual:"
crontab -l
