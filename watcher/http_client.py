"""Sessão HTTP compartilhada: UA de navegador, TLS via cert store do
Windows (sites gov.br) e retries."""
from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Sites gov.br (ex.: balanca.economia.gov.br) têm cadeia TLS incompleta para
# o bundle do certifi; o truststore usa o repositório de certificados do
# próprio Windows, que resolve.
try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001 - sem truststore o resto ainda funciona
    pass

DEFAULT_TIMEOUT = 30


def make_session(global_cfg: dict) -> requests.Session:
    http_cfg = global_cfg.get("http", {})
    session = requests.Session()
    session.headers.update({
        "User-Agent": http_cfg.get("user_agent", "Mozilla/5.0"),
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    })
    retry = Retry(
        total=int(http_cfg.get("retries", 2)),
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD", "POST"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.request_timeout = int(http_cfg.get("timeout_seconds", DEFAULT_TIMEOUT))
    return session


def get(session: requests.Session, url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", getattr(session, "request_timeout", DEFAULT_TIMEOUT))
    resp = session.get(url, **kwargs)
    resp.raise_for_status()
    return resp


def post(session: requests.Session, url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", getattr(session, "request_timeout", DEFAULT_TIMEOUT))
    resp = session.post(url, **kwargs)
    resp.raise_for_status()
    return resp
