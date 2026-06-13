"""
message_formatter.py
Builds the Telegram message text in the exact format requested.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from market_data import format_price
from wasde_parser import format_delta

TZ_BRASILIA = ZoneInfo("America/Sao_Paulo")
TZ_ET       = ZoneInfo("America/New_York")


def _scheduled_release_time(year: int, month: int) -> str:
    """
    Returns the WASDE release time in Brasília for the given report month,
    derived from RELEASE_DATES_2026. Falls back to the current BRT time.
    """
    try:
        from config import RELEASE_DATES_2026
        for y, m, d in RELEASE_DATES_2026:
            if y == year and m == month:
                release_et = datetime(y, m, d, 12, 0, tzinfo=TZ_ET)
                brt = release_et.astimezone(TZ_BRASILIA)
                return f"{brt.hour}h" if brt.minute == 0 else f"{brt.hour}h{brt.minute:02d}"
    except Exception:
        pass
    # Fallback: current time in BRT
    brt = datetime.now(timezone.utc).astimezone(TZ_BRASILIA)
    return f"{brt.hour}h" if brt.minute == 0 else f"{brt.hour}h{brt.minute:02d}"


def build_telegram_message(data: dict, market_prices: dict) -> str:
    """
    Returns a formatted Markdown string for Telegram.
    """
    month        = data.get("report_month", "WASDE")       # e.g. "Junho 2026"
    month_en     = data.get("report_month_en", "")          # e.g. "June 2026"
    crop_years   = data.get("crop_years_shown", [])
    current_year = crop_years[-1] if crop_years else ""

    # Derive year/month integers from report_month_en for the schedule lookup
    rel_year, rel_month = _parse_report_month(month_en)
    release_time = _scheduled_release_time(rel_year, rel_month)

    year_label = f" - {current_year}" if current_year else ""

    # ── Header ────────────────────────────────────────────────────────────────
    lines = [
        f"🌱 *WASDE - {month}* 🌽",
        "",
        f"O Departamento de Agricultura dos Estados Unidos (USDA) divulgou hoje às "
        f"{release_time} o relatório mensal de oferta e demanda para grãos e oleaginosas.",
    ]

    # ── Crop year flip notice ─────────────────────────────────────────────────
    if data.get("is_crop_year_flip"):
        new_year = crop_years[-1] if crop_years else ""
        lines += [
            "",
            f"⚠️ _Relatório de maio: inclusão das primeiras estimativas para a safra {new_year}._",
        ]

    # ── Key changes ───────────────────────────────────────────────────────────
    changes = data.get("key_changes", [])
    if changes:
        lines += ["", "*Resumo*", ""]
        for change in changes:
            clean = change.lstrip("•●-– ").strip()
            lines.append(f"• {clean}")

    # ── Market prices ─────────────────────────────────────────────────────────
    lines += ["", "*Mercado agora:*"]

    soy   = market_prices.get("Soja",  {})
    corn  = market_prices.get("Milho", {})
    wheat = market_prices.get("Trigo", {})

    def price_line(label, info):
        if not info or info.get("price") is None:
            return f"{label}: n/d"
        contract = info.get("contract", "")
        price    = format_price(info)
        return f"{label} {contract}: {price}"

    lines.append(price_line("Soja",  soy))
    lines.append(price_line("Milho", corn))
    lines.append(price_line("Trigo", wheat))

    # ── Production summary ────────────────────────────────────────────────────
    lines += ["", f"*Produção - Mundo{year_label} (Milhões de t):*"]
    lines.append(_prod_line("Soja",  data.get("soybeans", {})))
    lines.append(_prod_line("Milho", data.get("corn",     {})))
    lines.append(_prod_line("Trigo", data.get("wheat",    {})))

    # ── Ending stocks summary ─────────────────────────────────────────────────
    lines += ["", f"*Estoques Finais - Mundo{year_label} (Milhões de t):*"]
    lines.append(_stock_line("Soja",  data.get("soybeans", {})))
    lines.append(_stock_line("Milho", data.get("corn",     {})))
    lines.append(_stock_line("Trigo", data.get("wheat",    {})))

    return "\n".join(lines)


def _parse_report_month(month_en: str) -> tuple[int, int]:
    """Parse 'June 2026' → (2026, 6). Returns (0, 0) on failure."""
    MONTHS = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    try:
        parts = month_en.lower().split()
        return int(parts[1]), MONTHS[parts[0]]
    except Exception:
        return 0, 0


def _fmt(value) -> str:
    """Format a float in pt-BR style (comma as decimal separator)."""
    if value is None:
        return "n/d"
    s = f"{value:,.1f}"                                  # e.g. "1,300.4"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")  # → "1.300,4"


def _prod_line(label: str, commodity: dict) -> str:
    prod    = commodity.get("production", {})
    prior   = prod.get("world_prior")
    current = prod.get("world_current")
    _, delta_str = format_delta(prior, current)
    return f"• {label}: {_fmt(current)}  (Δ {delta_str})"


def _stock_line(label: str, commodity: dict) -> str:
    stk     = commodity.get("ending_stocks", {})
    prior   = stk.get("world_prior")
    current = stk.get("world_current")
    _, delta_str = format_delta(prior, current)
    return f"• {label}: {_fmt(current)}  (Δ {delta_str})"
