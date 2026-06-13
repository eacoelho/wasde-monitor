"""
scheduler.py
Runs as a persistent daemon on the VPS.
Checks every minute whether a WASDE release is due.
Triggers the pipeline at 12:05 PM ET (17:05 UTC in summer, 18:05 UTC in winter)
to give USDA a 5-minute buffer after the official 12:00 PM ET release time.

IMPORTANT: ET (Eastern Time) is UTC-4 in summer (DST), UTC-5 in winter (EST).
We use 17:10 UTC as a safe universal trigger that works in both cases:
  - Summer (UTC-4): 17:10 UTC = 13:10 ET  → 10 min after release ✓
  - Winter (UTC-5): 17:10 UTC = 12:10 ET  → 10 min after release ✓

State persistence: a simple JSON file records which reports have been sent
to prevent duplicate deliveries on restart.
"""

import json
import logging
import time
import os
from datetime import datetime, timezone
from pathlib import Path

from config import RELEASE_DATES_2026
from wasde_main import run_wasde_pipeline

logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).parent / "wasde_sent.json"

# Trigger time: 17:10 UTC (safe for both ET summer and winter)
TRIGGER_HOUR_UTC   = 17
TRIGGER_MINUTE_UTC = 10


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
    Checks if today is a WASDE release date AND we're past the trigger time.
    Returns (should_trigger, year, month).
    """
    today = (now_utc.year, now_utc.month, now_utc.day)

    for yr, mo, day in RELEASE_DATES_2026:
        if (yr, mo, day) == today:
            # Check if we're at or past the trigger time
            at_or_past_trigger = (
                now_utc.hour > TRIGGER_HOUR_UTC or
                (now_utc.hour == TRIGGER_HOUR_UTC and now_utc.minute >= TRIGGER_MINUTE_UTC)
            )
            return at_or_past_trigger, yr, mo

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

    logger.info("WASDE scheduler started. Checking every 60 seconds...")

    while True:
        try:
            now_utc = datetime.now(timezone.utc)
            should_trigger, yr, mo = is_release_day_and_time(now_utc)

            if should_trigger:
                key = f"{yr}-{mo:02d}"
                sent = load_sent_reports()

                if key not in sent:
                    logger.info(f"WASDE release detected: {mo:02d}/{yr}. Starting pipeline...")
                    success = run_wasde_pipeline(yr, mo)
                    if success:
                        mark_report_sent(yr, mo)
                        logger.info(f"Pipeline complete for {mo:02d}/{yr}. Marked as sent.")
                    else:
                        logger.error(f"Pipeline FAILED for {mo:02d}/{yr}. Will NOT retry automatically.")
                        # Still mark as sent to avoid infinite retry loop.
                        # If you want auto-retry, remove this line and add retry logic.
                        mark_report_sent(yr, mo)
                else:
                    logger.debug(f"Report {key} already sent. Skipping.")

        except Exception as e:
            logger.error(f"Scheduler error: {e}", exc_info=True)

        time.sleep(60)


if __name__ == "__main__":
    run_scheduler()
