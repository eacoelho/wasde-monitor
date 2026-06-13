"""
message_formatter.py
Builds the Telegram message text from parsed WASDE XML data.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from market_data import format_price
from wasde_parser import fmt_delta

TZ_BRASILIA = ZoneInfo("America/Sao_Paulo")
TZ_ET       = ZoneInfo("America/New_York")

_MONTH_PT_FROM_ABBR = {
    "Jan":"Janeiro",  "Feb":"Fevereiro", "Mar":"Março",    "Apr":"Abril",
    "May":"Maio",     "Jun":"Junho",     "Jul":"Julho",     "Aug":"Agosto",
    "Sep":"Setembro", "Oct":"Outubro",   "Nov":"Novembro",  "Dec":"Dezembro",
}


def _scheduled_release_time(year: int, month: int) -> str:
    """Returns the WASDE release time in Brasília (BRT) for the given report month."""
    try:
        from config import RELEASE_DATES_2026
        for y, m, d in RELEASE_DATES_2026:
            if y == year and m == month:
                release_et = datetime(y, m, d, 12, 0, tzinfo=TZ_ET)
                brt = release_et.astimezone(TZ_BRASILIA)
                return f"{brt.hour}h" if brt.minute == 0 else f"{brt.hour}h{brt.minute:02d}"
    except Exception:
        pass
    brt = datetime.now(timezone.utc).astimezone(TZ_BRASILIA)
    return f"{brt.hour}h" if brt.minute == 0 else f"{brt.hour}h{brt.minute:02d}"


def _fmt(value: float | None) -> str:
    """Format a float in pt-BR style: 1300.38 → '1.300,4'"""
    if value is None:
        return "n/d"
    s = f"{value:,.1f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _delta_suffix(prev_m: str | None, is_may: bool) -> str:
    if is_may:
        return "vs safra anterior"
    if prev_m:
        return f"vs {_MONTH_PT_FROM_ABBR.get(prev_m, prev_m)}"
    return "Δ"


def _prod_line(label: str, commodity_data: dict, prev_m: str | None, is_may: bool) -> str:
    prod    = commodity_data.get("World", {}).get("Production", {})
    current = prod.get("current")
    prior   = prod.get("prior")
    _, delta_str = fmt_delta(prior, current)
    suffix = _delta_suffix(prev_m, is_may)
    return f"• {label}: {_fmt(current)}  ({suffix}: {delta_str})"


def _stock_line(label: str, commodity_data: dict, prev_m: str | None, is_may: bool) -> str:
    stk     = commodity_data.get("World", {}).get("Ending Stocks", {})
    current = stk.get("current")
    prior   = stk.get("prior")
    _, delta_str = fmt_delta(prior, current)
    suffix = _delta_suffix(prev_m, is_may)
    return f"• {label}: {_fmt(current)}  ({suffix}: {delta_str})"


def build_telegram_message(data: dict, market_prices: dict) -> str:
    report_year  = data.get("report_year",  0)
    report_month = data.get("report_month", 0)
    month_pt     = data.get("report_month_pt", "WASDE")
    crop_year    = data.get("crop_year", "")
    prev_m       = data.get("prior_month_name")
    is_may       = data.get("is_may_report", False)

    release_time = _scheduled_release_time(report_year, report_month)
    year_label   = f" - {crop_year}" if crop_year else ""

    soy  = data.get("soybeans", {})
    corn = data.get("corn",     {})
    wht  = data.get("wheat",    {})

    # ── Header ────────────────────────────────────────────────────────────────
    lines = [
        f"🌱 *WASDE - {month_pt}* 🌽",
        "",
        f"O Departamento de Agricultura dos EUA (USDA) divulgou hoje às "
        f"{release_time} o relatório mensal de oferta e demanda para grãos e oleaginosas.",
    ]

    if is_may:
        lines += [
            "",
            f"⚠️ _Relatório de maio: primeiras estimativas para a safra {crop_year}._",
        ]

    # ── Market prices ─────────────────────────────────────────────────────────
    lines += ["", "*Mercado agora:*"]

    def price_line(label, info):
        if not info or info.get("price") is None:
            return f"{label}: n/d"
        return f"{label} {info.get('contract', '')}: {format_price(info)}"

    lines.append(price_line("Soja",  market_prices.get("Soja",  {})))
    lines.append(price_line("Milho", market_prices.get("Milho", {})))
    lines.append(price_line("Trigo", market_prices.get("Trigo", {})))

    # ── Production ────────────────────────────────────────────────────────────
    lines += ["", f"*Produção - Mundo{year_label} (Milhões de t):*"]
    lines.append(_prod_line("Soja",  soy,  prev_m, is_may))
    lines.append(_prod_line("Milho", corn, prev_m, is_may))
    lines.append(_prod_line("Trigo", wht,  prev_m, is_may))

    # ── Ending stocks ─────────────────────────────────────────────────────────
    lines += ["", f"*Estoques Finais - Mundo{year_label} (Milhões de t):*"]
    lines.append(_stock_line("Soja",  soy,  prev_m, is_may))
    lines.append(_stock_line("Milho", corn, prev_m, is_may))
    lines.append(_stock_line("Trigo", wht,  prev_m, is_may))

    return "\n".join(lines)
