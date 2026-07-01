#!/usr/bin/env bash
# ============================================================
# TheWatcher - abre o painel web local (Flask). Equivalente ao abrir_painel.bat.
# O painel escuta em 127.0.0.1:8765 (so localhost).
#
# Num servidor sem interface grafica, acesse pela sua maquina com um tunel SSH:
#   ssh -L 8765:127.0.0.1:8765 usuario@servidor
# e abra http://127.0.0.1:8765 no navegador local.
#
# Esta janela precisa ficar aberta enquanto o painel estiver em uso (Ctrl+C sai).
# ============================================================
set -euo pipefail

TZ_NAME="America/Sao_Paulo"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export TZ="${TZ:-$TZ_NAME}"
export LANG="${LANG:-C.UTF-8}"

echo "Subindo o painel do TheWatcher em http://127.0.0.1:8765/ (Ctrl+C encerra)"
exec "$DIR/.venv/bin/python" -m watcher panel "$@"
