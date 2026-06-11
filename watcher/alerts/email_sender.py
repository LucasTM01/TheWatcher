"""Envio de e-mail via SMTP (Gmail SSL por padrão)."""
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .. import config
from .composer import Message


class EmailNotConfigured(RuntimeError):
    pass


def send(global_cfg: dict, msg: Message) -> list[str]:
    """Envia e retorna a lista de destinatários. Levanta exceção em falha."""
    email_cfg = global_cfg.get("email", {})
    host = email_cfg.get("smtp_host", "smtp.gmail.com")
    port = int(email_cfg.get("smtp_port", 465))
    user = (email_cfg.get("smtp_user") or "").strip()
    # remove espaços — o Google exibe a senha de app como "xxxx xxxx xxxx xxxx"
    password = config.get_secret("SMTP_PASSWORD").replace(" ", "")
    recipients = [r.strip() for r in (email_cfg.get("recipients") or []) if r.strip()]

    if not user or not recipients:
        raise EmailNotConfigured(
            "e-mail não configurado (smtp_user/recipients em config/global.yaml)")
    if not password:
        raise EmailNotConfigured(
            "SMTP_PASSWORD ausente no .env (senha de app do Gmail — veja o README)")

    mime = MIMEMultipart("alternative")
    mime["Subject"] = msg.subject
    mime["From"] = user
    mime["To"] = ", ".join(recipients)
    mime.attach(MIMEText(msg.text, "plain", "utf-8"))
    mime.attach(MIMEText(msg.html, "html", "utf-8"))

    # porta 465 = SSL implícito; 587 (ou outras) = STARTTLS
    if int(port) == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30) as server:
            server.login(user, password)
            server.sendmail(user, recipients, mime.as_string())
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(user, password)
            server.sendmail(user, recipients, mime.as_string())
    return recipients
