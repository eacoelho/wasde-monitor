"""
wasde_main.py
Main pipeline: fetch → parse → generate image+audio → send via Telegram.
Called by the scheduler when a WASDE release is detected.
"""

import logging
import tempfile
import os
from datetime import datetime
from pathlib import Path

from wasde_fetcher     import get_wasde_text
from wasde_parser      import extract_wasde_data
from market_data       import get_grain_prices
from image_generator   import generate_wasde_image
from audio_generator   import text_to_speech, build_tts_script
from message_formatter import build_telegram_message
from telegram_sender   import send_message, send_photo, send_voice

logger = logging.getLogger(__name__)


def run_wasde_pipeline(year: int, month: int) -> bool:
    """
    Full pipeline for a single WASDE report.
    Returns True if Telegram messages were sent successfully.
    """
    logger.info(f"=== Starting WASDE pipeline for {month:02d}/{year} ===")

    # ── 1. Fetch and extract PDF text ────────────────────────────────────────
    logger.info("Step 1: Fetching WASDE PDF...")
    wasde_text = get_wasde_text(year, month)
    if not wasde_text:
        _send_error("❌ Falha ao baixar o relatório WASDE do USDA.")
        return False

    # ── 2. Parse with LLM ────────────────────────────────────────────────────
    logger.info("Step 2: Extracting data with LLM...")
    data = extract_wasde_data(wasde_text)
    if not data or data.get("parse_error"):
        _send_error("❌ Falha na extração dos dados do relatório WASDE.")
        return False

    # ── 3. Fetch market prices ───────────────────────────────────────────────
    logger.info("Step 3: Fetching market prices...")
    market_prices = get_grain_prices()

    # ── 4. Generate image ────────────────────────────────────────────────────
    logger.info("Step 4: Generating table image...")
    img_path = f"/tmp/wasde_{year}{month:02d}.png"
    img_ok = generate_wasde_image(data, img_path)

    # ── 5. Build text message ────────────────────────────────────────────────
    logger.info("Step 5: Building Telegram message...")
    text_msg = build_telegram_message(data, market_prices)

    # ── 6. Generate audio ────────────────────────────────────────────────────
    logger.info("Step 6: Generating audio...")
    audio_path = f"/tmp/wasde_{year}{month:02d}.ogg"
    tts_script = build_tts_script(data, market_prices)
    audio_ok = text_to_speech(tts_script, audio_path)

    # ── 7. Send to Telegram ──────────────────────────────────────────────────
    logger.info("Step 7: Sending to Telegram...")

    # 7a. Text message
    send_message(text_msg)

    # 7b. Image (if generated)
    if img_ok and Path(img_path).exists():
        send_photo(img_path)
        Path(img_path).unlink(missing_ok=True)

    # 7c. Voice (if generated)
    if audio_ok and Path(audio_path).exists():
        send_voice(audio_path, caption="🔊 Resumo em áudio")
        Path(audio_path).unlink(missing_ok=True)

    logger.info("=== Pipeline complete ===")
    return True


def _send_error(msg: str):
    logger.error(msg)
    try:
        send_message(f"⚠️ WASDE Monitor\n{msg}")
    except Exception:
        pass


if __name__ == "__main__":
    """Run manually for testing: python wasde_main.py"""
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    now = datetime.utcnow()
    year  = int(sys.argv[1]) if len(sys.argv) > 1 else now.year
    month = int(sys.argv[2]) if len(sys.argv) > 2 else now.month

    print(f"Running WASDE pipeline for {month:02d}/{year}...")
    ok = run_wasde_pipeline(year, month)
    print("Success." if ok else "Failed — check logs.")
