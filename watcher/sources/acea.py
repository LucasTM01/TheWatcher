"""ACEA — press releases de emplacamentos na Europa.

API REST do WordPress com custom post types:
  pr-pc = "New car registrations" (mensal)
  pr-cv = "New commercial vehicle registrations" (trimestral)
Requer User-Agent de navegador (403 sem). Fallback: scrape do /nav/.
"""
from __future__ import annotations

import html as html_mod
import re

from .. import http_client
from .base import Publication, clean_text

_TARGET_NAMES = {"pc": "Carros de passeio", "cv": "Veículos comerciais"}


def fetch(session, cfg, gcfg) -> list[Publication]:
    api_base = cfg["params"]["api_base"].rstrip("/")
    targets = cfg["params"].get("targets") or ["pc", "cv"]

    pubs: list[Publication] = []
    for target in targets:
        resp = http_client.get(
            session,
            f"{api_base}/pr-{target}",
            params={"per_page": 5, "orderby": "date", "order": "desc",
                    "_fields": "id,date,link,title,excerpt,content"},
            headers={"Accept": "application/json"},
        )
        for post in resp.json():
            title = _strip_html(post.get("title", {}).get("rendered", ""))
            excerpt = _strip_html((post.get("excerpt") or {}).get("rendered", ""))
            if not excerpt:  # excerpts vêm vazios na API da ACEA
                content = _strip_html((post.get("content") or {}).get("rendered", ""))
                excerpt = content[:400]
            date_iso = (post.get("date") or "")[:10]
            date_text = "/".join(reversed(date_iso.split("-"))) if date_iso else ""
            pubs.append(Publication(
                item_key=f"{target}:{post['id']}",
                target=target,
                title=f"[{_TARGET_NAMES.get(target, target)}] {title}",
                url=post.get("link", ""),
                date_text=date_text,
                preview=excerpt,
            ))

    if not pubs:
        raise RuntimeError("API da ACEA não retornou press releases")
    return pubs


def _strip_html(s: str) -> str:
    return clean_text(html_mod.unescape(re.sub(r"<[^>]+>", " ", s or "")))


def base_url(cfg, pub=None) -> str:
    return cfg["params"].get("site_url", "https://www.acea.auto/")
