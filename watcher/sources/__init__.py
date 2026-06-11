"""Registro das fontes. Adicionar uma fonte = criar o módulo aqui dentro,
importá-lo e registrá-lo neste dicionário (+ bloco em config/sources.yaml)."""
from __future__ import annotations

from . import acea, anfavea, anfir, antt, conab, cvm, fabus, fenabrave, iata, secex

REGISTRY = {
    "fabus": fabus,
    "fenabrave": fenabrave,
    "anfavea": anfavea,
    "acea": acea,
    "iata": iata,
    "anfir": anfir,
    "secex": secex,
    "conab": conab,
    "antt": antt,
    "cvm": cvm,
}
