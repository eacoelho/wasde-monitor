"""
WASDE Monitor Configuration
========================
Fill in your credentials and preferences below.
"""

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
TELEGRAM_CHAT_ID   = "YOUR_CHAT_ID_HERE"    # e.g. "-1001234567890"

# ── WASDE XML URL Pattern ─────────────────────────────────────────────────────
# wasde{MM}{YY}v2.xml  e.g. wasde0626v2.xml for June 2026
WASDE_XML_URL = "https://www.usda.gov/oce/commodity/wasde/wasde{month:02d}{year:02d}v2.xml"

# ── 2026 Release Schedule (ET = UTC-4 in summer, UTC-5 in winter) ─────────────
# All releases at 12:00 PM ET.
RELEASE_DATES_2026 = [
    (2026, 1, 12),   # Jan
    (2026, 2, 10),   # Feb
    (2026, 3, 10),   # Mar
    (2026, 4,  9),   # Apr
    (2026, 5, 12),   # May  ← first 2026/27 projections
    (2026, 6, 11),   # Jun
    (2026, 7, 10),   # Jul
    (2026, 8, 12),   # Aug
    (2026, 9, 11),   # Sep
    (2026, 10, 9),   # Oct
    (2026, 11, 10),  # Nov
    (2026, 12, 10),  # Dec
]

# ── Yahoo Finance tickers for front-month contracts ───────────────────────────
GRAIN_TICKERS = {
    "Soja":   "ZS=F",   # CBOT Soybeans front-month
    "Milho":  "ZC=F",   # CBOT Corn front-month
    "Trigo":  "ZW=F",   # CBOT Wheat front-month
}

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE = "/home/wasde-monitor/wasde_monitor.log"
