"""Montagem das mensagens (template global parametrizado por fonte).

Gera três representações da mesma informação:
  subject        -> assunto do e-mail / primeira linha
  html           -> corpo do e-mail (HTML simples, compatível com Gmail)
  telegram_html  -> texto para o Bot API com parse_mode=HTML (limite 4096)
  text           -> alternativa em texto puro (multipart do e-mail)
"""
from __future__ import annotations

import html as html_mod
from dataclasses import dataclass

from ..models import Publication

TELEGRAM_LIMIT = 4096


@dataclass
class Message:
    subject: str
    html: str
    text: str
    telegram_html: str
    preview: str  # resumo curto para o histórico


def _esc(s: str) -> str:
    return html_mod.escape(s or "", quote=False)


def _clip(s: str, n: int) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 1].rstrip() + "…"


def compose(source_cfg: dict, pubs: list[Publication], base_url: str,
            group_label: str = "", resend: bool = False) -> Message:
    """Monta a mensagem de um grupo de publicações de uma fonte.

    group_label: rótulo do agrupamento (ex.: nome da empresa na CVM).
    """
    title = source_cfg.get("alert_title") or source_cfg.get("display_name", "")
    preview_chars = int(source_cfg.get("preview_chars", 300))

    subject = title
    if group_label:
        subject = f"{title} — {group_label}: " + (
            "novo documento" if len(pubs) == 1 else f"{len(pubs)} documentos novos"
        )
    if resend:
        subject = "🔁 [REENVIO/TESTE] " + subject

    # ---------- corpo ----------
    html_items, text_items, tg_items = [], [], []
    for p in pubs:
        date_part = f" <span style='color:#777'>({_esc(p.date_text)})</span>" if p.date_text else ""
        preview = _clip(p.preview, preview_chars)
        html_items.append(
            "<div style='margin:0 0 14px 0;padding:10px 12px;background:#f6f7f9;"
            "border-left:3px solid #2b6cb0;border-radius:4px'>"
            f"<div style='font-weight:bold'>{_esc(p.title)}{date_part}</div>"
            + (f"<div style='margin:6px 0;color:#333'>{_esc(preview)}</div>" if preview else "")
            + f"<div style='margin-top:6px'><a href='{p.url}'>📄 Abrir publicação</a></div>"
            "</div>"
        )
        text_items.append(
            f"- {p.title}" + (f" ({p.date_text})" if p.date_text else "")
            + (f"\n  {preview}" if preview else "")
            + f"\n  Publicação: {p.url}"
        )
        tg_date = f" ({_esc(p.date_text)})" if p.date_text else ""
        tg_items.append(
            f"• <b>{_esc(p.title)}</b>{tg_date}"
            + (f"\n{_esc(preview)}" if preview else "")
            + f"\n<a href=\"{p.url}\">📄 Abrir publicação</a>"
        )

    header = _esc(subject if group_label else title)

    html_body = (
        "<div style='font-family:Segoe UI,Arial,sans-serif;font-size:14px;"
        "max-width:640px'>"
        f"<h2 style='margin:0 0 12px 0;font-size:17px'>{header}</h2>"
        + "".join(html_items)
        + f"<div style='margin-top:10px;color:#555'>"
          f"<a href='{base_url}'>🌐 Página da fonte</a></div>"
        "<hr style='border:none;border-top:1px solid #ddd;margin:14px 0 8px'>"
        "<div style='color:#999;font-size:12px'>TheWatcher — monitor de divulgações</div>"
        "</div>"
    )

    text_body = (
        subject + "\n\n" + "\n\n".join(text_items)
        + f"\n\nPágina da fonte: {base_url}\n\n— TheWatcher"
    )

    tg_body = f"<b>{header}</b>\n\n" + "\n\n".join(tg_items) \
              + f"\n\n<a href=\"{base_url}\">🌐 Página da fonte</a>"
    if len(tg_body) > TELEGRAM_LIMIT:
        # corta itens excedentes preservando o fechamento
        kept, used = [], len(header) + 60
        for it in tg_items:
            if used + len(it) > TELEGRAM_LIMIT - 200:
                kept.append(f"(+{len(tg_items) - len(kept)} itens — veja a página da fonte)")
                break
            kept.append(it)
            used += len(it) + 2
        tg_body = f"<b>{header}</b>\n\n" + "\n\n".join(kept) \
                  + f"\n\n<a href=\"{base_url}\">🌐 Página da fonte</a>"

    short = "; ".join(_clip(p.title, 80) for p in pubs[:3])
    return Message(subject=subject, html=html_body, text=text_body,
                   telegram_html=tg_body, preview=_clip(short, 200))


def compose_failure_notice(source_cfg: dict, source_id: str, n_errors: int,
                           last_error: str) -> Message:
    """Aviso de manutenção: fonte falhando repetidamente (≠ alerta de dado)."""
    name = source_cfg.get("display_name", source_id)
    subject = f"⚠️ TheWatcher — fonte com problema: {name}"
    body = (
        f"A fonte \"{name}\" falhou {n_errors} vezes consecutivas.\n"
        f"Último erro: {last_error}\n\n"
        "O monitoramento das demais fontes continua normal. "
        "Verifique o painel (aba Logs) — o site pode estar fora do ar "
        "ou o layout pode ter mudado."
    )
    html_body = (
        "<div style='font-family:Segoe UI,Arial,sans-serif;font-size:14px'>"
        f"<h2 style='font-size:16px'>{_esc(subject)}</h2>"
        f"<p>A fonte <b>{_esc(name)}</b> falhou <b>{n_errors}</b> vezes consecutivas.</p>"
        f"<p style='color:#a00'>Último erro: {_esc(_clip(last_error, 400))}</p>"
        "<p>O monitoramento das demais fontes continua normal. Verifique o painel "
        "(aba Logs) — o site pode estar fora do ar ou o layout pode ter mudado.</p>"
        "</div>"
    )
    tg = (f"<b>{_esc(subject)}</b>\n\nA fonte <b>{_esc(name)}</b> falhou "
          f"{n_errors} vezes consecutivas.\nÚltimo erro: {_esc(_clip(last_error, 300))}")
    return Message(subject=subject, html=html_body, text=body,
                   telegram_html=tg, preview=f"{n_errors} falhas consecutivas")
