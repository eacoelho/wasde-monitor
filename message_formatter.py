"""
message_formatter.py
Builds the Telegram message text in the exact format requested.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from market_data import format_price
from wasde_parser import format_delta

TZ_BRASILIA = ZoneInfo("America/Sao_Paulo")


def _release_time_brasilia() -> str:
    """
    Returns the current time in Brasília formatted as 'HHhMM'.
    Called at pipeline execution time, so it reflects the actual
    moment the report was processed — regardless of VPS timezone.
    Examples: '13h00', '14h05'
    """
    now_brt = datetime.now(timezone.utc).astimezone(TZ_BRASILIA)
    if now_brt.minute == 0:
        return f"{now_brt.hour}h"
    return f"{now_brt.hour}h{now_brt.minute:02d}"


def build_telegram_message(data: dict, market_prices: dict) -> str:
    """
    Returns a formatted Markdown string for Telegram.
    """
    month       = data.get("report_month", "WASDE")   # e.g. "Junho 2026"
    release_time = _release_time_brasilia()

    # ── Header ────────────────────────────────────────────────────────────────
    lines = [
        f"🌱 *WASDE - {month}* 🌽",
        "",
        f"O Departamento de Agricultura dos Estados Unidos (USDA) divulgou hoje às "
        f"{release_time} o relatório mensal de oferta e demanda para grãos e oleaginosas.",
    ]

    # ── Crop year flip notice ─────────────────────────────────────────────────
    if data.get("is_crop_year_flip"):
        years    = data.get("crop_years_shown", [])
        new_year = years[-1] if years else ""
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
    lines += ["", "*Produção (Mi t):*"]
    lines.append(_prod_line("Soja",  data.get("soybeans", {})))
    lines.append(_prod_line("Milho", data.get("corn",     {})))
    lines.append(_prod_line("Trigo", data.get("wheat",    {})))

    # ── Ending stocks summary ─────────────────────────────────────────────────
    lines += ["", "*Estoques Finais Mundo (Mi t):*"]
    lines.append(_stock_line("Soja",  data.get("soybeans", {})))
    lines.append(_stock_line("Milho", data.get("corn",     {})))
    lines.append(_stock_line("Trigo", data.get("wheat",    {})))

    return "\n".join(lines)


def _prod_line(label: str, commodity: dict) -> str:
    prod    = commodity.get("production", {})
    prior   = prod.get("world_prior")
    current = prod.get("world_current")
    _, delta_str = format_delta(prior, current)
    curr_str = f"{current:,.1f}" if current is not None else "n/d"
    curr_str = curr_str.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"• {label}: {curr_str} Mi t  (Δ {delta_str})"


def _stock_line(label: str, commodity: dict) -> str:
    stk     = commodity.get("ending_stocks", {})
    prior   = stk.get("world_prior")
    current = stk.get("world_current")
    _, delta_str = format_delta(prior, current)
    curr_str = f"{current:,.1f}" if current is not None else "n/d"
    curr_str = curr_str.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"• {label}: {curr_str} Mi t  (Δ {delta_str})"
