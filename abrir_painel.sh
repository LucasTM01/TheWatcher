#!/usr/bin/env bash
# ============================================================
# TheWatcher - abre o painel web local (Flask). Equivalente ao abrir_painel.bat.
#
# Por padrao o painel escuta so em 127.0.0.1:8765 (host da maquina). Num
# servidor sem interface grafica, acesse pela sua maquina com um tunel SSH:
#   ssh -L 8765:127.0.0.1:8765 usuario@servidor
# e abra http://127.0.0.1:8765 no navegador local.
#
# Para acessar direto pela rede local, sem tunel, defina "host: 0.0.0.0" em
# config/global.yaml (secao panel) — o painel nao tem login, entao so faca
# isso em rede domestica/confiavel.
#
# Esta janela precisa ficar aberta enquanto o painel estiver em uso (Ctrl+C sai).
# ============================================================
set -euo pipefail

TZ_NAME="America/Sao_Paulo"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export TZ="${TZ:-$TZ_NAME}"
export LANG="${LANG:-C.UTF-8}"

echo "Subindo o painel do TheWatcher... (Ctrl+C encerra)"
exec "$DIR/.venv/bin/python" -m watcher panel "$@"
