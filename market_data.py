"""
market_data.py
Fetches current grain futures prices from Yahoo Finance.
Returns prices in cents/bushel as displayed on CBOT, with daily % change.
"""

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import yfinance as yf
from config import GRAIN_TICKERS

logger = logging.getLogger(__name__)

TZ_BRASILIA = ZoneInfo("America/Sao_Paulo")
TZ_ET       = ZoneInfo("America/New_York")


def get_grain_prices() -> dict:
    """
    Fetches current (or last available) prices for soy, corn, wheat.

    Returns dict:
    {
        "Soja":  {"price": 1113.25, "pct_change": -0.18, "price_time": "14h19",
                  "contract": "Jul/26", "ticker": "ZS=F"},
        "Milho": {...},
        "Trigo": {...},
    }
    price_time is the BRT timestamp of the last trade reported by Yahoo Finance.
    """
    result = {}

    for commodity, ticker in GRAIN_TICKERS.items():
        try:
            tkr      = yf.Ticker(ticker)
            price    = None
            pct      = None
            pt       = None
            contract = _infer_contract(ticker)

            try:
                fi    = tkr.fast_info
                price = fi.last_price
                prev  = fi.previous_close
                if price and price > 0:
                    if prev and prev > 0:
                        pct = round((price / prev - 1) * 100, 2)
                    pt = _quote_time_et(tkr)
                    result[commodity] = {
                        "price":      round(price, 2),
                        "pct_change": pct,
                        "price_time": pt,
                        "contract":   contract,
                        "ticker":     ticker,
                    }
                    continue
            except Exception:
                pass

            # Fallback: use recent history
            hist = tkr.history(period="2d")
            if not hist.empty:
                closes = hist["Close"]
                price  = float(closes.iloc[-1])
                if len(closes) >= 2:
                    pct = round((closes.iloc[-1] / closes.iloc[-2] - 1) * 100, 2)
                # Try to get timestamp from history index
                try:
                    last_ts = hist.index[-1]
                    pt = last_ts.astimezone(TZ_BRASILIA).strftime("%Hh%M")
                except Exception:
                    pt = None
                result[commodity] = {
                    "price":      round(price, 2),
                    "pct_change": pct,
                    "price_time": pt,
                    "contract":   contract,
                    "ticker":     ticker,
                }
            else:
                logger.warning(f"No price data for {ticker}")
                result[commodity] = {
                    "price": None, "pct_change": None, "price_time": None,
                    "contract": "?", "ticker": ticker,
                }

        except Exception as e:
            logger.error(f"Error fetching {ticker}: {e}")
            result[commodity] = {
                "price": None, "pct_change": None, "price_time": None,
                "contract": "?", "ticker": ticker,
            }

    return result


def _quote_time_et(tkr) -> str | None:
    """
    Returns the last-trade time shown by Yahoo Finance, formatted as 'HHhMM' in ET.
    E.g. Yahoo shows 'At close: June 12 at 2:19:59 PM EDT' → '14h19'.
    """
    # Primary: regularMarketTime from tkr.info (Unix timestamp UTC)
    try:
        ts = tkr.info.get("regularMarketTime")
        if ts:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(TZ_ET)
            return f"{dt.hour}h{dt.minute:02d}"
    except Exception:
        pass
    # Fallback: last 1-minute bar (index already carries exchange TZ)
    try:
        hist = tkr.history(period="1d", interval="1m")
        if not hist.empty:
            last_ts = hist.index[-1]
            return f"{last_ts.hour}h{last_ts.minute:02d}"
    except Exception:
        pass
    return None


def _infer_contract(ticker: str) -> str:
    """Infers the approximate front-month contract label from the current date."""
    now   = datetime.utcnow()
    month = now.month
    year  = now.year % 100

    if ticker == "ZS=F":
        if month in (1, 2):          return f"Mar/{year:02d}"
        elif month == 3:             return f"May/{year:02d}"
        elif month in (4, 5, 6):     return f"Jul/{year:02d}"
        elif month == 7:             return f"Aug/{year:02d}"
        elif month == 8:             return f"Sep/{year:02d}"
        elif month in (9, 10):       return f"Nov/{year:02d}"
        else:
            y = (year + 1) % 100
            return f"Jan/{y:02d}"

    elif ticker == "ZC=F":
        if month in (1, 2):          return f"Mar/{year:02d}"
        elif month == 3:             return f"May/{year:02d}"
        elif month in (4, 5):        return f"Jul/{year:02d}"
        elif month in (6, 7, 8):     return f"Sep/{year:02d}"
        elif month in (9, 10, 11):   return f"Dec/{year:02d}"
        else:
            y = (year + 1) % 100
            return f"Mar/{y:02d}"

    elif ticker == "ZW=F":
        if month in (1, 2):          return f"Mar/{year:02d}"
        elif month == 3:             return f"May/{year:02d}"
        elif month in (4, 5, 6):     return f"Jul/{year:02d}"
        elif month in (7, 8):        return f"Sep/{year:02d}"
        elif month in (9, 10, 11):   return f"Dec/{year:02d}"
        else:
            y = (year + 1) % 100
            return f"Mar/{y:02d}"

    return f"{month:02d}/{year:02d}"


def format_price(price_info: dict) -> str:
    """Formats a price entry as e.g. '1.113,25 c/bu'"""
    if not price_info or price_info.get("price") is None:
        return "n/d"
    p = price_info["price"]
    s = f"{p:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") + " c/bu"
