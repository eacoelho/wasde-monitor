"""
wasde_parser.py
Uses Groq LLM to extract structured supply/demand data from raw WASDE text.
Returns a dict with production and ending stocks for soy, corn, wheat.

This approach is intentionally format-agnostic — if the USDA changes
PDF layout (as in May crop-year flip), the LLM still interprets it correctly.
"""

import json
import logging
import re
from groq import Groq
from config import GROQ_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

client = Groq(api_key=GROQ_API_KEY)


EXTRACTION_PROMPT = """
You are an agricultural commodities analyst. Below is a USDA WASDE report in two sections:
1. HIGHLIGHTS (pages 1-5): narrative text with key changes — use for key_changes only.
2. SUPPLY/DEMAND TABLES: key rows from commodity-specific tables — use for all numeric fields.

TABLE READING RULES:
- Columns are ordered oldest-to-newest crop year; "prior" = second-to-last column, "current" = last column.
- For SOYBEANS: use only the SOYBEANS table (world production ~420-450 MMT). Do NOT use the Oilseeds summary (~640-700 MMT).
- For CORN: use only the CORN table (world production ~1,200-1,400 MMT). Do NOT use the Coarse Grains summary (~1,450-1,600 MMT).
- For WHEAT: use only the WHEAT table (world production ~780-840 MMT).
- World-row values in these tables are already in MMT.
- US production rows are in MILLION BUSHELS — always convert before returning.

Extract the following data and return ONLY a valid JSON object (no markdown, no explanation):

{{
  "report_month": "Month Year",  // e.g. "Junho 2026"
  "report_month_en": "Month Year",  // e.g. "June 2026"
  "is_crop_year_flip": true/false,  // true if this is the May report (new crop year introduced)
  "crop_years_shown": ["25/26", "26/27"],  // list the crop years present in the report
  "soybeans": {{
    "production": {{
      "usa_prior": X,      // previous month estimate
      "usa_current": X,    // this month estimate
      "brazil_prior": X,
      "brazil_current": X,
      "argentina_prior": X,
      "argentina_current": X,
      "world_prior": X,
      "world_current": X
    }},
    "ending_stocks": {{
      "usa_prior": X,
      "usa_current": X,
      "world_prior": X,
      "world_current": X
    }}
  }},
  "corn": {{
    "production": {{
      "usa_prior": X,
      "usa_current": X,
      "brazil_prior": X,
      "brazil_current": X,
      "argentina_prior": X,
      "argentina_current": X,
      "world_prior": X,
      "world_current": X
    }},
    "ending_stocks": {{
      "usa_prior": X,
      "usa_current": X,
      "world_prior": X,
      "world_current": X
    }}
  }},
  "wheat": {{
    "production": {{
      "usa_prior": X,
      "usa_current": X,
      "world_prior": X,
      "world_current": X
    }},
    "ending_stocks": {{
      "usa_prior": X,
      "usa_current": X,
      "world_prior": X,
      "world_current": X
    }}
  }},
  "key_changes": [
    // EXACTLY 3 bullets in Portuguese (pt-BR) — one per commodity: soja, milho, trigo.
    // Always mention the crop year (e.g. "safra 2026/27"). Use MMT values. NEVER bushels.
    // 1-2 sentences, concise, analytical.
    "• Soja: safra 2026/27 ...",
    "• Milho: safra 2026/27 ...",
    "• Trigo: safra 2026/27 ..."
  ]
}}

Use null for any value that cannot be found.
CRITICAL — ALL numbers MUST be in million metric tons (MMT). NEVER use bushels.
If the report shows values in million bushels, convert before returning:
  corn: million bushels ÷ 39.368 = MMT
  soybeans: million bushels ÷ 36.744 = MMT
  wheat: million bushels ÷ 36.744 = MMT
All production numbers in million metric tons (MMT).
All ending stocks in million metric tons (MMT).
Prior = previous month's estimate. Current = this month's revised estimate.
For the May report (crop year flip), use the MOST RECENT crop year's data for "current" and the prior month's old crop year data for "prior" where applicable. Note differences in key_changes.

WASDE REPORT TEXT:
{text}
"""


def _clean_json(raw: str) -> str:
    """
    Normalises common LLM JSON formatting issues before parsing.

    Handles (in order):
    1. Markdown code fences  ``` json ... ```
    2. JS-style // line comments
    3. JS-style /* */ block comments
    4. Comma as thousands separator inside numbers  e.g. 4,461 → 4461
    5. Trailing commas before } or ]
    6. Extract the outermost {...} in case the model adds prose around it
    """
    # 1. Markdown fences
    raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    # 2. // line comments
    raw = re.sub(r"\s*//[^\n]*", "", raw)
    # 3. /* */ block comments
    raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)
    # 4. Thousands-separator commas inside numbers: "4,461" → "4461"
    #    Matches a comma between a digit and exactly 3 digits followed by non-digit
    for _ in range(3):                       # up to 3 passes for 7-digit numbers
        raw = re.sub(r"(?<=\d),(?=\d{3}(?:[^0-9]|$))", "", raw)
    # 5. Trailing commas
    raw = re.sub(r",(\s*[}\]])", r"\1", raw)
    # 6. Extract JSON object if prose surrounds it
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)
    return raw


def extract_wasde_data(wasde_text: str) -> dict | None:
    """
    Sends WASDE text to Groq LLM and returns parsed JSON dict.
    """
    truncated = wasde_text[:50000]
    prompt = EXTRACTION_PROMPT.format(text=truncated)

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=3000,
            )
            raw = response.choices[0].message.content.strip()
            raw = _clean_json(raw)

            data = json.loads(raw)
            logger.info("WASDE data extracted successfully by LLM.")
            return data

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error on attempt {attempt+1}: {e} | raw[:300]: {raw[:300]!r}")
            if attempt == 2:
                logger.error("All extraction attempts failed (JSON).")
                return {"parse_error": True, "raw_response": raw}
        except Exception as e:
            logger.error(f"LLM extraction error on attempt {attempt+1}: {e}")
            if attempt == 2:
                return None

    return None


def format_delta(prior, current) -> tuple[float | None, str]:
    """Returns (delta_value, formatted_string) using pt-BR decimal comma."""
    if prior is None or current is None:
        return None, "n/d"
    delta = round(current - prior, 1)
    if delta > 0:
        return delta, f"+{delta:.1f}".replace(".", ",")
    elif delta < 0:
        return delta, f"{delta:.1f}".replace(".", ",")
    else:
        return 0.0, "0,0"
