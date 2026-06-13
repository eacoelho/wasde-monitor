"""
wasde_fetcher.py
Downloads the USDA WASDE XML report for a given month/year.
Retries up to max_wait_minutes if the file is not yet published.
"""

import time
import logging
import requests
from config import WASDE_XML_URL

logger = logging.getLogger(__name__)


def build_wasde_url(year: int, month: int) -> str:
    """
    Constructs the WASDE XML URL.
    Example: year=2026, month=6  →  wasde0626v2.xml
    """
    return WASDE_XML_URL.format(month=month, year=year % 100)


def fetch_wasde_xml(year: int, month: int, max_wait_minutes: int = 15) -> bytes | None:
    """
    Downloads the WASDE v2 XML, retrying every 60s for up to max_wait_minutes.
    Returns raw XML bytes or None on failure.
    """
    url = build_wasde_url(year, month)
    logger.info(f"Fetching WASDE XML from: {url}")
    deadline = time.time() + max_wait_minutes * 60

    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                logger.info(f"XML downloaded ({len(resp.content):,} bytes)")
                return resp.content
            elif resp.status_code == 404:
                logger.warning("XML not yet available (404). Retrying in 60s…")
            else:
                logger.warning(f"Unexpected status {resp.status_code}. Retrying in 60s…")
        except requests.RequestException as e:
            logger.warning(f"Request error: {e}. Retrying in 60s…")
        time.sleep(60)

    logger.error("Failed to fetch WASDE XML within the wait window.")
    return None
