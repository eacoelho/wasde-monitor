"""
wasde_main.py
Pipeline: fetch WASDE XML → parse → get market prices → format → send via Telegram.

Usage:
    python wasde_main.py            # auto-detect latest released report
    python wasde_main.py 2026 6     # explicit year and month
"""

import logging
import sys
from datetime import datetime, timezone

from wasde_fetcher     import fetch_wasde_xml
from wasde_parser      import parse_wasde_xml, parse_wasde_xml_multi_year
from market_data       import get_grain_prices
from message_formatter import build_telegram_message
from image_generator   import generate_wasde_image
from telegram_sender   import send_message, send_photo_bytes

logger = logging.getLogger(__name__)


def run_wasde_pipeline(year: int, month: int) -> bool:
    logger.info(f"=== Starting WASDE pipeline for {month:02d}/{year} ===")

    # 1. Fetch XML
    logger.info("Step 1: Fetching WASDE XML...")
    xml_bytes = fetch_wasde_xml(year, month)
    if not xml_bytes:
        _send_error("❌ Falha ao baixar o relatório WASDE do USDA.")
        return False

    # 2. Parse XML
    logger.info("Step 2: Parsing XML...")
    data = parse_wasde_xml(xml_bytes, year, month)
    if not data:
        _send_error("❌ Falha na análise do relatório WASDE.")
        return False

    # 3. Fetch market prices
    logger.info("Step 3: Fetching market prices...")
    market_prices = get_grain_prices()

    # 4. Build and send Telegram message
    logger.info("Step 4: Sending Telegram message...")
    text_msg = build_telegram_message(data, market_prices)
    send_message(text_msg)

    # 5. Generate and send image
    logger.info("Step 5: Generating image...")
    multi_year = parse_wasde_xml_multi_year(xml_bytes, year, month)
    if multi_year:
        img_bytes = generate_wasde_image(multi_year)
        if img_bytes:
            send_photo_bytes(img_bytes)
        else:
            logger.warning("Image generation returned None")
    else:
        logger.warning("Multi-year parse returned None — skipping image")

    logger.info("=== Pipeline complete ===")
    return True


def _send_error(msg: str):
    logger.error(msg)
    try:
        send_message(f"⚠️ WASDE Monitor\n{msg}")
    except Exception:
        pass


def latest_wasde_date() -> tuple[int, int]:
    """
    Returns (year, month) of the most recently released WASDE report.
    Checks RELEASE_DATES_2026 first; falls back to a date heuristic.
    """
    now_utc = datetime.now(timezone.utc)
    try:
        from config import RELEASE_DATES_2026
        # Release at 12pm ET = 16:00 UTC (summer DST) / 17:00 UTC (winter)
        past = [
            (y, m) for y, m, d in RELEASE_DATES_2026
            if datetime(y, m, d, 17, 0, tzinfo=timezone.utc) <= now_utc
        ]
        if past:
            return past[-1]
    except (ImportError, AttributeError):
        pass

    # Heuristic: WASDE releases around the 10th-12th of each month
    if now_utc.day >= 11:
        return now_utc.year, now_utc.month
    if now_utc.month == 1:
        return now_utc.year - 1, 12
    return now_utc.year, now_utc.month - 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) >= 3:
        year  = int(sys.argv[1])
        month = int(sys.argv[2])
    else:
        year, month = latest_wasde_date()
        logger.info(f"No date specified — using latest available report: {month:02d}/{year}")

    print(f"Running WASDE pipeline for {month:02d}/{year}...")
    ok = run_wasde_pipeline(year, month)
    print("Success." if ok else "Failed — check logs.")
