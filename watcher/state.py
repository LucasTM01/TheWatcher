"""Estado persistente em SQLite: itens vistos, log de checagens, alertas."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from . import config
from .models import OUTCOME_ERROR, OUTCOME_RAN_NEW, OUTCOME_RAN_NOTHING, TRIGGER_DRYRUN
from .models import Publication

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_items (
    source      TEXT NOT NULL,
    target      TEXT NOT NULL DEFAULT '',
    item_key    TEXT NOT NULL,
    title       TEXT DEFAULT '',
    url         TEXT DEFAULT '',
    date_text   TEXT DEFAULT '',
    preview     TEXT DEFAULT '',
    period_key  TEXT DEFAULT '',
    first_seen  TEXT NOT NULL,
    alerted     INTEGER NOT NULL DEFAULT 0,
    pending     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (source, target, item_key)
);
CREATE TABLE IF NOT EXISTS check_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    source       TEXT NOT NULL,
    trigger_kind TEXT NOT NULL,
    outcome      TEXT NOT NULL,
    detail       TEXT DEFAULT '',
    duration_ms  INTEGER DEFAULT 0,
    new_items    INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_check_runs_source_ts ON check_runs (source, ts DESC);
CREATE TABLE IF NOT EXISTS alerts (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,
    source    TEXT NOT NULL,
    target    TEXT DEFAULT '',
    channel   TEXT NOT NULL,
    recipient TEXT DEFAULT '',
    subject   TEXT DEFAULT '',
    preview   TEXT DEFAULT '',
    status    TEXT NOT NULL,
    error     TEXT DEFAULT ''
);
"""

# Outcomes que contam como "checagem efetiva" para o throttle:
# a fonte foi de fato consultada (com ou sem novidade, ou com erro).
_EFFECTIVE_OUTCOMES = (OUTCOME_RAN_NEW, OUTCOME_RAN_NOTHING, OUTCOME_ERROR)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class State:
    def __init__(self, db_path=None):
        config.ensure_dirs()
        self.conn = sqlite3.connect(str(db_path or config.DB_PATH), timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ---------------- itens vistos ----------------

    def seen_keys(self, source: str) -> set[tuple[str, str]]:
        rows = self.conn.execute(
            "SELECT target, item_key FROM seen_items WHERE source=?", (source,)
        ).fetchall()
        return {(r["target"], r["item_key"]) for r in rows}

    def has_any_item(self, source: str, target: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM seen_items WHERE source=? AND target=? LIMIT 1",
            (source, target),
        ).fetchone()
        return row is not None

    def record_item(self, source: str, pub: Publication, period_key: str,
                    alerted: bool, pending: bool, seen_at: str = "") -> None:
        # seen_at: timestamp ÚNICO do ciclo — itens gravados juntos precisam
        # compartilhar o mesmo first_seen para o desempate por rowid funcionar
        self.conn.execute(
            """INSERT OR REPLACE INTO seen_items
               (source, target, item_key, title, url, date_text, preview,
                period_key, first_seen, alerted, pending)
               VALUES (?,?,?,?,?,?,?,?,
                       COALESCE((SELECT first_seen FROM seen_items
                                 WHERE source=? AND target=? AND item_key=?), ?),
                       ?, ?)""",
            (source, pub.target, pub.item_key, pub.title, pub.url,
             pub.date_text, pub.preview, period_key,
             source, pub.target, pub.item_key, seen_at or _now(),
             1 if alerted else 0, 1 if pending else 0),
        )
        self.conn.commit()

    def mark_alerted(self, source: str, target: str, item_key: str) -> None:
        self.conn.execute(
            "UPDATE seen_items SET alerted=1, pending=0 "
            "WHERE source=? AND target=? AND item_key=?",
            (source, target, item_key),
        )
        self.conn.commit()

    def pending_items(self, source: str) -> list[Publication]:
        """Itens detectados cujo envio falhou em execuções anteriores."""
        rows = self.conn.execute(
            "SELECT * FROM seen_items WHERE source=? AND pending=1", (source,)
        ).fetchall()
        return [self._row_to_pub(r) for r in rows]

    def targets_hit_in_period(self, source: str, period_key: str) -> set[str]:
        """Alvos que já tiveram item ALERTADO no período corrente."""
        rows = self.conn.execute(
            "SELECT DISTINCT target FROM seen_items "
            "WHERE source=? AND period_key=? AND alerted=1",
            (source, period_key),
        ).fetchall()
        return {r["target"] for r in rows}

    # Itens gravados no mesmo ciclo têm o MESMO first_seen (mesmo segundo);
    # o desempate é a ordem de inserção (rowid ASC), pois as fontes retornam
    # do mais recente para o mais antigo — contrato documentado em base.py.
    _LATEST_ORDER = "ORDER BY first_seen DESC, rowid ASC LIMIT 1"

    def last_detection(self, source: str):
        row = self.conn.execute(
            f"SELECT * FROM seen_items WHERE source=? {self._LATEST_ORDER}",
            (source,),
        ).fetchone()
        return dict(row) if row else None

    def latest_item(self, source: str, target: str = None):
        """Item mais recente conhecido (para o modo --resend)."""
        if target is None:
            row = self.conn.execute(
                f"SELECT * FROM seen_items WHERE source=? {self._LATEST_ORDER}",
                (source,),
            ).fetchone()
        else:
            row = self.conn.execute(
                f"SELECT * FROM seen_items WHERE source=? AND target=? "
                f"{self._LATEST_ORDER}", (source, target),
            ).fetchone()
        return self._row_to_pub(row) if row else None

    @staticmethod
    def _row_to_pub(row) -> Publication:
        return Publication(
            item_key=row["item_key"], title=row["title"], url=row["url"],
            target=row["target"], date_text=row["date_text"],
            preview=row["preview"],
        )

    # ---------------- log de checagens ----------------

    def record_check(self, source: str, trigger_kind: str, outcome: str,
                     detail: str = "", duration_ms: int = 0,
                     new_items: int = 0) -> None:
        self.conn.execute(
            "INSERT INTO check_runs (ts, source, trigger_kind, outcome, detail,"
            " duration_ms, new_items) VALUES (?,?,?,?,?,?,?)",
            (_now(), source, trigger_kind, outcome, detail, duration_ms, new_items),
        )
        self.conn.commit()

    def last_effective_check(self, source: str) -> datetime | None:
        """Última checagem em que a fonte foi de fato consultada (p/ throttle)."""
        placeholders = ",".join("?" * len(_EFFECTIVE_OUTCOMES))
        row = self.conn.execute(
            f"SELECT ts FROM check_runs WHERE source=? AND trigger_kind != ? "
            f"AND outcome IN ({placeholders}) ORDER BY id DESC LIMIT 1",
            (source, TRIGGER_DRYRUN, *_EFFECTIVE_OUTCOMES),
        ).fetchone()
        return datetime.fromisoformat(row["ts"]) if row else None

    def consecutive_errors(self, source: str) -> int:
        """Erros consecutivos nas checagens efetivas mais recentes."""
        placeholders = ",".join("?" * len(_EFFECTIVE_OUTCOMES))
        rows = self.conn.execute(
            f"SELECT outcome FROM check_runs WHERE source=? AND trigger_kind != ? "
            f"AND outcome IN ({placeholders}) ORDER BY id DESC LIMIT 20",
            (source, TRIGGER_DRYRUN, *_EFFECTIVE_OUTCOMES),
        ).fetchall()
        count = 0
        for r in rows:
            if r["outcome"] == OUTCOME_ERROR:
                count += 1
            else:
                break
        return count

    def recent_checks(self, limit: int = 200, source: str = "",
                      outcome: str = "") -> list[dict]:
        sql = "SELECT * FROM check_runs WHERE 1=1"
        args: list = []
        if source:
            sql += " AND source=?"
            args.append(source)
        if outcome:
            sql += " AND outcome=?"
            args.append(outcome)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def last_check(self, source: str):
        row = self.conn.execute(
            "SELECT * FROM check_runs WHERE source=? ORDER BY id DESC LIMIT 1",
            (source,),
        ).fetchone()
        return dict(row) if row else None

    # ---------------- alertas ----------------

    def record_alert(self, source: str, target: str, channel: str,
                     recipient: str, subject: str, preview: str,
                     status: str, error: str = "") -> None:
        self.conn.execute(
            "INSERT INTO alerts (ts, source, target, channel, recipient, subject,"
            " preview, status, error) VALUES (?,?,?,?,?,?,?,?,?)",
            (_now(), source, target, channel, recipient, subject,
             preview, status, error),
        )
        self.conn.commit()

    def recent_alerts(self, limit: int = 200, source: str = "") -> list[dict]:
        sql = "SELECT * FROM alerts WHERE 1=1"
        args: list = []
        if source:
            sql += " AND source=?"
            args.append(source)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    # ---------------- estatísticas (painel) ----------------

    def stats_by_source(self) -> list[dict]:
        rows = self.conn.execute(
            """SELECT source,
                      COUNT(*) AS total_checks,
                      SUM(CASE WHEN outcome='ran_new' THEN 1 ELSE 0 END) AS ran_new,
                      SUM(CASE WHEN outcome='ran_nothing' THEN 1 ELSE 0 END) AS ran_nothing,
                      SUM(CASE WHEN outcome LIKE 'skipped%' OR outcome='disabled'
                               THEN 1 ELSE 0 END) AS skipped,
                      SUM(CASE WHEN outcome='error' THEN 1 ELSE 0 END) AS errors,
                      AVG(CASE WHEN outcome IN ('ran_new','ran_nothing','error')
                               THEN duration_ms END) AS avg_ms,
                      SUM(new_items) AS new_items
               FROM check_runs GROUP BY source ORDER BY source"""
        ).fetchall()
        stats = [dict(r) for r in rows]
        alerts = {
            r["source"]: r["sent"]
            for r in self.conn.execute(
                "SELECT source, SUM(CASE WHEN status='sent' THEN 1 ELSE 0 END)"
                " AS sent FROM alerts GROUP BY source"
            ).fetchall()
        }
        for s in stats:
            s["alerts_sent"] = alerts.get(s["source"], 0) or 0
            effective = (s["ran_new"] or 0) + (s["ran_nothing"] or 0) + (s["errors"] or 0)
            s["fail_rate"] = round(100.0 * (s["errors"] or 0) / effective, 1) if effective else 0.0
        return stats
