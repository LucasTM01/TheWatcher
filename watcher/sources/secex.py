"""Secex — balança comercial semanal (nota à imprensa).

Página única (~2,8 MB) regenerada a cada divulgação. A chave do item é a
data do texto "Atualizado em DD/MM/AAAA" — imune a re-render sem dado novo.

O servidor derruba conexões longas (~0,5 MB), mas aceita requisições por
faixa (Range). A página é baixada em fatias de 512 KB — cada uma em uma
conexão nova, com retry próprio — e a leitura para assim que o marcador
(mais um colchão de contexto) chega. Se o servidor ignorar Range, cai no
modo streaming. TLS gov.br depende do truststore (cert store do Windows).
"""
from __future__ import annotations

import re
import time

from requests.exceptions import ChunkedEncodingError, ConnectionError as ReqConnectionError

from .. import http_client
from .base import Publication, clean_text, soup

_UPDATED_RE = re.compile(r"Atualizado em\s*(\d{2})/(\d{2})/(\d{4})", re.IGNORECASE)
_MARKER = b"Atualizado em"
_CONTEXT_BYTES = 16_384       # quanto ler além do marcador (p/ o preview)
_RANGE_SIZE = 512 * 1024
_MAX_BYTES = 8 * 1024 * 1024  # trava de segurança
_ATTEMPTS = 3


def fetch(session, cfg, gcfg) -> list[Publication]:
    url = cfg["params"]["url"]
    text = _ranged_fetch_until_marker(session, url)
    if text is None:  # servidor sem suporte a Range
        text = _stream_until_marker(session, url)

    m = _UPDATED_RE.search(text)
    if not m:
        raise RuntimeError('texto "Atualizado em" não encontrado — layout mudou?')
    dd, mm, yyyy = m.groups()
    date_text = f"{dd}/{mm}/{yyyy}"

    # trecho de contexto a partir do marcador
    start = max(0, m.start() - 500)
    snippet = clean_text(soup(text[start: m.end() + 8000]).get_text())
    pos = snippet.lower().find("atualizado em")
    preview = snippet[pos: pos + 800] if pos >= 0 else snippet[:800]

    return [Publication(
        item_key=f"atualizado-{yyyy}-{mm}-{dd}",
        title=f"Balança comercial — dados atualizados em {date_text}",
        url=url,
        date_text=date_text,
        preview=preview,
    )]


def _decode(buf: bytearray) -> str:
    return buf.decode("utf-8", errors="replace")


def _ranged_fetch_until_marker(session, url: str) -> str | None:
    """Baixa por fatias (Range). None se o servidor não suportar Range."""
    buf = bytearray()
    total: int | None = None
    while len(buf) < _MAX_BYTES:
        start = len(buf)
        headers = {
            "Range": f"bytes={start}-{start + _RANGE_SIZE - 1}",
            "Accept-Encoding": "identity",
            "Connection": "close",
        }
        resp = _get_with_retry(session, url, headers)
        if resp is None:
            return _decode(buf) if buf.find(_MARKER) >= 0 else None
        if resp.status_code != 206:
            return None  # servidor ignorou o Range
        buf += resp.content
        cr = resp.headers.get("Content-Range", "")
        m_total = re.search(r"/(\d+)\s*$", cr)
        if m_total:
            total = int(m_total.group(1))

        pos = buf.find(_MARKER)
        done = total is not None and len(buf) >= total
        if pos >= 0 and (len(buf) - pos >= _CONTEXT_BYTES or done):
            return _decode(buf)
        if done:
            return _decode(buf)  # página inteira lida (marcador ausente -> caller decide)
    return _decode(buf)


def _get_with_retry(session, url, headers):
    for attempt in range(1, _ATTEMPTS + 1):
        try:
            return http_client.get(session, url, headers=headers)
        except (ChunkedEncodingError, ReqConnectionError):
            if attempt == _ATTEMPTS:
                return None
            time.sleep(2 * attempt)
    return None


def _stream_until_marker(session, url: str) -> str:
    """Plano B: streaming com tolerância a conexão derrubada."""
    last_exc: Exception | None = None
    for attempt in range(1, _ATTEMPTS + 1):
        buf = bytearray()
        try:
            resp = http_client.get(session, url, stream=True,
                                   headers={"Accept-Encoding": "identity"})
            try:
                marker_at = -1
                for chunk in resp.iter_content(65_536):
                    buf += chunk
                    if marker_at < 0:
                        marker_at = buf.find(_MARKER)
                    if marker_at >= 0 and len(buf) - marker_at >= _CONTEXT_BYTES:
                        break
            finally:
                resp.close()
            return _decode(buf)
        except (ChunkedEncodingError, ReqConnectionError) as exc:
            if buf.find(_MARKER) >= 0:
                return _decode(buf)
            last_exc = exc
            time.sleep(2 * attempt)
    raise last_exc if last_exc else RuntimeError("falha ao baixar a página da Secex")
