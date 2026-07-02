#!/usr/bin/env bash
# Diagnostico rapido do agendamento no cron (rode no servidor Ubuntu).
# Uso: bash diagnose_cron.sh   (a partir da pasta do TheWatcher)
set -uo pipefail

echo "== 1. cron instalado e ativo =="
systemctl is-active cron 2>&1 || systemctl is-active crond 2>&1
dpkg -l cron 2>/dev/null | tail -1

echo
echo "== 2. crontab do usuario '$(whoami)' =="
crontab -l 2>&1

echo
echo "== 3. fuso horario do sistema (o cron so entende CRON_TZ em versoes recentes) =="
timedatectl 2>&1 | grep -i "time zone"
date

echo
echo "== 4. data/logs/cron.log (saida capturada pelo cron) =="
tail -n 50 data/logs/cron.log 2>&1 || echo "(arquivo nao existe -- cron nunca rodou o comando)"

echo
echo "== 5. data/logs/watcher.log (log interno do motor) =="
tail -n 50 data/logs/watcher.log 2>&1 || echo "(arquivo nao existe -- o motor nunca chegou a rodar)"

echo
echo "== 6. lock travado (impediria novas execucoes)? =="
ls -la data/watcher.lock 2>&1 || echo "(sem lock -- ok)"

echo
echo "== 7. run_watcher.sh executavel + venv presente =="
ls -la run_watcher.sh
ls -la .venv/bin/python 2>&1 || echo "(venv nao encontrado -- rode instalar.sh)"

echo
echo "== 8. segredos/config presentes (sao gitignored, precisam existir no servidor) =="
ls -la .env config/global.yaml config/sources.yaml 2>&1

echo
echo "== 9. entradas do cron no syslog (confirma se o cron tentou disparar) =="
grep CRON /var/log/syslog 2>/dev/null | tail -20
journalctl -u cron --since "2 days ago" 2>/dev/null | tail -20

echo
echo "== 10. teste manual (roda um ciclo a seco agora) =="
bash run_watcher.sh --dry-run
