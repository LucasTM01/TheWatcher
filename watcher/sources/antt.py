"""ANTT — dataset Monitriip (bilhetes de passagem) no portal CKAN.

Detecção via API: um novo CSV mensal = um novo resource (id imutável) no
package_show. Mais robusto que raspar a página do dataset.
"""
from __future__ import annotations

from .. import http_client
from .base import Publication


def fetch(session, cfg, gcfg) -> list[Publication]:
    api_url = cfg["params"]["api_url"]
    resp = http_client.get(session, api_url, headers={"Accept": "application/json"})
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"API CKAN retornou success=false: {str(data)[:200]}")

    result = data["result"]
    resources = result.get("resources") or []
    if not resources:
        raise RuntimeError("dataset sem resources — verificar API/permissões")

    site_url = cfg["params"].get("site_url", api_url)
    pubs: list[Publication] = []
    # mais recentes primeiro (por data de criação)
    for r in sorted(resources, key=lambda x: x.get("created") or "", reverse=True):
        created = (r.get("created") or "")[:10]
        date_text = "/".join(reversed(created.split("-"))) if created else ""
        name = r.get("name") or r.get("id")
        pubs.append(Publication(
            item_key=r["id"],
            title=f"{name} ({r.get('format', '?')})",
            url=r.get("url") or site_url,
            date_text=date_text,
            preview=f"Novo recurso no dataset Monitriip: {name}. "
                    f"Criado em {date_text or '?'}.",
        ))
    return pubs


def base_url(cfg, pub=None) -> str:
    return cfg["params"].get("site_url", "https://dados.antt.gov.br/")
