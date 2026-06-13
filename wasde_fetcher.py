"""
wasde_fetcher.py
Fetches the WASDE PDF for a given month/year and extracts raw text.
Robust to temporary failures — retries for up to 10 minutes after release time.
"""

import io
import re
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


_COMMODITY_KEYWORDS = {
    "soybean", "soybeans", "oilseed", "oilseeds",
    "corn", "maize",
    "wheat",
}


def _filter_commodity_text(text: str) -> str:
    """Keep only paragraphs that mention soybeans, corn, or wheat."""
    paragraphs = re.split(r"\n\s*\n", text)
    kept = [p for p in paragraphs if any(kw in p.lower() for kw in _COMMODITY_KEYWORDS)]
    return "\n\n".join(kept)


_HIGHLIGHTS_END = 5   # pages 1-5: narrative highlights
_TABLES_END     = 25  # pages 6-25: supply/demand tables

_NUMBER_RE = re.compile(r'\d')


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Two-segment extraction to stay within Groq token limits:
    - Pages 1-5  (highlights): commodity paragraph filter — full prose kept
    - Pages 6-25 (tables): only pages whose header mentions a target commodity,
      and only lines that contain numbers (strips footnotes and prose)
    """
    highlights_parts = []
    table_parts = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages[:_TABLES_END]):
            text = page.extract_text(x_tolerance=2, y_tolerance=3)
            if not text:
                continue
            if i < _HIGHLIGHTS_END:
                highlights_parts.append(f"--- PAGE {i+1} ---\n{text}")
            else:
                # Only keep table pages that are about our three commodities
                page_header = "\n".join(text.splitlines()[:5]).lower()
                if any(kw in page_header for kw in _COMMODITY_KEYWORDS):
                    num_lines = [l for l in text.splitlines() if _NUMBER_RE.search(l)]
                    if num_lines:
                        table_parts.append(f"[p{i+1}]\n" + "\n".join(num_lines))

    filtered_highlights = _filter_commodity_text("\n\n".join(highlights_parts))
    table_text = "\n\n".join(table_parts)

    full_text = filtered_highlights
    if table_text:
        full_text += "\n\n=== SUPPLY/DEMAND TABLES ===\n" + table_text

    logger.info(
        f"Highlights: {len(filtered_highlights):,} chars (pages 1-{_HIGHLIGHTS_END}); "
        f"Tables: {len(table_text):,} chars (pages {_HIGHLIGHTS_END+1}-{_TABLES_END}); "
        f"Total: {len(full_text):,} chars"
    )
    return full_text


def get_wasde_text(year: int, month: int) -> str | None:
    """
    End-to-end: fetch PDF and return extracted text ready for LLM.
    """
    pdf_bytes = fetch_wasde_pdf(year, month)
    if not pdf_bytes:
        return None
    return extract_text_from_pdf(pdf_bytes)
