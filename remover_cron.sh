#!/usr/bin/env bash
# ============================================================
# TheWatcher - remove o agendamento do cron (Ubuntu/Linux).
# Equivalente ao remover_tarefa.bat do Windows.
#   bash remover_cron.sh
# ============================================================
set -euo pipefail

BEGIN="# >>> TheWatcher >>>"
END="# <<< TheWatcher <<<"

if ! crontab -l >/dev/null 2>&1; then
    echo "Nenhum crontab encontrado para o usuario '$(whoami)' — nada a remover."
    exit 0
fi

new="$(crontab -l 2>/dev/null | awk -v b="$BEGIN" -v e="$END" '
    $0==b {skip=1; next}
    $0==e {skip=0; next}
    !skip {print}
')"

printf '%s\n' "$new" | crontab -
echo "Pronto. O agendamento do TheWatcher foi removido do cron (se existia)."
