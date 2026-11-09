import requests
import logging
from typing import Dict, Any, Optional
from app.config import WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_VERIFY_TOKEN

logger = logging.getLogger("whatsapp_channel")

def verify_webhook(mode: Optional[str], token: Optional[str], challenge: Optional[str]):
    """Validates WhatsApp Webhook registration."""
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return int(challenge) if challenge and challenge.isdigit() else challenge
    return None

def send_whatsapp_message(to_number: str, text: str) -> bool:
    """Sends a text message via WhatsApp Business Cloud API."""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        logger.info(f"[WhatsApp Mock Send] To: {to_number} | Message: {text}")
        return True

    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text}
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"WhatsApp API send error: {e}")
        return False

