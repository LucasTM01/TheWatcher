"""Pontos de entrada de linha de comando.

  python -m watcher run                  ciclo normal (Task Scheduler)
  python -m watcher run --force          ignora janela/throttle/já-saiu
  python -m watcher run --force --resend ... e reenvia o último item (teste)
  python -m watcher run --dry-run        detecta sem enviar nem gravar estado
  python -m watcher run --source cvm     só uma fonte
  python -m watcher list                 situação de cada fonte agora
  python -m watcher panel                sobe o painel web local
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from .models import OUTCOME_ERROR, OUTCOME_RAN_NEW, SKIP_OUTCOMES, TRIGGER_FORCED, TRIGGER_SCHEDULED


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="watcher",
                                     description="TheWatcher — monitor de divulgações")
    # padrões para quando é chamado sem subcomando (equivale a "run")
    parser.set_defaults(force=False, source=None, resend=False, dry_run=False, port=None)
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="executa um ciclo de checagens")
    p_run.add_argument("--force", action="store_true",
                       help="ignora janela, throttle e 'já saiu no período'")
    p_run.add_argument("--source", default=None,
                       help="roda apenas a fonte indicada (ex.: cvm)")
    p_run.add_argument("--resend", action="store_true",
                       help="com --force: reenvia o último item conhecido (teste)")
    p_run.add_argument("--dry-run", action="store_true",
                       help="detecta sem enviar alertas nem alterar o estado")

    sub.add_parser("list", help="mostra a situação de cada fonte agora")

    p_panel = sub.add_parser("panel", help="sobe o painel web local")
    p_panel.add_argument("--port", type=int, default=None)

    args = parser.parse_args(argv)
    command = args.command or "run"

    if command == "run":
        return _cmd_run(args)
    if command == "list":
        return _cmd_list()
    if command == "panel":
        from .webapp.app import run_panel
        run_panel(port=args.port)
        return 0
    parser.print_help()
    return 2


def _cmd_run(args) -> int:
    from . import engine

    trigger = TRIGGER_FORCED if args.force else TRIGGER_SCHEDULED
    try:
        results = engine.run_all(
            trigger=trigger, force=args.force, only_source=args.source,
            resend=args.resend, dry_run=args.dry_run,
        )
    except engine.AlreadyRunning as exc:
        print(f"abortado: {exc}")
        return 0

    print()
    print(f"{'FONTE':<12} {'RESULTADO':<18} DETALHE")
    print("-" * 76)
    errors = 0
    for r in results:
        if r.outcome == OUTCOME_ERROR:
            errors += 1
        mark = ("🔔" if r.outcome == OUTCOME_RAN_NEW
                else "·" if r.outcome in SKIP_OUTCOMES
                else "❌" if r.outcome == OUTCOME_ERROR else " ")
        detail = (r.detail or "")[:90]
        print(f"{r.source:<12} {r.outcome:<18} {mark} {detail}")
    print()
    return 1 if errors and len(results) == errors else 0


def _cmd_list() -> int:
    from . import config, gate
    from .state import State

    config.load_secrets()
    sources = config.load_sources()
    now = datetime.now()
    print(f"\nSituação em {now:%d/%m/%Y %H:%M}\n")
    print(f"{'FONTE':<12} {'ATIVA':<6} {'JANELA':<12} {'AGORA':<10} MOTIVO")
    print("-" * 90)
    with State() as state:
        for sid, cfg in sources.items():
            w = cfg["window"]
            window = f"{w['start_day']}–{w['end_day']}" if w else "todos os dias"
            should, _, reason = gate.evaluate(sid, cfg, state, now)
            print(f"{sid:<12} {'sim' if cfg['enabled'] else 'NÃO':<6} "
                  f"{window:<12} {'rodaria' if should else 'pularia':<10} {reason}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
