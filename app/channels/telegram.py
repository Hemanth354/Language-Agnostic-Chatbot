import requests
import logging
from app.config import TELEGRAM_BOT_TOKEN

logger = logging.getLogger("telegram_channel")

def send_telegram_message(chat_id: int | str, text: str) -> bool:
    """Sends a text message via official Telegram Bot API."""
    if not TELEGRAM_BOT_TOKEN:
        logger.info(f"[Telegram Mock Send] ChatID: {chat_id} | Text: {text}")
        return True

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Telegram API send error: {e}")
        return False

