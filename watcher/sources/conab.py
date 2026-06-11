"""CONAB — Boletim Logístico e Boletim da Safra de Grãos.

Um submódulo com dois alvos internos (decisão do usuário); cada boletim
novo gera o próprio alerta. Páginas gov.br (Plone) renderizadas no servidor:
  logistico: PDFs .../boletim-logistico-<mes>-<ano>.pdf/@@download/file
  graos:     páginas .../<N>o-levantamento-safra-AAAA-AA/...
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from .. import http_client
from .base import Publication, clean_text, soup

_LOGISTICO_RE = re.compile(r"/boletim-logistico[^\"']*?(@@download/file|\.pdf)", re.IGNORECASE)
_GRAOS_RE = re.compile(r"/(\d{1,2})o-levantamento-safra-(\d{4})-(\d{2})", re.IGNORECASE)


def fetch(session, cfg, gcfg) -> list[Publication]:
    targets: dict = cfg["params"]["targets"]
    pubs: list[Publication] = []
    errors: list[str] = []

    for target_id, tcfg in targets.items():
        try:
            if target_id == "logistico":
                pubs.extend(_fetch_logistico(session, target_id, tcfg))
            elif target_id == "graos":
                pubs.extend(_fetch_graos(session, target_id, tcfg))
            else:
                errors.append(f"alvo desconhecido: {target_id}")
        except Exception as exc:  # noqa: BLE001 — um boletim não derruba o outro
            errors.append(f"{target_id}: {type(exc).__name__}: {exc}")

    if not pubs:
        raise RuntimeError("; ".join(errors) or "nenhum boletim encontrado")
    if errors:
        # novidade de um alvo ainda vale; o erro do outro fica registrado
        pubs[0].preview += f" [aviso: falha no outro alvo — {'; '.join(errors)}]"
    return pubs


def _canonical_path(full_url: str) -> str:
    """Mesmo boletim aparece como .../view e .../@@download/file —
    normaliza para uma chave única por publicação."""
    path = urlparse(full_url).path.lower().rstrip("/")
    for suffix in ("/@@download/file", "/@@download", "/view", "/file"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
    return path


def _fetch_logistico(session, target_id, tcfg) -> list[Publication]:
    resp = http_client.get(session, tcfg["url"])
    page = soup(resp.text)
    pubs, seen = [], set()
    for a in page.find_all("a", href=True):
        if not _LOGISTICO_RE.search(a["href"]):
            continue
        full = urljoin(resp.url, a["href"])
        key = _canonical_path(full)
        if key in seen:
            continue
        seen.add(key)
        label = clean_text(a.get_text()) or "Boletim Logístico"
        label = re.sub(r"\.pdf$", "", label, flags=re.IGNORECASE)
        if not re.search(r"(?i)log[íi]stico", label):
            label = f"Boletim Logístico — {label}"
        pubs.append(Publication(
            item_key=key,
            target=target_id,
            title=label,
            url=full,
            preview=f"Novo {tcfg.get('nome', 'boletim')} publicado pela CONAB.",
        ))
    if not pubs:
        raise RuntimeError("nenhum PDF do Boletim Logístico encontrado")
    return pubs


def _fetch_graos(session, target_id, tcfg) -> list[Publication]:
    resp = http_client.get(session, tcfg["url"])
    page = soup(resp.text)
    pubs, seen = [], set()
    for a in page.find_all("a", href=True):
        m = _GRAOS_RE.search(a["href"])
        if not m:
            continue
        n, y1, y2 = int(m.group(1)), m.group(2), m.group(3)
        key = f"{n}o-levantamento-{y1}-{y2}"
        if key in seen:
            continue
        seen.add(key)
        text = clean_text(a.get_text())
        title = (text if re.search(r"(?i)levantamento", text)
                 else f"Boletim da Safra de Grãos — {n}º Levantamento, Safra {y1}/{y2}")
        pubs.append(Publication(
            item_key=key,
            target=target_id,
            title=title,
            url=urljoin(resp.url, a["href"]),
            preview=f"Novo levantamento da safra de grãos publicado pela CONAB "
                    f"({n}º levantamento, safra {y1}/{y2}).",
        ))
    if not pubs:
        raise RuntimeError("nenhum levantamento da safra encontrado")
    return pubs


def base_url(cfg, pub=None) -> str:
    targets = cfg["params"]["targets"]
    if pub is not None and pub.target in targets:
        return targets[pub.target]["url"]
    return next(iter(targets.values()))["url"]
