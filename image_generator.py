"""
image_generator.py
Generates a dark-themed PNG image with WASDE multi-year supply/demand tables.
5 columns: 2024/25 | 2025/26 Est. | 2026/27 (Mai) | 2026/27 (Jun) | Δ (Jun-Mai)
"""

import os
import sys
import logging
from io import BytesIO

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_OK = True
except ImportError:
    _PIL_OK = False
    logger.error("Pillow not installed — image generation disabled")


# ── Palette ───────────────────────────────────────────────────────────────────
_BG        = (13,  17,  23)     # near-black background
_SURFACE   = (22,  27,  34)     # card surface
_SURFACE2  = (28,  35,  44)     # table header row
_SURFACE3  = (18,  26,  40)     # section header (blue-tinted dark)
_BORDER    = (48,  54,  61)     # subtle grid lines
_TEXT      = (230, 237, 243)    # primary text
_TEXT_DIM  = (139, 148, 158)    # dimmed text (col headers, footer)
_DELTA_POS = (63,  185, 80)     # positive delta  (green)
_DELTA_NEG = (248, 81,  73)     # negative delta  (red)
_DELTA_ZRO = (100, 110, 120)    # zero delta      (muted)
_SECTION_ACCENT = (88, 166, 255)  # section title accent bar

_ACCENTS = {
    "soybeans":      (63,  185, 80),
    "corn":          (227, 179, 65),
    "wheat":         (240, 136, 62),
    "World":         (88,  166, 255),
    "United States": (121, 192, 255),
}

# ── Layout ────────────────────────────────────────────────────────────────────
_W        = 1080
_PAD_X    = 36
_TABLE_W  = _W - 2 * _PAD_X    # 1008
_COL0_W   = 148                 # row-label column
_DELTA_W  = 122                 # Δ column
_DATA_W   = (_TABLE_W - _COL0_W - _DELTA_W) // 4  # 184 per data column
_ROW_H    = 42
_HDR_H    = 66                  # table column-header row (two lines)
_TABLE_GAP  = 16
_SECTION_H  = 68                # section title height (prominent)
_TITLE_H    = 82
_FOOTER_H   = 50

# ── Fonts ─────────────────────────────────────────────────────────────────────
_FONT_CACHE: dict = {}

def _font(size: int, bold: bool = False) -> "ImageFont.FreeTypeFont":
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    if sys.platform == "win32":
        candidates = (
            ["C:/Windows/Fonts/seguisb.ttf", "C:/Windows/Fonts/segoeuib.ttf"]
            if bold else
            ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/calibri.ttf"]
        )
    else:
        candidates = (
            ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
             "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"]
            if bold else
            ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
             "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"]
        )

    font = None
    for path in candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                break
            except Exception:
                continue
    if font is None:
        try:
            font = ImageFont.load_default(size=size)
        except TypeError:
            font = ImageFont.load_default()

    _FONT_CACHE[key] = font
    return font


# ── Text helpers ──────────────────────────────────────────────────────────────

def _text_w(text: str, fnt) -> int:
    try:
        return int(fnt.getlength(text))
    except Exception:
        bb = fnt.getbbox(text)
        return bb[2] - bb[0]


def _font_height(fnt) -> int:
    try:
        bb = fnt.getbbox("Ag")
        return bb[3] - bb[1] + 3
    except Exception:
        return 15


def _draw_center(draw, x, y, w, h, text, fnt, color, multiline=False):
    if multiline and "\n" in text:
        lines = text.split("\n")
        lh = _font_height(fnt)
        total = lh * len(lines)
        ty = y + (h - total) // 2
        for line in lines:
            tw = _text_w(line, fnt)
            draw.text((x + (w - tw) // 2, ty), line, font=fnt, fill=color)
            ty += lh
    else:
        tw = _text_w(text, fnt)
        bb = fnt.getbbox(text)
        th = bb[3] - bb[1]
        draw.text((x + (w - tw) // 2, y + (h - th) // 2), text, font=fnt, fill=color)


def _draw_right(draw, x, y, w, h, text, fnt, color):
    tw = _text_w(text, fnt)
    bb = fnt.getbbox(text)
    th = bb[3] - bb[1]
    draw.text((x + w - tw - 6, y + (h - th) // 2), text, font=fnt, fill=color)


def _draw_left(draw, x, y, w, h, text, fnt, color, pad=8):
    bb = fnt.getbbox(text)
    th = bb[3] - bb[1]
    draw.text((x + pad, y + (h - th) // 2), text, font=fnt, fill=color)


# ── Formatting ────────────────────────────────────────────────────────────────

def _fmt(v: float | None) -> str:
    if v is None:
        return "—"
    s = f"{v:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_delta(v3: float | None, v4: float | None) -> tuple[str, tuple]:
    """Returns (formatted string, color) for delta = v4 - v3."""
    if v3 is None or v4 is None:
        return "—", _DELTA_ZRO
    d = round(v4 - v3, 2)
    if d > 0:
        s = f"+{d:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return s, _DELTA_POS
    elif d < 0:
        s = f"{d:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return s, _DELTA_NEG
    return "0,00", _DELTA_ZRO


def _col_display(col_labels: list[str]) -> list[str]:
    _PT = {"Jan":"Jan","Feb":"Fev","Mar":"Mar","Apr":"Abr","May":"Mai",
           "Jun":"Jun","Jul":"Jul","Aug":"Ago","Sep":"Set","Oct":"Out",
           "Nov":"Nov","Dec":"Dez"}
    out = []
    for lbl in col_labels:
        for en, pt in _PT.items():
            lbl = lbl.replace(f"({en})", f"({pt})")
        out.append(lbl)
    return out


# ── Table drawing ─────────────────────────────────────────────────────────────

def _draw_table(draw, x, y, title, title_color, col_headers, rows, f_tbl, f_hdr, f_data):
    """
    Draw one 5-column table (4 data cols + Δ col).
    col_headers: list of 4 strings for the data columns.
    rows: [(label, [v0,v1,v2,v3]), ...] — delta computed from v3-v2.
    Returns y after the table.
    """
    tw   = _TABLE_W
    dx   = x + _COL0_W                          # first data column x
    col_x = [dx + i * _DATA_W for i in range(4)]
    delta_x = dx + 4 * _DATA_W                  # delta column x

    # ── Header row ────────────────────────────────────────────────────────────
    draw.rectangle([x, y, x + tw, y + _HDR_H], fill=_SURFACE2)
    draw.rectangle([x, y, x + 5, y + _HDR_H], fill=title_color)
    _draw_left(draw, x + 4, y, _COL0_W, _HDR_H, title, f_tbl, title_color)

    for i, hdr in enumerate(col_headers):
        _draw_center(draw, col_x[i], y, _DATA_W, _HDR_H, hdr, f_hdr, _TEXT_DIM, multiline=True)

    # Delta column header
    _draw_center(draw, delta_x, y, _DELTA_W, _HDR_H, "Δ\n(Jun-Mai)", f_hdr, _TEXT_DIM, multiline=True)

    y += _HDR_H

    # ── Data rows ─────────────────────────────────────────────────────────────
    for ri, (label, vals) in enumerate(rows):
        bg = _SURFACE if ri % 2 == 0 else _BG
        draw.rectangle([x, y, x + tw, y + _ROW_H], fill=bg)
        draw.line([(x, y), (x + tw, y)], fill=_BORDER, width=1)

        _draw_left(draw, x, y, _COL0_W, _ROW_H, label, f_data, _TEXT)

        for i, v in enumerate(vals):
            c = _TEXT if v is not None else _TEXT_DIM
            _draw_right(draw, col_x[i], y, _DATA_W, _ROW_H, _fmt(v), f_data, c)

        d_str, d_color = _fmt_delta(vals[2], vals[3])
        _draw_right(draw, delta_x, y, _DELTA_W, _ROW_H, d_str, f_data, d_color)

        y += _ROW_H

    draw.line([(x, y), (x + tw, y)], fill=_BORDER, width=1)
    return y


# ── Section title ─────────────────────────────────────────────────────────────

def _draw_section_title(draw, x, y, text, f_sec) -> int:
    """Draw a prominent section header strip."""
    draw.rectangle([x, y, x + _TABLE_W, y + _SECTION_H], fill=_SURFACE3)
    # thick left accent bar
    draw.rectangle([x, y, x + 8, y + _SECTION_H], fill=_SECTION_ACCENT)
    # bottom separator line
    draw.line([(x, y + _SECTION_H - 1), (x + _TABLE_W, y + _SECTION_H - 1)],
              fill=_SECTION_ACCENT, width=1)
    _draw_left(draw, x + 8, y, _TABLE_W - 8, _SECTION_H, text, f_sec, _TEXT, pad=14)
    return y + _SECTION_H


# ── Public API ────────────────────────────────────────────────────────────────

def generate_wasde_image(multi_year_data: dict) -> bytes | None:
    if not _PIL_OK:
        logger.error("Pillow not available; cannot generate image")
        return None
    try:
        return _generate(multi_year_data)
    except Exception as e:
        logger.exception(f"Image generation error: {e}")
        return None


def _generate(data: dict) -> bytes:
    f_title = _font(26, bold=True)
    f_sec   = _font(20, bold=True)
    f_tbl   = _font(17, bold=True)
    f_hdr   = _font(14)
    f_data  = _font(15)

    col_labels = _col_display(data.get("col_labels", ["", "", "", ""]))

    PROD_LAYOUT = [
        ("soybeans", "Soja",  ["EUA","Brasil","Argentina","Mundo"],
                              ["United States","Brazil","Argentina","World"]),
        ("corn",     "Milho", ["EUA","Brasil","Argentina","Mundo"],
                              ["United States","Brazil","Argentina","World"]),
        ("wheat",    "Trigo", ["EUA","Brasil","Argentina","Mundo"],
                              ["United States","Brazil","Argentina","World"]),
    ]
    STOCK_LAYOUT = [
        ("World",         "Mundo", [("soybeans","Soja"),("corn","Milho"),("wheat","Trigo")]),
        ("United States", "EUA",   [("soybeans","Soja"),("corn","Milho"),("wheat","Trigo")]),
    ]

    PROD_ROWS  = 4
    STOCK_ROWS = 3

    h = (
        30
        + _TITLE_H + 14
        + _SECTION_H + 10
        + len(PROD_LAYOUT) * (_HDR_H + PROD_ROWS * _ROW_H + 1)
        + (len(PROD_LAYOUT) - 1) * _TABLE_GAP
        + 22
        + _SECTION_H + 10
        + len(STOCK_LAYOUT) * (_HDR_H + STOCK_ROWS * _ROW_H + 1)
        + (len(STOCK_LAYOUT) - 1) * _TABLE_GAP
        + 22
        + _FOOTER_H + 20
    )

    img  = Image.new("RGB", (_W, h), color=_BG)
    draw = ImageDraw.Draw(img)

    x = _PAD_X
    y = 30

    # ── Main title ─────────────────────────────────────────────────────────────
    month_pt = data.get("report_month_pt", "WASDE")
    draw.rectangle([x, y, x + _TABLE_W, y + _TITLE_H], fill=_SURFACE2)
    draw.rectangle([x, y, x + 5, y + _TITLE_H], fill=_ACCENTS["soybeans"])
    _draw_center(draw, x, y, _TABLE_W, _TITLE_H, f"WASDE  -  {month_pt}", f_title, _TEXT)
    y += _TITLE_H + 14

    # ── Section 1: Produção ────────────────────────────────────────────────────
    y = _draw_section_title(draw, x, y, "  Produção  (milhões de t)", f_sec)
    y += 10

    for comm_key, comm_label, pt_regions, xml_regions in PROD_LAYOUT:
        accent    = _ACCENTS.get(comm_key, _TEXT)
        comm_data = data.get(comm_key, {})
        rows = [
            (pt_r, [comm_data.get(xml_r, {}).get("Production", [None]*4)[i] for i in range(4)])
            for pt_r, xml_r in zip(pt_regions, xml_regions)
        ]
        y = _draw_table(draw, x, y, comm_label, accent, col_labels, rows, f_tbl, f_hdr, f_data)
        y += _TABLE_GAP

    # ── Section 2: Estoques Finais ─────────────────────────────────────────────
    y += 22 - _TABLE_GAP
    y = _draw_section_title(draw, x, y, "  Estoques Finais  (milhões de t)", f_sec)
    y += 10

    for xml_region, pt_region, commodities in STOCK_LAYOUT:
        accent = _ACCENTS.get(xml_region, _TEXT)
        rows = [
            (lbl, [data.get(ck, {}).get(xml_region, {}).get("Ending Stocks", [None]*4)[i]
                   for i in range(4)])
            for ck, lbl in commodities
        ]
        y = _draw_table(draw, x, y, pt_region, accent, col_labels, rows, f_tbl, f_hdr, f_data)
        y += _TABLE_GAP

    # ── Footer ─────────────────────────────────────────────────────────────────
    y += 22 - _TABLE_GAP
    draw.rectangle([x, y, x + _TABLE_W, y + _FOOTER_H], fill=_SURFACE)
    _draw_center(draw, x, y, _TABLE_W, _FOOTER_H, "Fonte: USDA / WASDE", f_hdr, _TEXT_DIM)

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
