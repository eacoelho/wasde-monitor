"""
message_formatter.py
Builds the Telegram message in the exact format specified.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from market_data import format_price

TZ_BRASILIA = ZoneInfo("America/Sao_Paulo")
TZ_ET       = ZoneInfo("America/New_York")

# ── Month mapping ─────────────────────────────────────────────────────────────
_MONTH_PT_FROM_ABBR = {
    "Jan":"Janeiro",  "Feb":"Fevereiro", "Mar":"Março",    "Apr":"Abril",
    "May":"Maio",     "Jun":"Junho",     "Jul":"Julho",     "Aug":"Agosto",
    "Sep":"Setembro", "Oct":"Outubro",   "Nov":"Novembro",  "Dec":"Dezembro",
}

# ── Commodity layout ──────────────────────────────────────────────────────────
# Each country entry: (xml_region_name, pt_label, flag_emoji, [xml_attr_names])
# xml_region_name must match the normalised region key returned by the parser.
_LAYOUT = {
    "soybeans": {
        "emoji": "🫛", "label": "Soja",
        "countries": [
            ("World",         "Mundo",          "🌎", ["Production", "Ending Stocks"]),
            ("United States", "EUA",            "🇺🇸", ["Production", "Ending Stocks"]),
            ("Brazil",        "Brasil",         "🇧🇷", ["Production", "Exports"]),
            ("Argentina",     "Argentina",      "🇦🇷", ["Production", "Ending Stocks"]),
            ("China",         "China",          "🇨🇳", ["Domestic Total", "Imports"]),
        ],
    },
    "corn": {
        "emoji": "🌽", "label": "Milho",
        "countries": [
            ("World",         "Mundo",          "🌎", ["Production", "Ending Stocks"]),
            ("United States", "EUA",            "🇺🇸", ["Production", "Ending Stocks"]),
            ("Brazil",        "Brasil",         "🇧🇷", ["Production", "Exports"]),
            ("China",         "China",          "🇨🇳", ["Production", "Domestic Total"]),
            ("Argentina",     "Argentina",      "🇦🇷", ["Production"]),
            ("Ukraine",       "Ucrânia",        "🇺🇦", ["Production"]),
        ],
    },
    "wheat": {
        "emoji": "🌾", "label": "Trigo",
        "countries": [
            ("World",         "Mundo",          "🌎", ["Production", "Ending Stocks"]),
            ("United States", "EUA",            "🇺🇸", ["Production", "Ending Stocks"]),
            ("Brazil",        "Brasil",         "🇧🇷", ["Production"]),
            ("Argentina",     "Argentina",      "🇦🇷", ["Production"]),
            ("Russia",        "Rússia",         "🇷🇺", ["Production"]),
            ("Ukraine",       "Ucrânia",        "🇺🇦", ["Production"]),
            ("European Union","União Européia", "🇪🇺", ["Domestic Total"]),
        ],
    },
}

# XML attribute name → Portuguese label
_ATTR_PT = {
    "Production":    "Produção",
    "Ending Stocks": "Estoques Finais",
    "Exports":       "Exportação",
    "Imports":       "Importação",
    "Domestic Total": "Consumo Doméstico",
    "Domestic Crush": "Consumo Doméstico",
    "Domestic Feed":  "Consumo Doméstico",
}

_COMMODITY_EMOJI = {"Soja": "🫛", "Milho": "🌽", "Trigo": "🌾"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _scheduled_release_time(year: int, month: int) -> str:
    """Returns release time in BRT as 'HHhMM' (e.g. '13h00')."""
    try:
        from config import RELEASE_DATES_2026
        for y, m, d in RELEASE_DATES_2026:
            if y == year and m == month:
                release_et = datetime(y, m, d, 12, 0, tzinfo=TZ_ET)
                brt = release_et.astimezone(TZ_BRASILIA)
                return f"{brt.hour}h{brt.minute:02d}"
    except Exception:
        pass
    brt = datetime.now(timezone.utc).astimezone(TZ_BRASILIA)
    return f"{brt.hour}h{brt.minute:02d}"


def _fmt(value: float | None) -> str:
    """Format with 2 decimal places in pt-BR style: 1300.38 → '1.300,38'"""
    if value is None:
        return "n/d"
    s = f"{value:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _delta_str(prior: float | None, current: float | None, delta_label: str) -> str:
    """Returns '(Δ -0,20 vs Maio)' or empty string if values missing."""
    if prior is None or current is None:
        return ""
    delta = round(current - prior, 2)
    if delta > 0:
        d = f"+{delta:.2f}".replace(".", ",")
    elif delta < 0:
        d = f"{delta:.2f}".replace(".", ",")
    else:
        d = "0,00"
    return f"(Δ {d} {delta_label})"


# ── Section builder ───────────────────────────────────────────────────────────

def _build_commodity_section(
    commodity_key: str,
    commodity_data: dict,
    delta_label: str,
    crop_year: str,
) -> list[str]:
    """
    Builds lines for one commodity section (Soja, Milho, or Trigo).

    Multi-attribute countries get the region header on its own line:
        _Mundo 🌎:_
        Produção: 441,34 (Δ -0,20 vs Maio)
        Estoques Finais: 124,88 (Δ +0,10 vs Maio)

    Single-attribute countries get everything on one line:
        _Argentina 🇦🇷:_ Produção: 55,00 (Δ 0,00 vs Maio)
    """
    layout = _LAYOUT[commodity_key]
    emoji  = layout["emoji"]
    label  = layout["label"]

    lines = [f"*{emoji} {label} - Safra {crop_year} (milhões de t)*"]

    for xml_region, pt_region, flag, xml_attrs in layout["countries"]:
        region_data = commodity_data.get(xml_region, {})

        # Gather available (pt_attr_name, current, prior) tuples
        attr_rows = []
        for xml_attr in xml_attrs:
            vals = region_data.get(xml_attr, {})
            cur  = vals.get("current")
            pri  = vals.get("prior")
            if cur is not None:
                attr_rows.append((_ATTR_PT.get(xml_attr, xml_attr), cur, pri))

        if not attr_rows:
            continue

        lines.append("")  # blank line before each country block
        country_hdr = f"_{pt_region} {flag}:_"

        if len(attr_rows) == 1:
            pt_attr, cur, pri = attr_rows[0]
            d = _delta_str(pri, cur, delta_label)
            lines.append(f"{country_hdr} {pt_attr}: {_fmt(cur)} {d}".rstrip())
        else:
            lines.append(country_hdr)
            for pt_attr, cur, pri in attr_rows:
                d = _delta_str(pri, cur, delta_label)
                lines.append(f"{pt_attr}: {_fmt(cur)} {d}".rstrip())

    return lines


# ── Public API ────────────────────────────────────────────────────────────────

def build_telegram_message(data: dict, market_prices: dict) -> str:
    report_year  = data.get("report_year",  0)
    report_month = data.get("report_month", 0)
    month_pt     = data.get("report_month_pt", "WASDE")
    crop_year    = data.get("crop_year", "")
    prev_m       = data.get("prior_month_name")
    is_may       = data.get("is_may_report", False)

    release_time = _scheduled_release_time(report_year, report_month)

    if is_may:
        delta_label = "vs safra anterior"
    elif prev_m:
        delta_label = f"vs {_MONTH_PT_FROM_ABBR.get(prev_m, prev_m)}"
    else:
        delta_label = ""

    # ── Header ────────────────────────────────────────────────────────────────
    lines = [
        f"*🌱 WASDE - {month_pt} 🫛🌽🌾*",
        "",
        f"O Departamento de Agricultura dos Estados Unidos (USDA) divulgou hoje às "
        f"{release_time} o relatório mensal de oferta e demanda para grãos e oleaginosas.",
    ]

    if is_may:
        # Strip "Proj." suffix for a cleaner notice (e.g. "safra 2026/27")
        safra_label = crop_year.replace(" Proj.", "").strip()
        lines += [
            "",
            f"⚠️ _Relatório de maio: primeiras estimativas para a safra {safra_label}._",
        ]

    # ── Commodity sections ─────────────────────────────────────────────────────
    for commodity_key in ("soybeans", "corn", "wheat"):
        commodity_data = data.get(commodity_key, {})
        lines.append("")
        lines.extend(_build_commodity_section(commodity_key, commodity_data, delta_label, crop_year))

    # ── Market prices ─────────────────────────────────────────────────────────
    fetch_time = market_prices.get("_fetch_time_brt", "")
    time_label = f" (às {fetch_time})" if fetch_time else ""
    lines += ["", f"*💹 Mercado agora{time_label}:*"]

    for label in ("Soja", "Milho", "Trigo"):
        info     = market_prices.get(label) or {}
        emoji    = _COMMODITY_EMOJI[label]
        contract = info.get("contract", "")
        price    = format_price(info)
        pct      = info.get("pct_change")

        if pct is not None:
            sign    = "+" if pct >= 0 else ""
            pct_str = f" ({sign}{pct:.2f}%)"
            pct_str = pct_str.replace(".", ",")
        else:
            pct_str = ""

        lines.append(f"_{label} {emoji} {contract}:_ {price}{pct_str}")

    return "\n".join(lines)
