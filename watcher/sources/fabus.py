"""Fabus — produção mensal das associadas.

Página WordPress estática; cada mês vira um PDF em
wp-content/uploads/AAAA/MM/<Mes><AAAA>-... .pdf (ex.: Mai2026-03A.pdf).
Chave do item = (ano, mês) parseado do nome do arquivo — imune a
re-uploads com sufixo "-1".
"""
from __future__ import annotations

import re

from .. import http_client
from .base import MONTH_NAMES_PT, Publication, clean_text, month_pt_to_num, soup

_PDF_RE = re.compile(
    r"/(Jan|Fev|Mar|Abr|Mai|Jun|Jul|Ago|Set|Out|Nov|Dez)[a-zç]*?(\d{4})[^/]*\.pdf$",
    re.IGNORECASE,
)


def fetch(session, cfg, gcfg) -> list[Publication]:
    url = cfg["params"]["url"]
    resp = http_client.get(session, url)
    page = soup(resp.text)

    by_month: dict[str, Publication] = {}
    for a in page.find_all("a", href=True):
        m = _PDF_RE.search(a["href"])
        if not m:
            continue
        month = month_pt_to_num(m.group(1))
        year = int(m.group(2))
        if not month or year < 2000:
            continue
        key = f"{year}-{month:02d}"
        if key in by_month:
            continue  # mantém o primeiro PDF do mês (pode haver variações)
        label = clean_text(a.get_text()) or MONTH_NAMES_PT[month]
        by_month[key] = Publication(
            item_key=key,
            title=f"Produção das associadas — {MONTH_NAMES_PT[month]}/{year}",
            url=a["href"],
            date_text=f"{MONTH_NAMES_PT[month]}/{year}",
            preview=f"PDF mensal de produção disponível ({label}).",
        )

    if not by_month:
        raise RuntimeError("nenhum PDF mensal encontrado — layout da página mudou?")
    # mais recentes primeiro
    return [by_month[k] for k in sorted(by_month, reverse=True)]
