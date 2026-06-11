"""Utilidades comuns às fontes.

Contrato de cada fonte (módulo em watcher/sources/):
    fetch(session, cfg, gcfg) -> list[Publication]
        Retorna os itens ATUALMENTE visíveis na fonte, em ordem do
        MAIS RECENTE para o mais antigo (o painel e o --resend usam a
        ordem de inserção como desempate). Não compara com estado —
        isso é papel do engine.
    base_url(cfg, pub) -> str        (opcional) link "site da fonte" no alerta
    GROUP_BY_TARGET = True           (opcional) agrupa alertas por alvo (CVM)
"""
from __future__ import annotations

import re
import unicodedata

from bs4 import BeautifulSoup

from ..models import Publication  # noqa: F401  (re-export p/ as fontes)

# Meses em português -> número (aceita abreviações tipo "Mai", "março" etc.)
_MONTHS_PT = {
    "janeiro": 1, "jan": 1, "fevereiro": 2, "fev": 2, "marco": 3, "mar": 3,
    "abril": 4, "abr": 4, "maio": 5, "mai": 5, "junho": 6, "jun": 6,
    "julho": 7, "jul": 7, "agosto": 8, "ago": 8, "setembro": 9, "set": 9,
    "outubro": 10, "out": 10, "novembro": 11, "nov": 11,
    "dezembro": 12, "dez": 12,
}
MONTH_NAMES_PT = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def month_pt_to_num(name: str) -> int | None:
    key = strip_accents((name or "").strip().lower())
    return _MONTHS_PT.get(key)


def soup(html_text: str) -> BeautifulSoup:
    return BeautifulSoup(html_text, "lxml")


def decoded_text(resp) -> str:
    """Texto da resposta com tratamento de charset ausente/errado.

    Alguns sites (ex.: Anfir) servem UTF-8 sem declarar charset; o requests
    assume ISO-8859-1 e os acentos viram mojibake. Tenta UTF-8 estrito antes
    de cair no comportamento padrão.
    """
    declared = (resp.headers.get("Content-Type") or "").lower()
    if "charset" not in declared:
        try:
            return resp.content.decode("utf-8")
        except UnicodeDecodeError:
            pass
    return resp.text


def clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()
