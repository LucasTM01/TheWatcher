"""Decide se cada submódulo deve rodar nesta invocação.

Regras, na ordem: fonte ativa? -> janela de dias -> já saiu no período?
-> throttle. O modo forçado ignora janela, throttle e "já saiu" (mas não
reativa fonte desligada, exceto quando ela é chamada explicitamente por
--source / botão do painel).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .models import (
    OUTCOME_DISABLED,
    OUTCOME_SKIPPED_DONE,
    OUTCOME_SKIPPED_THROTTLE,
    OUTCOME_SKIPPED_WINDOW,
)


def in_window(window: dict | None, today: date) -> bool:
    """Janela de dias do mês. start>end = cruza o mês (ex.: 25 -> 5)."""
    if not window:
        return True
    start, end = int(window["start_day"]), int(window["end_day"])
    day = today.day
    if start <= end:
        return start <= day <= end
    return day >= start or day <= end


def period_key(periodicity: str, window: dict | None, today: date) -> str:
    """Chave do período corrente para o "parar quando já saiu".

    monthly: ciclo ancorado no mês em que a janela COMEÇA. Para janela que
    cruza o mês (ex.: IATA 25->5), dias <= end_day pertencem ao ciclo do mês
    anterior (em 03/07 o ciclo ainda é "2026-06", iniciado em 25/06).
    weekly: semana ISO. continuous: sem período.
    """
    if periodicity == "weekly":
        iso = today.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    if periodicity == "continuous":
        return ""
    # monthly
    anchor = today
    if window:
        start, end = int(window["start_day"]), int(window["end_day"])
        if start > end and today.day <= end:
            anchor = today.replace(day=1) - timedelta(days=1)  # mês anterior
    return f"{anchor.year}-{anchor.month:02d}"


def evaluate(source_id: str, cfg: dict, state, now: datetime,
             force: bool = False, explicit: bool = False) -> tuple[bool, str, str]:
    """Retorna (deve_rodar, outcome_se_pulado, motivo_legível)."""
    today = now.date()
    pkey = period_key(cfg["periodicity"], cfg["window"], today)

    if not cfg["enabled"] and not explicit:
        return False, OUTCOME_DISABLED, "fonte desativada"

    if force or explicit:
        return True, "", "execução forçada (ignora janela/throttle/já-saiu)"

    if not in_window(cfg["window"], today):
        w = cfg["window"]
        return (False, OUTCOME_SKIPPED_WINDOW,
                f"fora da janela (dias {w['start_day']}–{w['end_day']}, hoje é dia {today.day})")

    if cfg["stop_after_hit"] and cfg["periodicity"] != "continuous":
        targets = _expected_targets(cfg)
        hit = state.targets_hit_in_period(source_id, pkey)
        if targets.issubset(hit):
            return (False, OUTCOME_SKIPPED_DONE,
                    f"já divulgado no período {pkey} — volta a checar no próximo período")

    interval = int(cfg["min_interval_minutes"] or 0)
    if interval > 0:
        last = state.last_effective_check(source_id)
        if last is not None:
            elapsed = now - last
            if elapsed < timedelta(minutes=interval):
                next_at = last + timedelta(minutes=interval)
                return (False, OUTCOME_SKIPPED_THROTTLE,
                        f"throttle de {interval} min — última checagem efetiva "
                        f"{last.strftime('%H:%M')}, próxima a partir de "
                        f"{next_at.strftime('%H:%M')}")

    return True, "", "dentro da janela e sem restrições"


def _expected_targets(cfg: dict) -> set[str]:
    """Alvos declarados da fonte ('' quando a fonte é de alvo único)."""
    params = cfg.get("params") or {}
    targets = params.get("targets")
    if isinstance(targets, dict):
        return set(targets.keys())
    if isinstance(targets, list):
        return set(targets)
    return {""}
