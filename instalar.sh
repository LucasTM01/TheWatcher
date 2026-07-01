#!/usr/bin/env bash
# ============================================================
# TheWatcher - instalacao no Ubuntu/Linux (rodar UMA vez, ou apos atualizar)
# Equivalente ao instalar.bat do Windows.
# Uso:  bash instalar.sh
# ============================================================
set -euo pipefail

# pasta deste script (funciona a partir de qualquer diretorio)
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERRO] python3 nao encontrado. Instale com:"
    echo "       sudo apt update && sudo apt install -y python3 python3-venv python3-pip"
    exit 1
fi

echo "=== TheWatcher: criando ambiente virtual (.venv) ==="
if [ ! -d ".venv" ]; then
    if ! python3 -m venv .venv 2>/dev/null; then
        echo "[ERRO] Falha ao criar o virtualenv. No Ubuntu, instale o modulo venv:"
        echo "       sudo apt install -y python3-venv python3-pip"
        exit 1
    fi
fi

echo "=== Instalando dependencias ==="
.venv/bin/python -m pip install --upgrade pip --quiet --disable-pip-version-check
if ! .venv/bin/python -m pip install -r requirements.txt --quiet --disable-pip-version-check; then
    echo "[ERRO] Falha ao instalar dependencias. Verifique sua conexao."
    exit 1
fi

if [ ! -f ".env" ]; then
    cp ".env.example" ".env"
    echo "Arquivo .env criado a partir do .env.example"
fi

if [ ! -f "config/global.yaml" ]; then
    cp "config/global.example.yaml" "config/global.yaml"
    echo "Arquivo config/global.yaml criado a partir do modelo"
fi

# garante que os demais scripts fiquem executaveis (o bit +x nao vem do git)
chmod +x "$DIR"/*.sh 2>/dev/null || true

echo
echo "============================================================"
echo "Instalacao concluida! Proximos passos (detalhes no README.md):"
echo "  1) Edite o arquivo .env         -> SMTP_PASSWORD e TELEGRAM_BOT_TOKEN"
echo "  2) Edite config/global.yaml     -> remetente, destinatarios e chat_id"
echo "  3) Teste sem enviar nada:          .venv/bin/python -m watcher run --dry-run"
echo "  4) Agende no cron:                 bash agendar_cron.sh"
echo "============================================================"
