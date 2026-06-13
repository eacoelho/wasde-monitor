"""
telegram_sender.py
Sends text messages, images, and voice messages to Telegram.
"""

import logging
import requests
from pathlib import Path
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_message(text: str, parse_mode: str = "Markdown") -> bool:
    """Sends a text message."""
    try:
        resp = requests.post(
            f"{BASE_URL}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": parse_mode},
            timeout=30,
        )
        if resp.status_code == 200:
            logger.info("Text message sent.")
            return True
        logger.error(f"sendMessage failed: {resp.status_code} {resp.text}")
        return False
    except Exception as e:
        logger.error(f"sendMessage exception: {e}")
        return False


def send_photo_bytes(image_bytes: bytes, caption: str = "", filename: str = "wasde.png") -> bool:
    """Sends an in-memory image (bytes) directly to Telegram."""
    try:
        resp = requests.post(
            f"{BASE_URL}/sendPhoto",
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
            files={"photo": (filename, image_bytes, "image/png")},
            timeout=60,
        )
        if resp.status_code == 200:
            logger.info("Photo (bytes) sent.")
            return True
        logger.error(f"sendPhoto failed: {resp.status_code} {resp.text}")
        return False
    except Exception as e:
        logger.error(f"sendPhoto exception: {e}")
        return False


def send_photo(image_path: str, caption: str = "") -> bool:
    """Sends an image file."""
    try:
        with open(image_path, "rb") as f:
            resp = requests.post(
                f"{BASE_URL}/sendPhoto",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
                files={"photo": f},
                timeout=60,
            )
        if resp.status_code == 200:
            logger.info("Photo sent.")
            return True
        logger.error(f"sendPhoto failed: {resp.status_code} {resp.text}")
        return False
    except Exception as e:
        logger.error(f"sendPhoto exception: {e}")
        return False


def send_voice(audio_path: str, caption: str = "") -> bool:
    """Sends an OGG voice message."""
    try:
        with open(audio_path, "rb") as f:
            resp = requests.post(
                f"{BASE_URL}/sendVoice",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
                files={"voice": ("wasde_audio.ogg", f, "audio/ogg")},
                timeout=120,
            )
        if resp.status_code == 200:
            logger.info("Voice message sent.")
            return True
        logger.error(f"sendVoice failed: {resp.status_code} {resp.text}")
        return False
    except Exception as e:
        logger.error(f"sendVoice exception: {e}")
        return False
