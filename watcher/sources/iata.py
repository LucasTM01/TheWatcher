"""IATA — Air Passenger / Air Cargo Market Analysis (mensais).

A listagem da economics-library é renderizada no servidor (verificado);
os itens têm URLs previsíveis:
  /en/iata-repository/publications/economic-reports/air-passenger-market-analysis-<mes>-<ano>/
  /en/iata-repository/publications/economic-reports/air-cargo-market-analysis-<mes>-<ano>/
Dois alvos (passenger/cargo), cada um com "parar quando já saiu" próprio.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from .. import http_client
from .base import Publication, clean_text, soup

_REPORT_RE = re.compile(
    r"/economic-reports/(air-(passenger|cargo)-market-analysis[a-z0-9-]*)/?$",
    re.IGNORECASE,
)
_LEADING_DATE_RE = re.compile(r"^\s*(\d{2})\.(\d{2})\.(\d{4})\s*")
_MONTHS_EN = {"january", "february", "march", "april", "may", "june", "july",
              "august", "september", "october", "november", "december"}


def _title_from_slug(slug: str) -> str:
    """air-passenger-market-analysis-april-2026 -> Air Passenger Market
    Analysis — April 2026 (título estável; o texto do link é poluído)."""
    words = slug.split("-")
    for i, w in enumerate(words):
        if w in _MONTHS_EN:
            head = " ".join(x.capitalize() for x in words[:i])
            tail = " ".join(x.capitalize() for x in words[i:])
            return f"{head} — {tail}"
    return " ".join(x.capitalize() for x in words)


def fetch(session, cfg, gcfg) -> list[Publication]:
    url = cfg["params"]["url"]
    resp = http_client.get(session, url)
    page = soup(resp.text)

    pubs: list[Publication] = []
    seen: set[str] = set()
    for a in page.find_all("a", href=True):
        m = _REPORT_RE.search(a["href"].rstrip("/"))
        if not m:
            continue
        slug = m.group(1).lower()
        if slug in seen:
            continue
        seen.add(slug)
        target = m.group(2).lower()

        # o texto do link concatena "dd.mm.yyyy Título Manchete Tipo" —
        # a data vem do prefixo do PRÓPRIO link; o título, do slug
        anchor_text = clean_text(a.get_text())
        dm = _LEADING_DATE_RE.match(anchor_text)
        date_text = f"{dm.group(1)}/{dm.group(2)}/{dm.group(3)}" if dm else ""
        summary = _LEADING_DATE_RE.sub("", anchor_text)

        pubs.append(Publication(
            item_key=slug,
            target=target,
            title=_title_from_slug(slug),
            url=urljoin(resp.url, a["href"]),
            date_text=date_text,
            preview=summary,
        ))

    if not pubs:
        raise RuntimeError(
            "nenhum Market Analysis encontrado na listagem — layout mudou?")
    return pubs
