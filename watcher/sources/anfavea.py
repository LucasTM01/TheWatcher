"""Anfavea — materiais da coletiva de imprensa mensal.

Página WordPress estática com PPT/release/estatísticas por mês, em
wp-content/uploads/AAAA/MM/... . Chave do item = mês da coletiva
(pasta de upload), que coincide com a janela de checagem 2–15.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from .. import http_client
from .base import MONTH_NAMES_PT, Publication, clean_text, soup

_UPLOAD_RE = re.compile(r"/wp-content/uploads/(\d{4})/(\d{2})/", re.IGNORECASE)
_MATERIAL_RE = re.compile(r"(?i)apresenta|release|estat[ií]st|coletiva")


def fetch(session, cfg, gcfg) -> list[Publication]:
    url = cfg["params"]["url"]
    resp = http_client.get(session, url)
    page = soup(resp.text)

    months: dict[str, dict] = {}
    for a in page.find_all("a", href=True):
        href = a["href"]
        text = clean_text(a.get_text())
        m = _UPLOAD_RE.search(href)
        if not m:
            continue
        if not (_MATERIAL_RE.search(text) or _MATERIAL_RE.search(href)):
            continue
        year, month = int(m.group(1)), int(m.group(2))
        if not (1 <= month <= 12) or year < 2000:
            continue
        key = f"{year}-{month:02d}"
        info = months.setdefault(key, {"materials": [], "url": href})
        if text:
            info["materials"].append(text)
        # o link principal do alerta: prefere o press release
        if re.search(r"(?i)release", text) or re.search(r"(?i)release", href):
            info["url"] = href

    pubs: list[Publication] = []
    for key in sorted(months, reverse=True):
        year, month = int(key[:4]), int(key[5:7])
        info = months[key]
        materials = ", ".join(dict.fromkeys(info["materials"])) or "materiais da coletiva"
        pubs.append(Publication(
            item_key=key,
            title=f"Coletiva de imprensa — {MONTH_NAMES_PT[month]}/{year}",
            url=urljoin(resp.url, info["url"]),
            date_text=f"{MONTH_NAMES_PT[month]}/{year}",
            preview=f"Materiais disponíveis: {materials}.",
        ))

    if not pubs:
        raise RuntimeError("nenhum material de coletiva encontrado — layout mudou?")
    return pubs
