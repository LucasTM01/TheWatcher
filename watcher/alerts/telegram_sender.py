"""Envio de mensagem para grupo do Telegram via Bot API."""
from __future__ import annotations

import requests

from .. import config
from .composer import Message


class TelegramNotConfigured(RuntimeError):
    pass


def send(global_cfg: dict, msg: Message) -> str:
    """Envia e retorna o chat_id de destino. Levanta exceção em falha."""
    chat_id = str(global_cfg.get("telegram", {}).get("chat_id", "")).strip()
    token = config.get_secret("TELEGRAM_BOT_TOKEN")

    if not token:
        raise TelegramNotConfigured(
            "TELEGRAM_BOT_TOKEN ausente no .env (crie o bot no @BotFather — veja o README)")
    if not chat_id:
        raise TelegramNotConfigured(
            "telegram.chat_id vazio em config/global.yaml (veja o README)")

    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": msg.telegram_html,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=30,
    )
    data = {}
    try:
        data = resp.json()
    except ValueError:
        pass
    if resp.status_code != 200 or not data.get("ok"):
        raise RuntimeError(
            f"Telegram respondeu {resp.status_code}: "
            f"{data.get('description') or resp.text[:200]}")
    return chat_id
