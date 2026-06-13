"""
image_generator.py
Creates a dark-themed table image matching the Itaú BBA WASDE style.
Uses Pillow only — no external rendering or browser needed.
"""

import logging
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from config import (
    IMG_BG_COLOR, IMG_HEADER_BG, IMG_TEXT_WHITE,
    IMG_TEXT_ORANGE, IMG_TEXT_GRAY, IMG_DELTA_POS,
    IMG_DELTA_NEG, IMG_DELTA_ZERO
)

logger = logging.getLogger(__name__)

# ── Font loading ──────────────────────────────────────────────────────────────
def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'Bold' if bold else ''}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans-{'Bold' if bold else 'Regular'}.ttf",
        f"/usr/share/fonts/truetype/freefont/FreeSans{'Bold' if bold else ''}.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _delta_color(val) -> tuple:
    if val is None:
        return IMG_TEXT_GRAY
    if val > 0:
        return IMG_DELTA_POS
    elif val < 0:
        return IMG_DELTA_NEG
    return IMG_DELTA_ZERO


def _fmt(val, decimals=1) -> str:
    if val is None:
        return "n/d"
    return f"{val:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _delta_str(prior, current) -> tuple:
    """Returns (delta_value_or_None, display_string)."""
    if prior is None or current is None:
        return None, "n/d"
    d = round(current - prior, 1)
    if d > 0:
        return d, f"+{_fmt(d)}"
    elif d < 0:
        return d, _fmt(d)
    return 0.0, "0,0"


def generate_wasde_image(data: dict, output_path: str) -> bool:
    """
    Generates the WASDE summary table image.
    data: parsed dict from wasde_parser.extract_wasde_data()
    output_path: where to save the PNG
    Returns True on success.
    """
    try:
        W = 600
        # Fonts
        f_title   = _load_font(17, bold=True)
        f_header  = _load_font(13, bold=True)
        f_section = _load_font(12, bold=True)
        f_body    = _load_font(11)
        f_small   = _load_font(10)

        # ── Layout constants ──────────────────────────────────────────────────
        PAD       = 16
        ROW_H     = 22
        SEC_H     = 28    # section header height
        TITLE_H   = 50
        FOOTER_H  = 28
        COL_LABEL = 90    # width of the row-label column
        N_COLS    = 5     # label | prior | current | Δ (and year labels)
        COL_W     = (W - PAD*2 - COL_LABEL) // 4

        # Determine crop years
        years = data.get("crop_years_shown", ["25/26", "26/27"])
        if len(years) >= 2:
            yr_prior, yr_curr = years[-2], years[-1]
        elif len(years) == 1:
            yr_prior = yr_curr = years[0]
        else:
            yr_prior, yr_curr = "Ant.", "Atual"

        col_headers = [yr_prior, yr_curr, "Δ"]
        report_label = data.get("report_month", "WASDE")

        # ── Build row data ────────────────────────────────────────────────────
        def prod_rows(commodity_key: str, include_arg: bool = True) -> list:
            """Returns list of (label, prior, current) tuples."""
            prod = data.get(commodity_key, {}).get("production", {})
            rows = [
                ("EUA",    prod.get("usa_prior"),       prod.get("usa_current")),
                ("BRA",    prod.get("brazil_prior"),    prod.get("brazil_current")),
            ]
            if include_arg:
                rows.append(("ARG", prod.get("argentina_prior"), prod.get("argentina_current")))
            rows.append(("Mundo", prod.get("world_prior"), prod.get("world_current")))
            return rows

        def stock_rows(commodity_key: str) -> list:
            stk = data.get(commodity_key, {}).get("ending_stocks", {})
            return [
                ("EUA",    stk.get("usa_prior"),   stk.get("usa_current")),
                ("Mundo",  stk.get("world_prior"), stk.get("world_current")),
            ]

        sections = [
            # (section_title, orange_label, rows_fn)
            ("Produção", None, None),
            (None, "Soja",   prod_rows("soybeans")),
            (None, "Milho",  prod_rows("corn")),
            (None, "Trigo",  prod_rows("wheat", include_arg=False)),
            ("Estoques Finais", None, None),
            (None, "Soja",   stock_rows("soybeans")),
            (None, "Milho",  stock_rows("corn")),
            (None, "Trigo",  stock_rows("wheat")),
        ]

        # ── Calculate height ──────────────────────────────────────────────────
        H = TITLE_H + FOOTER_H + PAD
        col_header_row_h = ROW_H + 4
        H += col_header_row_h  # top column headers

        # Add sub-headers for Produção column headers (one set)
        for sec_title, orange_label, rows in sections:
            if sec_title:
                H += SEC_H
            elif orange_label:
                H += ROW_H  # orange label row
                H += col_header_row_h  # col header row
                H += len(rows) * ROW_H

        H += PAD * 2

        # ── Create image ──────────────────────────────────────────────────────
        img  = Image.new("RGB", (W, H), IMG_BG_COLOR)
        draw = ImageDraw.Draw(img)

        def x_col(col_idx):
            """Returns x start for data columns (0=prior, 1=current, 2=delta)."""
            return PAD + COL_LABEL + col_idx * COL_W

        def draw_text_right(text, x_right, y, font, color):
            bbox = font.getbbox(text)
            tw = bbox[2] - bbox[0]
            draw.text((x_right - tw - 4, y), text, font=font, fill=color)

        def draw_text_center(text, x_left, col_w, y, font, color):
            bbox = font.getbbox(text)
            tw = bbox[2] - bbox[0]
            draw.text((x_left + (col_w - tw) // 2, y), text, font=font, fill=color)

        # ── Title ─────────────────────────────────────────────────────────────
        y = 0
        draw.rectangle([0, 0, W, TITLE_H], fill=IMG_BG_COLOR)

        title_text = f"USDA – WASDE | {report_label}"
        bbox = f_title.getbbox(title_text)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, 14), title_text, font=f_title, fill=IMG_TEXT_WHITE)

        subtitle = "Relatório de Oferta e Demanda"
        bbox2 = f_header.getbbox(subtitle)
        tw2 = bbox2[2] - bbox2[0]
        draw.text(((W - tw2) // 2, 33), subtitle, font=f_header, fill=IMG_TEXT_GRAY)

        y = TITLE_H + PAD

        # ── Main loop ─────────────────────────────────────────────────────────
        for sec_title, orange_label, rows in sections:

            if sec_title:
                # Dark orange section banner
                draw.rectangle([PAD, y, W - PAD, y + SEC_H - 2], fill=IMG_HEADER_BG)
                bbox = f_section.getbbox(sec_title)
                th = bbox[3] - bbox[1]
                draw.text(
                    ((W - (bbox[2]-bbox[0])) // 2, y + (SEC_H - th) // 2 - 1),
                    sec_title, font=f_section, fill=IMG_TEXT_WHITE
                )
                y += SEC_H
                continue

            # Orange commodity label row
            draw.text((PAD, y + 3), orange_label, font=f_section, fill=IMG_TEXT_ORANGE)

            # Column headers to the right of the label
            for i, ch in enumerate(col_headers):
                draw_text_center(ch, x_col(i), COL_W, y + 3, f_small, IMG_TEXT_GRAY)

            y += ROW_H + 4

            # Data rows
            for row_label, prior, current in rows:
                delta_val, delta_str = _delta_str(prior, current)
                label_color = IMG_TEXT_GRAY if row_label != "Mundo" else IMG_TEXT_WHITE

                draw.text((PAD + 6, y + 2), row_label, font=f_body, fill=label_color)
                draw_text_right(_fmt(prior),   x_col(0) + COL_W, y + 2, f_body, IMG_TEXT_GRAY)
                draw_text_right(_fmt(current), x_col(1) + COL_W, y + 2, f_body, IMG_TEXT_WHITE)
                draw_text_right(delta_str,     x_col(2) + COL_W, y + 2, f_body, _delta_color(delta_val))

                # Subtle row separator
                draw.line([(PAD, y + ROW_H - 1), (W - PAD, y + ROW_H - 1)],
                          fill=(40, 40, 40), width=1)
                y += ROW_H

        # ── Footer ────────────────────────────────────────────────────────────
        y += PAD
        draw.rectangle([0, y, W, y + FOOTER_H], fill=(28, 28, 28))
        footer = "Fonte: USDA WASDE  |  Números em milhões de toneladas métricas"
        bbox = f_small.getbbox(footer)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, y + 7), footer, font=f_small, fill=IMG_TEXT_GRAY)

        img.save(output_path, "PNG", optimize=True)
        logger.info(f"Image saved: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Image generation failed: {e}", exc_info=True)
        return False
