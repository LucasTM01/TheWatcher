"""Motor: para cada fonte ativa decide (gate), busca, compara com o
estado, envia alertas e registra tudo. Falha de uma fonte nunca derruba
as demais."""
from __future__ import annotations

import logging
import os
import time
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler

from . import config, gate
from .alerts import composer, email_sender, telegram_sender
from .http_client import make_session
from .models import (
    CheckResult,
    OUTCOME_ERROR,
    OUTCOME_RAN_NEW,
    OUTCOME_RAN_NOTHING,
    Publication,
    TRIGGER_DRYRUN,
)
from .sources import REGISTRY
from .state import State

log = logging.getLogger("watcher")

LOCK_STALE_MINUTES = 15


def setup_logging() -> None:
    if log.handlers:
        return
    config.ensure_dirs()
    log.setLevel(logging.INFO)
    fh = RotatingFileHandler(
        config.LOGS_DIR / "watcher.log", maxBytes=2_000_000, backupCount=5,
        encoding="utf-8",
    )
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    log.addHandler(sh)


# ---------------------------------------------------------------- lock

class AlreadyRunning(RuntimeError):
    pass


def _acquire_lock() -> None:
    config.ensure_dirs()
    path = config.LOCK_PATH
    if path.exists():
        try:
            age_min = (time.time() - path.stat().st_mtime) / 60
        except OSError:
            age_min = 0
        if age_min < LOCK_STALE_MINUTES:
            raise AlreadyRunning(
                f"outra execução em andamento (lock criado há {age_min:.0f} min)")
        log.warning("lock antigo (%.0f min) — assumindo execução", age_min)
        path.unlink(missing_ok=True)
    path.write_text(f"{os.getpid()} {datetime.now().isoformat()}", encoding="utf-8")


def _release_lock() -> None:
    config.LOCK_PATH.unlink(missing_ok=True)


# ---------------------------------------------------------------- run

def run_all(trigger: str, force: bool = False, only_source: str | None = None,
            resend: bool = False, dry_run: bool = False) -> list[CheckResult]:
    """Executa um ciclo de checagens. Retorna um resultado por fonte."""
    setup_logging()
    config.load_secrets()
    gcfg = config.load_global()
    sources_cfg = config.load_sources()

    if only_source and only_source not in sources_cfg:
        raise SystemExit(
            f"fonte desconhecida: {only_source!r} — disponíveis: "
            + ", ".join(sources_cfg))

    effective_trigger = TRIGGER_DRYRUN if dry_run else trigger
    results: list[CheckResult] = []

    _acquire_lock()
    try:
        with State() as state:
            session = make_session(gcfg)
            now = datetime.now()
            log.info("=== ciclo iniciado (trigger=%s force=%s dry_run=%s%s) ===",
                     trigger, force, dry_run,
                     f" source={only_source}" if only_source else "")
            for source_id, scfg in sources_cfg.items():
                if only_source and source_id != only_source:
                    continue
                explicit = only_source == source_id
                result = _run_source(
                    source_id, scfg, gcfg, state, session, now,
                    effective_trigger, force=force, explicit=explicit,
                    resend=resend, dry_run=dry_run,
                )
                results.append(result)
            log.info("=== ciclo encerrado: %s ===",
                     ", ".join(f"{r.source}={r.outcome}" for r in results) or "nada")
    finally:
        _release_lock()
    return results


def _run_source(source_id, scfg, gcfg, state, session, now, trigger, *,
                force, explicit, resend, dry_run) -> CheckResult:
    module = REGISTRY.get(source_id)
    if module is None:
        state.record_check(source_id, trigger, OUTCOME_ERROR,
                           "fonte sem implementação no registro")
        return CheckResult(source_id, OUTCOME_ERROR, "sem implementação")

    should_run, skip_outcome, reason = gate.evaluate(
        source_id, scfg, state, now, force=force, explicit=explicit)
    if not should_run:
        state.record_check(source_id, trigger, skip_outcome, reason)
        log.info("[%s] pulado: %s", source_id, reason)
        return CheckResult(source_id, skip_outcome, reason)

    # ---------------- fetch ----------------
    t0 = time.monotonic()
    try:
        pubs: list[Publication] = module.fetch(session, scfg, gcfg)
    except Exception as exc:  # noqa: BLE001 — isolamento por fonte
        duration = int((time.monotonic() - t0) * 1000)
        detail = f"{type(exc).__name__}: {exc}"
        log.error("[%s] ERRO: %s\n%s", source_id, detail, traceback.format_exc())
        state.record_check(source_id, trigger, OUTCOME_ERROR, detail, duration)
        if not dry_run:
            _maybe_notify_failure(source_id, scfg, gcfg, state, detail)
        return CheckResult(source_id, OUTCOME_ERROR, detail, duration)

    duration = int((time.monotonic() - t0) * 1000)
    pkey = gate.period_key(scfg["periodicity"], scfg["window"], now.date())

    # ---------------- diff ----------------
    seen = state.seen_keys(source_id)
    fresh = [p for p in pubs if (p.target, p.item_key) not in seen]

    # primeira execução de um alvo: registra tudo como "já visto" (baseline),
    # sem alertar — evita inundação de itens antigos
    baseline_targets = {
        t for t in {p.target for p in fresh}
        if not state.has_any_item(source_id, t)
    }
    baselined = [p for p in fresh if p.target in baseline_targets]
    new = [p for p in fresh if p.target not in baseline_targets]

    if dry_run:
        parts = []
        if baselined:
            parts.append(f"{len(baselined)} item(ns) seriam registrados como baseline")
        if new:
            parts.append("NOVO: " + "; ".join(p.title for p in new[:5]))
        detail = "[dry-run] " + ("; ".join(parts) if parts else "nada novo")
        outcome = OUTCOME_RAN_NEW if new else OUTCOME_RAN_NOTHING
        state.record_check(source_id, trigger, outcome, detail, duration, len(new))
        log.info("[%s] %s", source_id, detail)
        return CheckResult(source_id, outcome, detail, duration, len(new), new)

    # timestamp único do ciclo: itens gravados juntos compartilham o
    # first_seen e o desempate da ordenação fica na ordem de inserção
    seen_at = datetime.now().isoformat(timespec="seconds")
    for p in baselined:
        state.record_item(source_id, p, pkey, alerted=False, pending=False,
                          seen_at=seen_at)
    if baselined:
        log.info("[%s] baseline: %d item(ns) registrados sem alerta",
                 source_id, len(baselined))

    # itens de execuções anteriores cujo envio falhou
    pending = state.pending_items(source_id)
    for p in new:
        state.record_item(source_id, p, pkey, alerted=False, pending=True,
                          seen_at=seen_at)

    to_send = pending + new
    sent_count = 0
    if to_send:
        sent_count = _send_alerts(source_id, scfg, gcfg, state, module,
                                  to_send, pkey, resend=False)
    elif resend and force:
        latest = state.latest_item(source_id)
        if latest:
            _send_alerts(source_id, scfg, gcfg, state, module,
                         [latest], pkey, resend=True)

    parts = []
    if new:
        parts.append(f"{len(new)} novo(s): " + "; ".join(p.title for p in new[:5]))
    if pending:
        parts.append(f"{len(pending)} pendente(s) de execução anterior reenviado(s)")
    if baselined:
        parts.append(f"baseline de {len(baselined)} item(ns)")
    if resend and force and not to_send:
        parts.append("reenvio de teste do último item conhecido")
    detail = "; ".join(parts) if parts else "nada novo"

    outcome = OUTCOME_RAN_NEW if new else OUTCOME_RAN_NOTHING
    state.record_check(source_id, trigger, outcome, detail, duration, len(new))
    log.info("[%s] %s (%d ms)", source_id, detail, duration)
    return CheckResult(source_id, outcome, detail, duration, len(new), new)


# ---------------------------------------------------------------- envio

def _send_alerts(source_id, scfg, gcfg, state, module, pubs, pkey,
                 resend: bool) -> int:
    """Envia alertas e marca itens. Retorna nº de mensagens enviadas."""
    group_by_target = getattr(module, "GROUP_BY_TARGET", False)
    if group_by_target:
        groups: dict[str, list[Publication]] = {}
        for p in pubs:
            groups.setdefault(p.target, []).append(p)
        batches = [(label, items) for label, items in groups.items()]
    else:
        batches = [("", [p]) for p in pubs]

    sent = 0
    for label, items in batches:
        base_url = _base_url(module, scfg, items[0])
        msg = composer.compose(scfg, items, base_url, group_label=label,
                               resend=resend)
        ok = _dispatch(source_id, scfg, gcfg, state, msg,
                       target=items[0].target)
        if ok:
            sent += 1
            if not resend:
                for p in items:
                    state.mark_alerted(source_id, p.target, p.item_key)
        elif not resend:
            log.warning("[%s] todos os canais falharam — itens ficam pendentes "
                        "para nova tentativa no próximo ciclo", source_id)
    return sent


def _dispatch(source_id, scfg, gcfg, state, msg, target="") -> bool:
    """Envia pelos canais configurados. True se AO MENOS um canal entregou."""
    channels = scfg.get("channels") or []
    any_ok = False
    for channel in channels:
        try:
            if channel == "email":
                recipients = email_sender.send(gcfg, msg)
                state.record_alert(source_id, target, "email",
                                   ", ".join(recipients), msg.subject,
                                   msg.preview, "sent")
            elif channel == "telegram":
                chat_id = telegram_sender.send(gcfg, msg)
                state.record_alert(source_id, target, "telegram", chat_id,
                                   msg.subject, msg.preview, "sent")
            else:
                continue
            any_ok = True
            log.info("[%s] alerta enviado via %s: %s", source_id, channel,
                     msg.subject)
        except Exception as exc:  # noqa: BLE001
            log.error("[%s] falha no envio via %s: %s", source_id, channel, exc)
            state.record_alert(source_id, target, channel, "", msg.subject,
                               msg.preview, "failed", str(exc)[:500])
    return any_ok


def _maybe_notify_failure(source_id, scfg, gcfg, state, last_error) -> None:
    """Aviso de manutenção quando a fonte atinge N falhas consecutivas."""
    threshold = int(gcfg.get("engine", {}).get("failure_alert_after", 3) or 0)
    if threshold <= 0:
        return
    n = state.consecutive_errors(source_id)
    if n != threshold:
        return  # dispara uma única vez, exatamente ao cruzar o limiar
    msg = composer.compose_failure_notice(scfg, source_id, n, last_error)
    _dispatch(source_id, scfg, gcfg, state, msg, target="__manutencao__")


def _base_url(module, scfg, pub: Publication) -> str:
    fn = getattr(module, "base_url", None)
    if callable(fn):
        try:
            return fn(scfg, pub)
        except Exception:  # noqa: BLE001
            pass
    params = scfg.get("params") or {}
    return (params.get("url") or params.get("site_url")
            or params.get("url_template", "").replace("{ano}", str(datetime.now().year))
            or "")
