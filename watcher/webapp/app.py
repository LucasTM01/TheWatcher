"""Painel web (Flask).

Por padrão escuta só em localhost (127.0.0.1); veja "panel.host" em
config/global.yaml para liberar acesso pela rede local (0.0.0.0).

Sobe com:  python -m watcher panel   (ou pelo abrir_painel.bat / .sh)
"""
from __future__ import annotations

import threading
import webbrowser
from datetime import datetime

import yaml
from flask import Flask, flash, redirect, render_template, request, url_for

from .. import config, engine, gate
from ..models import TRIGGER_MANUAL
from ..state import State

# estado da checagem manual em andamento (uma por vez)
_run_state = {"running": False, "label": "", "started": "", "summary": "", "error": ""}
_run_guard = threading.Lock()

OUTCOME_LABELS = {
    "ran_new": ("novidade!", "ok-new"),
    "ran_nothing": ("sem novidade", "ok"),
    "skipped_window": ("fora da janela", "skip"),
    "skipped_throttle": ("throttle", "skip"),
    "skipped_done": ("já saiu no período", "skip"),
    "disabled": ("desativada", "skip"),
    "error": ("ERRO", "err"),
}

CHANNEL_OPTIONS = ["email", "telegram"]
PERIODICITY_OPTIONS = ["monthly", "weekly", "continuous"]
PERIODICITY_LABELS = {"monthly": "mensal", "weekly": "semanal", "continuous": "contínua"}


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "thewatcher-painel-local"  # só p/ mensagens flash em localhost

    @app.template_filter("dt")
    def _fmt_dt(value):
        if not value:
            return "—"
        try:
            return datetime.fromisoformat(str(value)).strftime("%d/%m %H:%M")
        except ValueError:
            return str(value)

    @app.template_filter("outcome_label")
    def _outcome_label(value):
        return OUTCOME_LABELS.get(value, (value, ""))[0]

    @app.template_filter("outcome_class")
    def _outcome_class(value):
        return OUTCOME_LABELS.get(value, ("", ""))[1]

    # ------------------------------------------------ dashboard

    @app.route("/")
    def dashboard():
        sources = config.load_sources()
        now = datetime.now()
        rows = []
        with State() as state:
            for sid, cfg in sources.items():
                should, _, reason = gate.evaluate(sid, cfg, state, now)
                rows.append({
                    "id": sid,
                    "cfg": cfg,
                    "window_label": _window_label(cfg["window"]),
                    "last_check": state.last_check(sid),
                    "last_detection": state.last_detection(sid),
                    "would_run": should,
                    "reason": reason,
                })
        return render_template("dashboard.html", rows=rows, run=_run_state,
                               now=now)

    # ------------------------------------------------ checagem manual

    @app.route("/run", methods=["POST"])
    def run_now():
        source = request.form.get("source") or None
        if source == "all":
            source = None
        resend = request.form.get("resend") == "1"
        with _run_guard:
            if _run_state["running"]:
                flash("Já existe uma checagem em andamento — aguarde terminar.", "warn")
                return redirect(url_for("dashboard"))
            _run_state.update(running=True, error="", summary="",
                              label=source or "todas as fontes",
                              started=datetime.now().isoformat(timespec="seconds"))
        threading.Thread(target=_run_thread, args=(source, resend),
                         daemon=True).start()
        flash(f"Checagem manual iniciada ({source or 'todas as fontes'}).", "info")
        return redirect(url_for("dashboard"))

    # ------------------------------------------------ fontes

    @app.route("/toggle/<sid>", methods=["POST"])
    def toggle(sid):
        sources = config.load_sources()
        if sid not in sources:
            flash(f"Fonte desconhecida: {sid}", "warn")
            return redirect(url_for("dashboard"))
        sources[sid]["enabled"] = not sources[sid]["enabled"]
        config.save_sources(sources)
        flash(f"Fonte {sid} {'ativada' if sources[sid]['enabled'] else 'desativada'}.",
              "info")
        return redirect(url_for("dashboard"))

    @app.route("/source/<sid>", methods=["GET", "POST"])
    def source_edit(sid):
        sources = config.load_sources()
        if sid not in sources:
            flash(f"Fonte desconhecida: {sid}", "warn")
            return redirect(url_for("dashboard"))
        cfg = sources[sid]

        if request.method == "POST":
            f = request.form
            cfg["enabled"] = f.get("enabled") == "on"
            cfg["display_name"] = f.get("display_name", "").strip() or sid
            cfg["alert_title"] = f.get("alert_title", "").strip()
            if f.get("periodicity") in PERIODICITY_OPTIONS:
                cfg["periodicity"] = f["periodicity"]
            if f.get("window_enabled") == "on":
                try:
                    start = max(1, min(31, int(f.get("start_day", 1))))
                    end = max(1, min(31, int(f.get("end_day", 31))))
                    cfg["window"] = {"start_day": start, "end_day": end}
                except ValueError:
                    flash("Janela inválida — mantida a anterior.", "warn")
            else:
                cfg["window"] = None
            cfg["stop_after_hit"] = f.get("stop_after_hit") == "on"
            try:
                cfg["min_interval_minutes"] = max(0, int(f.get("min_interval_minutes", 0)))
            except ValueError:
                pass
            try:
                cfg["preview_chars"] = max(0, int(f.get("preview_chars", 300)))
            except ValueError:
                pass
            cfg["channels"] = [c for c in CHANNEL_OPTIONS if f.get(f"ch_{c}") == "on"]
            sources[sid] = cfg
            config.save_sources(sources)
            flash(f"Configuração de {cfg['display_name']} salva.", "info")
            return redirect(url_for("dashboard"))

        params_yaml = yaml.safe_dump(cfg.get("params") or {}, sort_keys=False,
                                     allow_unicode=True)
        return render_template("source_edit.html", sid=sid, cfg=cfg,
                               params_yaml=params_yaml,
                               periodicity_options=PERIODICITY_OPTIONS,
                               periodicity_labels=PERIODICITY_LABELS,
                               channel_options=CHANNEL_OPTIONS)

    # ------------------------------------------------ config global

    @app.route("/global", methods=["GET", "POST"])
    def global_edit():
        gcfg = config.load_global()
        if request.method == "POST":
            f = request.form
            email = gcfg.setdefault("email", {})
            email["smtp_host"] = f.get("smtp_host", "").strip()
            try:
                email["smtp_port"] = int(f.get("smtp_port", 465))
            except ValueError:
                pass
            email["smtp_user"] = f.get("smtp_user", "").strip()
            email["recipients"] = [r.strip() for r in
                                   f.get("recipients", "").splitlines() if r.strip()]
            gcfg.setdefault("telegram", {})["chat_id"] = f.get("chat_id", "").strip()
            http_cfg = gcfg.setdefault("http", {})
            http_cfg["user_agent"] = f.get("user_agent", "").strip()
            try:
                http_cfg["timeout_seconds"] = max(5, int(f.get("timeout_seconds", 30)))
                http_cfg["retries"] = max(0, int(f.get("retries", 2)))
            except ValueError:
                pass
            eng = gcfg.setdefault("engine", {})
            try:
                eng["failure_alert_after"] = max(0, int(f.get("failure_alert_after", 3)))
            except ValueError:
                pass
            config.save_global(gcfg)
            flash("Configuração global salva.", "info")
            return redirect(url_for("global_edit"))

        secrets_status = {
            "smtp": bool(config.get_secret("SMTP_PASSWORD")),
            "telegram": bool(config.get_secret("TELEGRAM_BOT_TOKEN")),
        }
        return render_template("global_edit.html", gcfg=gcfg,
                               secrets=secrets_status)

    # ------------------------------------------------ logs / mensagens / stats

    @app.route("/logs")
    def logs():
        source = request.args.get("source", "")
        outcome = request.args.get("outcome", "")
        with State() as state:
            checks = state.recent_checks(300, source=source, outcome=outcome)
        sources = list(config.load_sources())
        return render_template("logs.html", checks=checks, sources=sources,
                               sel_source=source, sel_outcome=outcome,
                               outcomes=list(OUTCOME_LABELS))

    @app.route("/alerts")
    def alerts():
        source = request.args.get("source", "")
        with State() as state:
            items = state.recent_alerts(200, source=source)
        sources = list(config.load_sources())
        return render_template("alerts.html", items=items, sources=sources,
                               sel_source=source)

    @app.route("/stats")
    def stats():
        with State() as state:
            data = state.stats_by_source()
            detections = {row["source"]: state.last_detection(row["source"])
                          for row in data}
        names = {sid: cfg["display_name"] for sid, cfg in config.load_sources().items()}
        return render_template("stats.html", data=data, names=names,
                               detections=detections)

    return app


def _window_label(window) -> str:
    if not window:
        return "todos os dias"
    s, e = window["start_day"], window["end_day"]
    return f"dias {s}–{e}" + (" (cruza o mês)" if s > e else "")


def _run_thread(source, resend) -> None:
    try:
        results = engine.run_all(trigger=TRIGGER_MANUAL, force=True,
                                 only_source=source, resend=resend)
        parts = []
        for r in results:
            label = OUTCOME_LABELS.get(r.outcome, (r.outcome, ""))[0]
            parts.append(f"{r.source}: {label}"
                         + (f" ({r.new_items} novo(s))" if r.new_items else ""))
        _run_state["summary"] = "; ".join(parts) or "nada executado"
    except engine.AlreadyRunning as exc:
        _run_state["error"] = str(exc)
    except SystemExit as exc:
        _run_state["error"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        _run_state["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        _run_state["running"] = False


def run_panel(port: int | None = None) -> None:
    engine.setup_logging()
    config.load_secrets()
    gcfg = config.load_global()
    panel_cfg = gcfg.get("panel", {})
    port = port or int(panel_cfg.get("port", 8765))
    host = panel_cfg.get("host") or "127.0.0.1"
    app = create_app()
    if host in ("127.0.0.1", "localhost"):
        threading.Timer(
            1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}/")).start()
    print(f"TheWatcher — painel em http://{host}:{port}/ (Ctrl+C encerra)")
    app.run(host=host, port=port, debug=False)
