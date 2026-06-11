"""Anfir — dados do setor (implementos rodoviários).

Página PHP estática com seleção de ano via ?selAno=AAAA. O ano corrente é
parametrizado automaticamente; em janeiro/fevereiro o ano anterior também
é consultado (o dado de dezembro sai no ano seguinte). PDFs cumulativos em
ADM/VIEW/ARQUIVO/ESTATISTICA/<timestamp>-Desempenho_*.pdf.
Requer User-Agent de navegador (403 sem).
"""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin

from .. import http_client
from .base import Publication, clean_text, decoded_text, soup

_DATA_RE = re.compile(r"ADM/VIEW/ARQUIVO/ESTATISTICA/[^\"']+\.pdf", re.IGNORECASE)


def fetch(session, cfg, gcfg) -> list[Publication]:
    template = cfg["params"]["url_template"]
    today = date.today()
    years = [today.year]
    if today.month <= 2:
        years.append(today.year - 1)

    pubs: list[Publication] = []
    seen_keys: set[str] = set()
    for year in years:
        url = template.format(ano=year)
        resp = http_client.get(session, url)
        page = soup(decoded_text(resp))
        for a in page.find_all("a", href=True):
            href = a["href"]
            if not _DATA_RE.search(href):
                continue
            key = href.rsplit("/", 1)[-1]
            if key in seen_keys:
                continue
            seen_keys.add(key)
            title = clean_text(a.get_text()) or key
            pubs.append(Publication(
                item_key=key,
                title=title,
                url=urljoin(resp.url, href),
                date_text=str(year),
                preview=f"Novo arquivo de dados do setor publicado pela Anfir ({title}).",
            ))

    if not pubs:
        raise RuntimeError("nenhum arquivo de dados encontrado — layout/ano mudou?")
    pubs.reverse()  # página lista do mais antigo para o mais novo
    return pubs


def base_url(cfg, pub=None) -> str:
    return cfg["params"]["url_template"].format(ano=date.today().year)
