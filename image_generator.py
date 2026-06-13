"""
image_generator.py
Generates a dark-themed PNG image with WASDE multi-year supply/demand tables.
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
_BG       = (13,  17,  23)      # #0D1117  near-black background
_SURFACE  = (22,  27,  34)      # #161B22  card surface
_SURFACE2 = (28,  35,  44)      # table header row
_BORDER   = (48,  54,  61)      # #30363D  subtle grid lines
_TEXT     = (230, 237, 243)     # #E6EDF3  primary text
_TEXT_DIM = (139, 148, 158)     # #8B949E  secondary text

# Accent colors per commodity and region
_ACCENTS = {
    "soybeans": (63,  185, 80),   # green
    "corn":     (227, 179, 65),   # gold
    "wheat":    (240, 136, 62),   # orange
    "World":         (88,  166, 255),  # blue
    "United States": (121, 192, 255),  # light blue
}

# ── Layout constants ──────────────────────────────────────────────────────────
_W          = 900    # total image width
_PAD_X      = 30    # horizontal outer padding
_TABLE_W    = _W - 2 * _PAD_X   # 840
_COL0_W     = 130   # label column width
_DATA_W     = (_TABLE_W - _COL0_W) // 4  # 177 px per data column
_ROW_H      = 32    # data row height
_HDR_H      = 52    # column-header row height (fits two lines)
_TABLE_GAP  = 14    # vertical gap between consecutive tables
_SECTION_H  = 46    # section title strip height
_TITLE_H    = 68    # main title height
_FOOTER_H   = 38

# ── Font helpers ──────────────────────────────────────────────────────────────
_FONT_CACHE: dict = {}

def _font(size: int, bold: bool = False) -> "ImageFont.FreeTypeFont":
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    if sys.platform == "win32":
        candidates = (
            ["C:/Windows/Fonts/seguisb.ttf",
             "C:/Windows/Fonts/segoeuib.ttf"] if bold else
            ["C:/Windows/Fonts/segoeui.ttf",
             "C:/Windows/Fonts/calibri.ttf"]
        )
    else:
        candidates = (
            ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
             "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"] if bold else
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


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _text_w(text: str, fnt) -> int:
    try:
        return int(fnt.getlength(text))
    except Exception:
        bb = fnt.getbbox(text)
        return bb[2] - bb[0]


def _draw_text_center(draw: "ImageDraw.ImageDraw", x: int, y: int, w: int, h: int,
                      text: str, fnt, color: tuple, multiline: bool = False):
    """Draw text centered in a bounding box (x, y, x+w, y+h)."""
    if multiline and "\n" in text:
        lines = text.split("\n")
        line_h = _font_height(fnt)
        total_h = line_h * len(lines)
        ty = y + (h - total_h) // 2
        for line in lines:
            tw = _text_w(line, fnt)
            tx = x + (w - tw) // 2
            draw.text((tx, ty), line, font=fnt, fill=color)
            ty += line_h
    else:
        tw = _text_w(text, fnt)
        bb = fnt.getbbox(text)
        th = bb[3] - bb[1]
        tx = x + (w - tw) // 2
        ty = y + (h - th) // 2
        draw.text((tx, ty), text, font=fnt, fill=color)


def _font_height(fnt) -> int:
    try:
        bb = fnt.getbbox("Ag")
        return bb[3] - bb[1] + 2
    except Exception:
        return 14


def _draw_text_right(draw, x: int, y: int, w: int, h: int, text: str, fnt, color: tuple):
    """Draw text right-aligned within the bounding box."""
    tw = _text_w(text, fnt)
    bb = fnt.getbbox(text)
    th = bb[3] - bb[1]
    tx = x + w - tw - 8
    ty = y + (h - th) // 2
    draw.text((tx, ty), text, font=fnt, fill=color)


def _draw_text_left(draw, x: int, y: int, w: int, h: int, text: str, fnt, color: tuple):
    """Draw text left-aligned with small left padding."""
    bb = fnt.getbbox(text)
    th = bb[3] - bb[1]
    tx = x + 8
    ty = y + (h - th) // 2
    draw.text((tx, ty), text, font=fnt, fill=color)


def _fmt(value: float | None) -> str:
    """pt-BR number format: 1300.38 → '1.300,38'; None → '—'"""
    if value is None:
        return "—"
    s = f"{value:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# ── Table drawing ─────────────────────────────────────────────────────────────

def _draw_table(
    draw: "ImageDraw.ImageDraw",
    x: int, y: int,
    title: str,
    title_color: tuple,
    col_headers: list[str],
    rows: list[tuple[str, list[float | None]]],
    fnt_title,
    fnt_hdr,
    fnt_data,
) -> int:
    """
    Draw a single table.  Returns the y coordinate after the table.

    col_headers: list of 4 strings (may contain \\n for two-line headers)
    rows: [(row_label, [val0, val1, val2, val3]), ...]
    """
    table_w = _TABLE_W
    col_x   = [x + _COL0_W + i * _DATA_W for i in range(4)]

    # ── Title row (colored band) ──────────────────────────────────────────────
    draw.rectangle([x, y, x + table_w, y + _HDR_H], fill=_SURFACE2)
    # left accent stripe
    draw.rectangle([x, y, x + 4, y + _HDR_H], fill=title_color)
    # title text (left-aligned in label col)
    _draw_text_left(draw, x + 4, y, _COL0_W, _HDR_H, title, fnt_title, title_color)
    # column header labels (centered, potentially two lines)
    for i, hdr in enumerate(col_headers):
        cx = col_x[i]
        _draw_text_center(draw, cx, y, _DATA_W, _HDR_H, hdr, fnt_hdr, _TEXT_DIM, multiline=True)
    y += _HDR_H

    # ── Data rows ─────────────────────────────────────────────────────────────
    for ri, (label, vals) in enumerate(rows):
        row_bg = _SURFACE if ri % 2 == 0 else _BG
        draw.rectangle([x, y, x + table_w, y + _ROW_H], fill=row_bg)
        # left separator line
        draw.line([(x, y), (x + table_w, y)], fill=_BORDER, width=1)
        # row label
        _draw_text_left(draw, x, y, _COL0_W, _ROW_H, label, fnt_data, _TEXT)
        # data values
        for i, val in enumerate(vals):
            cx = col_x[i]
            text_color = _TEXT if val is not None else _TEXT_DIM
            _draw_text_right(draw, cx, y, _DATA_W, _ROW_H, _fmt(val), fnt_data, text_color)
        y += _ROW_H

    # bottom border
    draw.line([(x, y), (x + table_w, y)], fill=_BORDER, width=1)
    return y


# ── Section title strip ───────────────────────────────────────────────────────

def _draw_section_title(draw, x: int, y: int, text: str, fnt) -> int:
    draw.rectangle([x, y, x + _TABLE_W, y + _SECTION_H], fill=_SURFACE)
    _draw_text_left(draw, x, y, _TABLE_W, _SECTION_H, text, fnt, _TEXT)
    return y + _SECTION_H


# ── Column-label helpers ──────────────────────────────────────────────────────

def _col_display(col_labels: list[str]) -> list[str]:
    """
    Convert raw col_labels (e.g. ['2024/25', '2025/26\\nEst.', '2026/27\\n(May)', '2026/27\\n(Jun)'])
    to display labels with translated month abbreviation for the last two columns.
    """
    _MONTH_PT_ABB = {
        "Jan":"Jan", "Feb":"Fev", "Mar":"Mar", "Apr":"Abr", "May":"Mai",
        "Jun":"Jun", "Jul":"Jul", "Aug":"Ago", "Sep":"Set", "Oct":"Out",
        "Nov":"Nov", "Dec":"Dez",
    }
    out = []
    for lbl in col_labels:
        for en, pt in _MONTH_PT_ABB.items():
            lbl = lbl.replace(f"({en})", f"({pt})")
        out.append(lbl)
    return out


# ── Public API ────────────────────────────────────────────────────────────────

def generate_wasde_image(multi_year_data: dict) -> bytes | None:
    """
    Build the WASDE image from multi-year parsed data.
    Returns PNG bytes or None on error.
    """
    if not _PIL_OK:
        logger.error("Pillow not available; cannot generate image")
        return None

    try:
        return _generate(multi_year_data)
    except Exception as e:
        logger.exception(f"Image generation error: {e}")
        return None


def _generate(data: dict) -> bytes:
    # ── Fonts ─────────────────────────────────────────────────────────────────
    f_title  = _font(20, bold=True)
    f_sec    = _font(14, bold=True)
    f_tbl    = _font(13, bold=True)
    f_hdr    = _font(11)
    f_data   = _font(12)

    col_labels = _col_display(data.get("col_labels", ["","","",""]))

    # ── Commodity configs ──────────────────────────────────────────────────────
    PROD_LAYOUT = [
        ("soybeans", "Soja",  ["EUA","Brasil","Argentina","Mundo"],
         ["United States","Brazil","Argentina","World"]),
        ("corn",     "Milho", ["EUA","Brasil","Argentina","Mundo"],
         ["United States","Brazil","Argentina","World"]),
        ("wheat",    "Trigo", ["EUA","Brasil","Argentina","Mundo"],
         ["United States","Brazil","Argentina","World"]),
    ]
    STOCK_LAYOUT = [
        ("World",         "Mundo",
         [("soybeans","Soja"),("corn","Milho"),("wheat","Trigo")]),
        ("United States", "EUA",
         [("soybeans","Soja"),("corn","Milho"),("wheat","Trigo")]),
    ]

    # ── Compute required height ────────────────────────────────────────────────
    prod_rows_per = 4
    stock_rows_per = 3

    h = (
        30                                                          # top pad
        + _TITLE_H                                                  # main title
        + 12                                                        # gap
        + _SECTION_H                                                # section 1 title
        + 8                                                         # gap
        + len(PROD_LAYOUT) * (_HDR_H + prod_rows_per * _ROW_H + 1)  # tables
        + (len(PROD_LAYOUT) - 1) * _TABLE_GAP                      # inter-table gaps
        + 20                                                        # section gap
        + _SECTION_H                                                # section 2 title
        + 8
        + len(STOCK_LAYOUT) * (_HDR_H + stock_rows_per * _ROW_H + 1)
        + (len(STOCK_LAYOUT) - 1) * _TABLE_GAP
        + 20
        + _FOOTER_H
        + 20                                                        # bottom pad
    )

    img  = Image.new("RGB", (_W, h), color=_BG)
    draw = ImageDraw.Draw(img)

    x = _PAD_X
    y = 30

    # ── Main title ─────────────────────────────────────────────────────────────
    month_pt = data.get("report_month_pt", "WASDE")
    title    = f"WASDE  -  {month_pt}"
    draw.rectangle([x, y, x + _TABLE_W, y + _TITLE_H], fill=_SURFACE2)
    draw.rectangle([x, y, x + 5, y + _TITLE_H], fill=_ACCENTS["soybeans"])
    _draw_text_center(draw, x, y, _TABLE_W, _TITLE_H, title, f_title, _TEXT)
    y += _TITLE_H + 12

    # ── Section 1: Production ──────────────────────────────────────────────────
    y = _draw_section_title(draw, x, y, "  Produção  (milhões de t)", f_sec)
    y += 8

    for comm_key, comm_label, pt_regions, xml_regions in PROD_LAYOUT:
        accent = _ACCENTS.get(comm_key, _TEXT)
        comm_data = data.get(comm_key, {})

        rows = []
        for pt_r, xml_r in zip(pt_regions, xml_regions):
            vals = [comm_data.get(xml_r, {}).get("Production", [None]*4)[i] for i in range(4)]
            rows.append((pt_r, vals))

        y = _draw_table(draw, x, y, comm_label, accent, col_labels, rows,
                        f_tbl, f_hdr, f_data)
        y += _TABLE_GAP

    # ── Section 2: Ending Stocks ───────────────────────────────────────────────
    y += 20 - _TABLE_GAP   # replace last table gap with larger section gap
    y = _draw_section_title(draw, x, y, "  Estoques Finais  (milhões de t)", f_sec)
    y += 8

    for xml_region, pt_region, commodities in STOCK_LAYOUT:
        accent = _ACCENTS.get(xml_region, _TEXT)

        rows = []
        for comm_key, comm_label in commodities:
            comm_data = data.get(comm_key, {})
            vals = [comm_data.get(xml_region, {}).get("Ending Stocks", [None]*4)[i] for i in range(4)]
            rows.append((comm_label, vals))

        y = _draw_table(draw, x, y, pt_region, accent, col_labels, rows,
                        f_tbl, f_hdr, f_data)
        y += _TABLE_GAP

    # ── Footer ─────────────────────────────────────────────────────────────────
    y += 20 - _TABLE_GAP
    draw.rectangle([x, y, x + _TABLE_W, y + _FOOTER_H], fill=_SURFACE)
    _draw_text_center(draw, x, y, _TABLE_W, _FOOTER_H,
                      "Fonte: USDA / WASDE", f_hdr, _TEXT_DIM)

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
