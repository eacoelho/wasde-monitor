"""
market_data.pyy
Fetches current grain futures prices from Yahoo Finance.
Returns prices in cents/bushel as displayed on CBOT.
"""

import logging
import yfinance as yf
from datetime import datetime
from config import GRAIN_TICKERS

logger = logging.getLogger(__name__)


def get_grain_prices() -> dict:
    """
    Fetches current (or last available) prices for soy, corn, wheat.
    Returns dict: { "Soja": {"price": 1113.25, "contract": "Jul/26", "ticker": "ZS=F"}, ... }
    """
    result = {}

    for commodity, ticker in GRAIN_TICKERS.items():
        try:
            tkr = yf.Ticker(ticker)

            # Use fast_info if available, else fallback to history
            try:
                info = tkr.fast_info
                price = info.last_price
                if price and price > 0:
                    contract = _infer_contract(ticker)
                    result[commodity] = {
                        "price": round(price, 2),
                        "contract": contract,
                        "ticker": ticker,
                    }
                    continue
            except Exception:
                pass

            # Fallback: use recent history
            hist = tkr.history(period="2d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
                contract = _infer_contract(ticker)
                result[commodity] = {
                    "price": round(price, 2),
                    "contract": contract,
                    "ticker": ticker,
                }
            else:
                logger.warning(f"No price data for {ticker}")
                result[commodity] = {"price": None, "contract": "?", "ticker": ticker}

        except Exception as e:
            logger.error(f"Error fetching {ticker}: {e}")
            result[commodity] = {"price": None, "contract": "?", "ticker": ticker}

    return result


def _infer_contract(ticker: str) -> str:
    """
    Infers the approximate front-month contract label.
    yfinance =F tickers roll automatically — we just show the current month/year.
    For a more precise label you'd need to scrape CME group.
    """
    now = datetime.utcnow()
    # CBOT contract months:
    # Soy (ZS): Jan(F), Mar(H), May(K), Jul(N), Aug(Q), Sep(U), Nov(X)
    # Corn (ZC): Mar(H), May(K), Jul(N), Sep(U), Dec(Z)
    # Wheat (ZW): Mar(H), May(K), Jul(N), Sep(U), Dec(Z)
    month = now.month
    year  = now.year % 100  # 2-digit

    if ticker == "ZS=F":
        # Soy front months
        if month in (1, 2):
            return f"Mar/{year:02d}"
        elif month == 3:
            return f"May/{year:02d}"
        elif month in (4,):
            return f"Jul/{year:02d}"
        elif month in (5, 6):
            return f"Jul/{year:02d}"
        elif month == 7:
            return f"Aug/{year:02d}"
        elif month == 8:
            return f"Sep/{year:02d}"
        elif month in (9, 10):
            return f"Nov/{year:02d}"
        else:
            y = (year + 1) % 100
            return f"Jan/{y:02d}"

    elif ticker == "ZC=F":
        # Corn front months
        if month in (1, 2):
            return f"Mar/{year:02d}"
        elif month == 3:
            return f"May/{year:02d}"
        elif month in (4, 5):
            return f"Jul/{year:02d}"
        elif month in (6, 7, 8):
            return f"Sep/{year:02d}"
        elif month in (9, 10, 11):
            return f"Dec/{year:02d}"
        else:
            y = (year + 1) % 100
            return f"Mar/{y:02d}"

    elif ticker == "ZW=F":
        # Wheat front months
        if month in (1, 2):
            return f"Mar/{year:02d}"
        elif month == 3:
            return f"May/{year:02d}"
        elif month in (4, 5, 6):
            return f"Jul/{year:02d}"
        elif month in (7, 8):
            return f"Sep/{year:02d}"
        elif month in (9, 10, 11):
            return f"Dec/{year:02d}"
        else:
            y = (year + 1) % 100
            return f"Mar/{y:02d}"

    return f"{month:02d}/{year:02d}"


def format_price(price_info: dict) -> str:
    """
    Formats a price entry as e.g. '1113,25 c/bu'
    """
    if price_info["price"] is None:
        return "n/d"
    # CBOT quotes cents/bushel — round to 2 decimal places
    p = price_info["price"]
    return f"{p:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " c/bu"
