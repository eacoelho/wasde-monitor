"""
WASDE Monitor Configuration
========================
Fill in your credentials and preferences below.
"""

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
TELEGRAM_CHAT_ID   = "YOUR_CHAT_ID_HERE"    # e.g. "-1001234567890"

# ── Groq ──────────────────────────────────────────────────────────────────────
GROQ_API_KEY = "YOUR_GROQ_API_KEY_HERE"

# ── TTS Settings ──────────────────────────────────────────────────────────────
ENABLE_AUDIO = True                          # set False to skip audio generation
TTS_MODEL    = "canopylabs/orpheus-v1-english"
TTS_VOICE    = "diana"

# ── LLM Settings ─────────────────────────────────────────────────────────────
LLM_PROVIDER   = "groq"                      # "groq" or "gemini"
LLM_MODEL      = "llama-3.3-70b-versatile"   # model used when LLM_PROVIDER = "groq"
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"
GEMINI_MODEL   = "gemini-1.5-flash"          # model used when LLM_PROVIDER = "gemini"

# ── WASDE URL Pattern ─────────────────────────────────────────────────────────
# wasde{MM}{YY}.pdf  e.g. wasde0626.pdf for June 2026
WASDE_BASE_URL = "https://www.usda.gov/oce/commodity/wasde/wasde{month:02d}{year:02d}.pdf"

# ── 2026 Release Schedule (ET = UTC-4 in summer, UTC-5 in winter) ─────────────
# All releases at 12:00 PM ET. We convert to UTC in scheduler.py.
RELEASE_DATES_2026 = [
    (2026, 1, 12),   # Jan
    (2026, 2, 10),   # Feb
    (2026, 3, 10),   # Mar
    (2026, 4,  9),   # Apr
    (2026, 5, 12),   # May  ← crop-year flip
    (2026, 6, 11),   # Jun
    (2026, 7, 10),   # Jul
    (2026, 8, 12),   # Aug
    (2026, 9, 11),   # Sep
    (2026, 10, 9),   # Oct
    (2026, 11, 10),  # Nov
    (2026, 12, 10),  # Dec
]

# ── Yahoo Finance tickers for front-month contracts ───────────────────────────
# These tickers rotate; update if yfinance stops recognizing them.
GRAIN_TICKERS = {
    "Soja":   "ZS=F",   # CBOT Soybeans front-month
    "Milho":  "ZC=F",   # CBOT Corn front-month
    "Trigo":  "ZW=F",   # CBOT Wheat front-month
}

# ── Image Style ───────────────────────────────────────────────────────────────
IMG_BG_COLOR      = (18, 18, 18)
IMG_HEADER_BG     = (230, 80, 20)    # orange
IMG_TEXT_WHITE    = (255, 255, 255)
IMG_TEXT_ORANGE   = (230, 80, 20)
IMG_TEXT_GRAY     = (180, 180, 180)
IMG_DELTA_POS     = (80, 200, 80)    # green
IMG_DELTA_NEG     = (220, 60, 60)    # red
IMG_DELTA_ZERO    = (180, 180, 180)  # gray

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE = "/home/claude/wasde_bot/wasde_monitor.log"
