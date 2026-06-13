"""
scheduler.py
Runs as a persistent daemon on the VPS.
Checks every minute whether a WASDE release is due.

Trigger logic:
  - The WASDE is released at 12:00 PM ET (Eastern Time).
  - ET = UTC-4 during DST (Mar–Nov), UTC-5 during EST (Nov–Mar).
  - Rather than hardcoding a UTC offset, we convert 12:00 PM ET to UTC
    dynamically using zoneinfo, so DST transitions are handled automatically.
  - First attempt starts at exactly 12:00 PM ET. If the PDF is not yet
    available (404), wasde_fetcher.py retries every 60s for up to 15 minutes.

State persistence: a JSON file records which reports have been sent,
preventing duplicate deliveries on VPS restarts.
"""

import json
import logging
import time
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

from config import RELEASE_DATES_2026
from wasde_main import run_wasde_pipeline

logger = logging.getLogger(__name__)

STATE_FILE  = Path(__file__).parent / "wasde_sent.json"
TZ_ET       = ZoneInfo("America/New_York")

# WASDE official release time (ET)
RELEASE_HOUR_ET   = 12
RELEASE_MINUTE_ET = 0


def load_sent_reports() -> set:
    """Returns a set of 'YYYY-MM' strings for already-sent reports."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def mark_report_sent(year: int, month: int):
    sent = load_sent_reports()
    sent.add(f"{year}-{month:02d}")
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(sent), f)


def is_release_day_and_time(now_utc: datetime) -> tuple[bool, int, int]:
    """
    Checks if today is a WASDE release date AND the current time in ET
    is at or past 12:00 PM.
    Returns (should_trigger, year, month).
    """
    # Convert current UTC to ET — handles DST automatically
    now_et = now_utc.astimezone(TZ_ET)
    today_et = (now_et.year, now_et.month, now_et.day)

    for yr, mo, day in RELEASE_DATES_2026:
        if (yr, mo, day) == today_et:
            at_or_past_release = (
                now_et.hour > RELEASE_HOUR_ET or
                (now_et.hour == RELEASE_HOUR_ET and now_et.minute >= RELEASE_MINUTE_ET)
            )
            return at_or_past_release, yr, mo

    return False, 0, 0


def run_scheduler():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(os.path.dirname(__file__), "wasde_monitor.log")),
        ]
    )

    logger.info("WASDE Monitor scheduler started. Checking every 60 seconds...")

    while True:
        try:
            now_utc = datetime.now(timezone.utc)
            should_trigger, yr, mo = is_release_day_and_time(now_utc)

            if should_trigger:
                key = f"{yr}-{mo:02d}"
                sent = load_sent_reports()

                if key not in sent:
                    now_et = now_utc.astimezone(TZ_ET)
                    logger.info(
                        f"WASDE release detected: {mo:02d}/{yr} "
                        f"(ET {now_et.strftime('%H:%M')}). Starting pipeline..."
                    )
                    success = run_wasde_pipeline(yr, mo)
                    if success:
                        mark_report_sent(yr, mo)
                        logger.info(f"Pipeline complete for {mo:02d}/{yr}. Marked as sent.")
                    else:
                        logger.error(f"Pipeline FAILED for {mo:02d}/{yr}.")
                        mark_report_sent(yr, mo)
                else:
                    logger.debug(f"Report {key} already sent. Skipping.")

        except Exception as e:
            logger.error(f"Scheduler error: {e}", exc_info=True)

        time.sleep(60)


if __name__ == "__main__":
    run_scheduler()
