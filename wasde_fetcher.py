"""
wasde_fetcher.py
Fetches the WASDE PDF for a given month/year and extracts raw text.
Robust to temporary failures — retries for up to 10 minutes after release time.
"""

import io
import time
import logging
import requests
import pdfplumber
from datetime import datetime
from config import WASDE_BASE_URL

logger = logging.getLogger(__name__)


def build_wasde_url(year: int, month: int) -> str:
    """
    Constructs the WASDE PDF URL.
    Example: year=2026, month=6  →  wasde0626.pdf
    """
    return WASDE_BASE_URL.format(month=month, year=year % 100)


def fetch_wasde_pdf(year: int, month: int, max_wait_minutes: int = 15) -> bytes | None:
    """
    Tries to download the WASDE PDF, retrying every 60s for up to max_wait_minutes.
    Returns raw PDF bytes or None on failure.
    """
    url = build_wasde_url(year, month)
    logger.info(f"Fetching WASDE from: {url}")

    deadline = time.time() + max_wait_minutes * 60

    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200 and resp.headers.get("Content-Type", "").startswith("application/pdf"):
                logger.info(f"PDF downloaded successfully ({len(resp.content):,} bytes)")
                return resp.content
            elif resp.status_code == 404:
                logger.warning(f"PDF not yet available (404). Retrying in 60s…")
            else:
                logger.warning(f"Unexpected status {resp.status_code}. Retrying in 60s…")
        except requests.RequestException as e:
            logger.warning(f"Request error: {e}. Retrying in 60s…")

        time.sleep(60)

    logger.error("Failed to fetch WASDE PDF within the wait window.")
    return None


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extracts all text from a PDF using pdfplumber.
    Returns full text concatenated across all pages.
    """
    text_parts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text(x_tolerance=2, y_tolerance=3)
            if page_text:
                text_parts.append(f"--- PAGE {i+1} ---\n{page_text}")

    full_text = "\n\n".join(text_parts)
    logger.info(f"Extracted {len(full_text):,} characters from PDF ({len(text_parts)} pages)")
    return full_text


def get_wasde_text(year: int, month: int) -> str | None:
    """
    End-to-end: fetch PDF and return extracted text.
    """
    pdf_bytes = fetch_wasde_pdf(year, month)
    if not pdf_bytes:
        return None
    return extract_text_from_pdf(pdf_bytes)
