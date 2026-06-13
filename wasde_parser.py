"""
wasde_parser.py
Parses the USDA WASDE v2 XML file directly into a structured dict.
No LLM required — reads data from XML using xml.etree.ElementTree.

XML structure (per commodity section):
  <srNN><Report Name="srNN" Report_Month="June 2026">
    <matrix3 region_header2="2026/27 Proj.">  ← soybeans (sr28) uses matrix3 / suffix 2
      <m1_region_group3_Collection>
        <m1_region_group3 region2="World  2/">
          <m1_month_group2_Collection>
            <m1_month_group2 forecast_month2="Jun">
              <m1_attribute_group3_Collection>
                <m1_attribute_group3 attribute2="Production">
                  <Cell cell_value2="441.34" />

    <matrix1 region_header1="2026/27 Proj.">  ← corn/wheat (sr22/sr18) uses matrix1 / suffix 1
      <m1_region_group_Collection>
        <m1_region_group region1="World  3/">
          <m1_month_group_Collection>
            <m1_month_group forecast_month1="Jun">
              <m1_attribute_group_Collection>
                <m1_attribute_group attribute1="Production">
                  <FormatFiller3><Cell cell_value1="1,300.38" /></FormatFiller3>
"""

import re
import logging
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# ── Section IDs ───────────────────────────────────────────────────────────────
# The WASDE XML splits each commodity into two sections:
#   base section  — historical data (2024/25, 2025/26 Est.)
#   cont section  — current crop year projections (2026/27 Proj.)
# For non-May reports both prior and current months live in the cont section.
# For May reports the prior year must be fetched from the base section.
_SECTIONS = {
    "soybeans": {"cont": "sr28", "base": "sr28"},  # soybeans is combined in one section
    "corn":     {"cont": "sr23", "base": "sr22"},
    "wheat":    {"cont": "sr19", "base": "sr18"},
}

# ── Month helpers ─────────────────────────────────────────────────────────────
_MONTH_ORDER = {
    "Jan":1, "Feb":2, "Mar":3, "Apr":4,  "May":5,  "Jun":6,
    "Jul":7, "Aug":8, "Sep":9, "Oct":10, "Nov":11, "Dec":12,
}

_MONTH_PT = {
    1:"Janeiro", 2:"Fevereiro", 3:"Março",    4:"Abril",
    5:"Maio",    6:"Junho",     7:"Julho",     8:"Agosto",
    9:"Setembro",10:"Outubro",  11:"Novembro", 12:"Dezembro",
}

_MONTH_EN = {
    1:"January", 2:"February", 3:"March",     4:"April",
    5:"May",     6:"June",     7:"July",       8:"August",
    9:"September",10:"October",11:"November",  12:"December",
}

# Attributes we care about (after whitespace normalisation).
# Order matters: longer names first to avoid spurious prefix matches.
_TARGET_ATTRIBUTES = [
    "Ending Stocks",
    "Production",
    "Exports",
    "Imports",
    "Domestic Total",   # matches "Domestic Total", "Domestic Total 2/", etc.
    "Domestic Crush",   # soybeans crush
    "Domestic Feed",    # corn/wheat feed use
]


# ── Normalisation helpers ─────────────────────────────────────────────────────

def _norm_region(raw: str) -> str:
    """Strip leading/trailing spaces and trailing footnote markers like '  2/'."""
    s = raw.strip()
    return re.sub(r'\s+\d+/\s*$', '', s).strip()


def _norm_attr(raw: str) -> str:
    """Collapse whitespace and \\r\\n (encoded as &#xD;&#xA; in XML) to a single space."""
    return re.sub(r'[\r\n\s]+', ' ', raw).strip()


def _parse_float(s: str | None) -> float | None:
    """Parse a cell value, stripping comma thousands separators (e.g. '1,300.38')."""
    if not s:
        return None
    try:
        return float(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None


# ── Matrix parser ─────────────────────────────────────────────────────────────

def _parse_matrix(matrix_elem: ET.Element) -> dict:
    """
    Parses a matrix1 or matrix3 element.

    Returns:
        { normalised_region: { month_abbr: { normalised_attr: float } } }

    Only TARGET_ATTRIBUTES and regions that have data are kept.
    """
    is3 = matrix_elem.tag == "matrix3"
    s   = "2" if is3 else "1"          # attribute suffix
    n   = "3" if is3 else ""           # element name suffix (for group tags)

    rg_coll_tag = f"m1_region_group{n}_Collection"
    rg_tag      = f"m1_region_group{n}"
    mg_coll_tag = f"m1_month_group{s if is3 else ''}_Collection"
    mg_tag      = f"m1_month_group{s if is3 else ''}"
    ag_coll_tag = f"m1_attribute_group{n}_Collection"
    ag_tag      = f"m1_attribute_group{n}"

    result = {}

    rg_coll = matrix_elem.find(rg_coll_tag)
    if rg_coll is None:
        return result

    for rg in rg_coll.findall(rg_tag):
        region = _norm_region(rg.get(f"region{s}", ""))
        if not region:
            continue

        mg_coll_elem = rg.find(mg_coll_tag)
        if mg_coll_elem is None:
            continue

        months = {}
        for mg in mg_coll_elem.findall(mg_tag):
            month = mg.get(f"forecast_month{s}", "")
            if month not in _MONTH_ORDER:
                continue

            ag_coll_elem = mg.find(ag_coll_tag)
            if ag_coll_elem is None:
                continue

            attrs = {}
            for ag in ag_coll_elem.findall(ag_tag):
                raw_attr = ag.get(f"attribute{s}", "")
                attr = _norm_attr(raw_attr)
                # Match targets; allow trailing footnote suffix (e.g., "Domestic Total 2/")
                matched = next(
                    (t for t in _TARGET_ATTRIBUTES
                     if attr == t or attr.startswith(t + " ")),
                    None
                )
                if matched is None:
                    continue
                cell = ag.find(".//Cell")
                if cell is None:
                    continue
                val = _parse_float(cell.get(f"cell_value{s}"))
                if val is not None:
                    attrs[matched] = val

            if attrs:
                months[month] = attrs

        if months:
            result[region] = months

    return result


# ── Matrix finder ─────────────────────────────────────────────────────────────

def _find_matrices(section_elem: ET.Element) -> tuple[ET.Element | None, ET.Element | None]:
    """
    Scans a section's Report element for matrix elements.

    Returns:
        (proj_matrix, prev_matrix)
        proj_matrix  = matrix whose region_header contains "Proj." (current crop year)
        prev_matrix  = last matrix whose region_header contains "Est." before proj_matrix
    """
    proj     = None
    last_est = None

    for child in section_elem.iter():
        if child.tag not in ("matrix1", "matrix2", "matrix3", "matrix5"):
            continue
        for sfx in ("1", "2"):
            header = child.get(f"region_header{sfx}", "")
            if "Proj." in header:
                if proj is None:
                    proj = child
                break
            elif "Est." in header and proj is None:
                # Only collect Est. matrices before the Proj. one
                last_est = child
                break

    return proj, last_est


# ── Month ordering ────────────────────────────────────────────────────────────

def _sort_months(month_keys) -> list[str]:
    return sorted(month_keys, key=lambda m: _MONTH_ORDER.get(m, 99))


# ── Public API ────────────────────────────────────────────────────────────────

def parse_wasde_xml(xml_bytes: bytes, report_year: int, report_month: int) -> dict | None:
    """
    Parses the full WASDE v2 XML and returns a structured dict.

    Result shape:
    {
        "report_year":       int,
        "report_month":      int,
        "report_month_en":   "June 2026",
        "report_month_pt":   "Junho 2026",
        "crop_year":         "2026/27",
        "current_month_name": "Jun",
        "prior_month_name":  "May",     # None for May report
        "is_may_report":     bool,
        "soybeans": {
            "World": {
                "Production":    {"current": 441.34, "prior": 441.54},
                "Ending Stocks": {"current": 124.88, "prior": 124.78},
            },
            "United States": { ... },
            "Brazil": { ... },
            "Argentina": { ... },
        },
        "corn":  { same structure },
        "wheat": { same structure },
    }
    """
    try:
        if xml_bytes.startswith(b'\xef\xbb\xbf'):
            xml_bytes = xml_bytes[3:]   # strip UTF-8 BOM
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        logger.error(f"XML parse error: {e}")
        return None

    report_month_en = f"{_MONTH_EN.get(report_month, '')} {report_year}"
    report_month_pt = f"{_MONTH_PT.get(report_month, '')} {report_year}"

    # Try to get the report month label directly from XML
    sr08_report = root.find("sr08/Report")
    if sr08_report is not None:
        rm = sr08_report.get("Report_Month", "")
        if rm:
            report_month_en = rm

    result = {
        "report_year":     report_year,
        "report_month":    report_month,
        "report_month_en": report_month_en,
        "report_month_pt": report_month_pt,
    }

    crop_year          = None
    current_month_name = None
    prior_month_name   = None
    is_may_report      = False

    for commodity, ids in _SECTIONS.items():
        cont_id = ids["cont"]
        base_id = ids["base"]

        cont_report = root.find(f"{cont_id}/Report")
        if cont_report is None:
            logger.warning(f"Section {cont_id} ({commodity}) not found in XML")
            result[commodity] = {}
            continue

        proj_matrix, _ = _find_matrices(cont_report)
        if proj_matrix is None:
            logger.warning(f"No projected crop-year matrix found in {cont_id}")
            result[commodity] = {}
            continue

        # Extract crop year label — keep "Proj." suffix so the message can show it verbatim
        if crop_year is None:
            for sfx in ("1", "2"):
                hdr = proj_matrix.get(f"region_header{sfx}", "")
                if hdr:
                    crop_year = hdr.strip()   # e.g. "2026/27 Proj."
                    break

        proj_data = _parse_matrix(proj_matrix)

        # Determine which months are available in the projected matrix
        all_months: set[str] = set()
        for region_data in proj_data.values():
            all_months.update(region_data.keys())
        sorted_months = _sort_months(list(all_months))

        if len(sorted_months) >= 2:
            cur_m  = sorted_months[-1]
            prev_m = sorted_months[-2]
        elif len(sorted_months) == 1:
            cur_m         = sorted_months[0]
            prev_m        = None
            is_may_report = True
        else:
            logger.warning(f"No months found in projected matrix for {cont_id}")
            result[commodity] = {}
            continue

        # Record globally (all sections should agree)
        if current_month_name is None:
            current_month_name = cur_m
            prior_month_name   = prev_m

        # For May report: pull prior values from the base (prior crop year) section
        prev_data: dict = {}
        if is_may_report:
            base_report = root.find(f"{base_id}/Report")
            if base_report is not None:
                _, prev_matrix = _find_matrices(base_report)
                if prev_matrix is not None:
                    prev_data = _parse_matrix(prev_matrix)

        # Build per-region attribute dict
        commodity_result: dict = {}
        for region, months_data in proj_data.items():
            cur_attrs  = months_data.get(cur_m,  {})
            prev_attrs = months_data.get(prev_m, {}) if prev_m else {}

            if is_may_report:
                prev_region = prev_data.get(region, {})
                if prev_region:
                    last_prev_month = _sort_months(list(prev_region.keys()))[-1]
                    prev_attrs = prev_region[last_prev_month]

            if not cur_attrs:
                continue

            attr_dict: dict = {}
            for attr in _TARGET_ATTRIBUTES:
                cur_val  = cur_attrs.get(attr)
                prev_val = prev_attrs.get(attr)
                if cur_val is not None:
                    attr_dict[attr] = {"current": cur_val, "prior": prev_val}

            if attr_dict:
                commodity_result[region] = attr_dict

        result[commodity] = commodity_result

    result["crop_year"]          = crop_year or "?"
    result["current_month_name"] = current_month_name
    result["prior_month_name"]   = prior_month_name
    result["is_may_report"]      = is_may_report

    logger.info(
        f"Parsed: {report_month_en} | crop_year={crop_year} | "
        f"months={prior_month_name}→{current_month_name} | may_report={is_may_report}"
    )
    return result


def fmt_delta(prior: float | None, current: float | None) -> tuple[float | None, str]:
    """Returns (delta_float, pt-BR formatted string) e.g. (0.1, '+0,1')."""
    if prior is None or current is None:
        return None, "n/d"
    delta = round(current - prior, 2)
    d1 = round(delta, 1)
    if d1 > 0:
        return delta, f"+{d1:.1f}".replace(".", ",")
    elif d1 < 0:
        return delta, f"{d1:.1f}".replace(".", ",")
    return 0.0, "0,0"
