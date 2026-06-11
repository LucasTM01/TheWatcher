"""Fenabrave — emplacamentos mensais.

Página ASP.NET renderizada no servidor. Os relatórios mensais ficam em
fenabrave.org.br/portal/files/AAAA_MM_NN.pdf (o NN=02 é o relatório de
emplacamentos). Chave do item = (ano, mês).
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from .. import http_client
from .base import MONTH_NAMES_PT, Publication, soup

_PDF_RE = re.compile(r"/portal/files/(\d{4})_(\d{2})_(\d+)\.pdf", re.IGNORECASE)


def fetch(session, cfg, gcfg) -> list[Publication]:
    url = cfg["params"]["url"]
    resp = http_client.get(session, url)
    page = soup(resp.text)

    candidates: dict[str, dict[int, str]] = {}
    for a in page.find_all("a", href=True):
        m = _PDF_RE.search(a["href"])
        if not m:
            continue
        year, month, doc_n = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not (1 <= month <= 12) or year < 2000:
            continue
        key = f"{year}-{month:02d}"
        candidates.setdefault(key, {})[doc_n] = urljoin(resp.url, a["href"])

    pubs: list[Publication] = []
    for key in sorted(candidates, reverse=True):
        year, month = int(key[:4]), int(key[5:7])
        docs = candidates[key]
        pdf = docs.get(2) or docs[min(docs)]  # prefere o relatório _02
        pubs.append(Publication(
            item_key=key,
            title=f"Emplacamentos — {MONTH_NAMES_PT[month]}/{year}",
            url=pdf,
            date_text=f"{MONTH_NAMES_PT[month]}/{year}",
            preview="Relatório mensal de emplacamentos Fenabrave disponível.",
        ))

    if not pubs:
        raise RuntimeError("nenhum relatório encontrado — layout da página mudou?")
    return pubs
