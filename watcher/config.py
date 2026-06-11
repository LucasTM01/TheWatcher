"""Carregamento e gravação da configuração (YAML + .env)."""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
DB_PATH = DATA_DIR / "state.db"
LOCK_PATH = DATA_DIR / "watcher.lock"

GLOBAL_YAML = CONFIG_DIR / "global.yaml"
SOURCES_YAML = CONFIG_DIR / "sources.yaml"

# Valores padrão aplicados a cada fonte (campos ausentes no YAML)
SOURCE_DEFAULTS = {
    "enabled": True,
    "display_name": "",
    "periodicity": "monthly",       # monthly | weekly | continuous
    "window": None,                 # {"start_day": int, "end_day": int} ou None
    "stop_after_hit": True,
    "min_interval_minutes": 0,
    "channels": ["email", "telegram"],
    "alert_title": "",
    "preview_chars": 300,
    "params": {},
}


def ensure_dirs() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)


def load_secrets() -> None:
    """Carrega o .env para o ambiente (idempotente)."""
    load_dotenv(PROJECT_ROOT / ".env")


def get_secret(name: str) -> str:
    return os.environ.get(name, "").strip()


def load_global() -> dict:
    with open(GLOBAL_YAML, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    return cfg


def load_sources() -> dict[str, dict]:
    with open(SOURCES_YAML, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    sources: dict[str, dict] = {}
    for source_id, scfg in raw.items():
        merged = dict(SOURCE_DEFAULTS)
        merged.update(scfg or {})
        if not merged["display_name"]:
            merged["display_name"] = source_id
        sources[source_id] = merged
    return sources


def save_global(cfg: dict) -> None:
    _dump_yaml(GLOBAL_YAML, cfg)


def save_sources(sources: dict[str, dict]) -> None:
    _dump_yaml(SOURCES_YAML, sources)


def _dump_yaml(path: Path, data: dict) -> None:
    """Grava YAML legível (sem reordenar chaves, com acentos).

    Observação: comentários do arquivo original são perdidos ao salvar
    pelo painel — o README documenta todos os campos.
    """
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True, width=100)
    tmp.replace(path)
