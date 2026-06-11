"""CVM — documentos novos por empresa (caso especial, throttle de 2h).

Fonte primária (quase tempo real, verificada sem captcha):
  POST https://www.rad.cvm.gov.br/ENET/frmConsultaExternaCVM.aspx/ListarDocumentos
  Resposta: {"d": {"dados": "campo1$&campo2$&...&*linha2..."}} com código CVM,
  categoria, tipo, datas (entrega com hora) e nº de protocolo.

Fallback (se o ENET mudar/falhar): dataset IPE em dados.cvm.gov.br
(atualização semanal — serve para não ficar cego, com defasagem).

Alertas agrupados por empresa (GROUP_BY_TARGET).
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from datetime import date, datetime, timedelta

from .. import http_client
from .base import Publication, clean_text, strip_accents

GROUP_BY_TARGET = True

ENET_LIST_URL = ("https://www.rad.cvm.gov.br/ENET/"
                 "frmConsultaExternaCVM.aspx/ListarDocumentos")
ENET_VIEW_URL = ("https://www.rad.cvm.gov.br/ENET/"
                 "frmExibirArquivoIPEExterno.aspx?NumeroProtocoloEntrega={protocolo}")
ENET_SEARCH_PAGE = "https://www.rad.cvm.gov.br/ENET/frmConsultaExternaCVM.aspx"
IPE_DATASET_URL = ("https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/"
                   "ipe_cia_aberta_{year}.zip")

_PROTOCOLO_RE = re.compile(r"NumeroProtocoloEntrega=(\d+)")
_DOWNLOAD_RE = re.compile(r"OpenDownloadDocumentos\('?(\d+)'?,\s*'?(\d+)'?,\s*'?(\d+)'?")
_SPANORDER_RE = re.compile(r"<spanOrder>.*?</spanOrder>", re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_DATETIME_RE = re.compile(r"(\d{2}/\d{2}/\d{4})(?:\s+(\d{2}:\d{2}))?")


def fetch(session, cfg, gcfg) -> list[Publication]:
    try:
        return _fetch_enet(session, cfg)
    except Exception as primary_exc:  # noqa: BLE001
        try:
            pubs = _fetch_ipe_fallback(session, cfg)
        except Exception:  # noqa: BLE001 — reporta o erro da fonte primária
            raise primary_exc
        for p in pubs:
            p.preview += " [obtido via dataset IPE — fonte primária ENET falhou; dados podem ter defasagem]"
        return pubs


# ---------------------------------------------------------------- ENET

def _fetch_enet(session, cfg) -> list[Publication]:
    params = cfg["params"]
    lookback = int(params.get("lookback_days", 3))
    companies = _company_map(params)
    categories = _normalized_set(params.get("categories") or [])

    today = date.today()
    payload = {
        "dataDe": (today - timedelta(days=lookback)).strftime("%d/%m/%Y"),
        "dataAte": today.strftime("%d/%m/%Y"),
        "empresa": "",
        "setorAtividade": "-1",
        "categoriaEmissor": "-1",
        "situacaoEmissor": "-1",
        "tipoParticipante": "1",
        "dataReferencia": "",
        "categoria": "-1",
        "periodo": "2",
        "horaIni": "",
        "horaFim": "",
        "palavraChave": "",
        "ultimaDtRef": "false",
        "tipoEmpresa": "0",
        "token": "",
        "versaoCaptcha": "",
    }
    resp = http_client.post(
        session, ENET_LIST_URL,
        data=json.dumps(payload),
        headers={"Content-Type": "application/json; charset=UTF-8",
                 "Accept": "application/json"},
    )
    d = resp.json().get("d") or {}
    if d.get("temErro"):
        raise RuntimeError(f"ENET retornou erro: {d.get('msgErro') or '?'}")
    dados = d.get("dados") or ""
    if not dados.strip():
        return []  # nenhum documento no intervalo (raro, mas válido)

    pubs: list[Publication] = []
    for row in dados.split("&*"):
        fields = row.split("$&")
        if len(fields) < 11:
            continue
        code = _digits(fields[0])
        company_name = companies.get(code)
        if company_name is None:
            continue
        categoria = clean_text(_strip_markup(fields[2]))
        tipo = clean_text(_strip_markup(fields[3]))
        especie = clean_text(_strip_markup(fields[4]))
        data_ref = _extract_date(fields[5])
        data_entrega = _extract_date(fields[6])
        status = clean_text(_strip_markup(fields[7]))
        versao = clean_text(_strip_markup(fields[8]))
        actions = fields[10]

        if categories and _norm(categoria) not in categories:
            continue

        protocolo = None
        m = _PROTOCOLO_RE.search(actions)
        if m:
            protocolo = m.group(1)
        else:
            m = _DOWNLOAD_RE.search(actions)
            if m:
                protocolo = m.group(3)
        if not protocolo:
            continue

        title_parts = [categoria or "Documento"]
        if tipo and tipo != "-":
            title_parts.append(tipo)
        if especie and especie != "-":
            title_parts.append(especie)
        title = " — ".join(title_parts)
        if status and status.lower() != "ativo":
            title += f" [{status}]"

        preview_parts = [f"Categoria: {categoria or '?'}"]
        if tipo and tipo != "-":
            preview_parts.append(f"Tipo: {tipo}")
        if data_ref:
            preview_parts.append(f"Referência: {data_ref}")
        if data_entrega:
            preview_parts.append(f"Entrega: {data_entrega}")
        if versao:
            preview_parts.append(f"Versão: {versao}")

        pubs.append(Publication(
            item_key=protocolo,
            target=company_name,
            title=title,
            url=ENET_VIEW_URL.format(protocolo=protocolo),
            date_text=data_entrega,
            preview=" | ".join(preview_parts),
        ))
    # o ENET devolve em ordem cronológica crescente — inverte para
    # cumprir o contrato "mais recente primeiro" (ver base.py)
    pubs.sort(key=lambda p: _sort_key(p.date_text), reverse=True)
    return pubs


def _sort_key(date_text: str) -> str:
    """'10/06/2026 07:38' -> '202606100738' (ordenável)."""
    m = _DATETIME_RE.search(date_text or "")
    if not m:
        return ""
    d, mo, y = m.group(1).split("/")
    hm = (m.group(2) or "00:00").replace(":", "")
    return f"{y}{mo}{d}{hm}"


def _strip_markup(field: str) -> str:
    field = _SPANORDER_RE.sub("", field or "")
    return _TAG_RE.sub("", field)


def _extract_date(field: str) -> str:
    text = _strip_markup(field)
    m = _DATETIME_RE.search(text)
    if not m:
        return clean_text(text).strip("- ")
    return m.group(1) + (f" {m.group(2)}" if m.group(2) else "")


def _digits(s: str) -> int:
    ds = re.sub(r"\D", "", s or "")
    return int(ds) if ds else -1


def _norm(s: str) -> str:
    return strip_accents((s or "").strip().lower())


def _normalized_set(items) -> set[str]:
    return {_norm(x) for x in items if str(x).strip()}


def _company_map(params) -> dict[int, str]:
    """code (int) -> nome de exibição."""
    out: dict[int, str] = {}
    for c in params.get("companies") or []:
        out[int(c["code"])] = str(c.get("name") or c["code"]).strip()
    if not out:
        raise RuntimeError("nenhuma empresa configurada em params.companies")
    return out


# ---------------------------------------------------------------- fallback IPE

def _fetch_ipe_fallback(session, cfg) -> list[Publication]:
    """Dataset aberto da CVM (CSV anual, atualização semanal)."""
    params = cfg["params"]
    companies = _company_map(params)
    categories = _normalized_set(params.get("categories") or [])
    # janela mais larga: o dataset pode ter dias de defasagem
    cutoff = date.today() - timedelta(days=int(params.get("lookback_days", 3)) + 10)

    url = IPE_DATASET_URL.format(year=date.today().year)
    resp = http_client.get(session, url, timeout=120)
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    csv_name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))

    pubs: list[Publication] = []
    with zf.open(csv_name) as fh:
        reader = csv.DictReader(io.TextIOWrapper(fh, encoding="latin-1"),
                                delimiter=";")
        for row in reader:
            code = _digits(row.get("Codigo_CVM") or "")
            company_name = companies.get(code)
            if company_name is None:
                continue
            entrega_raw = (row.get("Data_Entrega") or "").strip()
            try:
                entrega = datetime.strptime(entrega_raw[:10], "%Y-%m-%d").date()
            except ValueError:
                continue
            if entrega < cutoff:
                continue
            categoria = (row.get("Categoria") or "").strip()
            if categories and _norm(categoria) not in categories:
                continue
            tipo = (row.get("Tipo") or "").strip()
            protocolo = (row.get("Protocolo_Entrega") or "").strip()
            link = (row.get("Link_Download") or "").strip()
            if not protocolo:
                continue
            title = categoria or "Documento"
            if tipo and tipo != "-":
                title += f" — {tipo}"
            pubs.append(Publication(
                item_key=protocolo,
                target=company_name,
                title=title,
                url=link or ENET_VIEW_URL.format(protocolo=protocolo),
                date_text="/".join(reversed(entrega_raw[:10].split("-"))),
                preview=f"Categoria: {categoria or '?'} | Entrega: {entrega_raw}",
            ))
    return pubs


def base_url(cfg, pub=None) -> str:
    return ENET_SEARCH_PAGE
