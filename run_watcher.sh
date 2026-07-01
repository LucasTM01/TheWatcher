#!/usr/bin/env bash
# ============================================================
# TheWatcher - motor headless (alvo do cron no Ubuntu/Linux).
# Roda um ciclo de checagens e encerra. Equivalente ao run_watcher.bat.
# Logs em data/logs/watcher.log e no painel (aba Logs).
#
# Aceita os mesmos argumentos do "watcher run", ex.:
#   bash run_watcher.sh --dry-run
#   bash run_watcher.sh --source cvm
# ============================================================
set -euo pipefail

# Fuso horario do processo. As janelas/throttle usam datetime.now() (horario
# local), entao fixamos BRT para o resultado nao depender do fuso do servidor.
# Troque para o seu fuso se quiser usar o horario local da maquina.
TZ_NAME="America/Sao_Paulo"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export TZ="${TZ:-$TZ_NAME}"
export LANG="${LANG:-C.UTF-8}"

exec "$DIR/.venv/bin/python" -m watcher run "$@"
