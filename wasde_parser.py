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
You are an agricultural commodities analyst. Below is the raw text of a USDA WASDE report.

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
    // EXACTLY 3 bullet points in Portuguese (pt-BR) — one per commodity in this order: soja, milho, trigo.
    // Each bullet summarizes the most important production or stocks revision for that commodity.
    // Concise analytical tone, 1-2 sentences. Use ONLY metric tons — NEVER bushels.
    "• Soja: ...",
    "• Milho: ...",
    "• Trigo: ..."
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


def extract_wasde_data(wasde_text: str) -> dict | None:
    """
    Sends WASDE text to Groq LLM and returns parsed JSON dict.
    """
    # Truncate to ~50k chars to stay within context limits
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

            # Strip markdown fences if present
            raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("```").strip()

            data = json.loads(raw)
            logger.info("WASDE data extracted successfully by LLM.")
            return data

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error on attempt {attempt+1}: {e}")
            if attempt == 2:
                logger.error("All extraction attempts failed (JSON). Returning raw text.")
                return {"parse_error": True, "raw_response": raw}
        except Exception as e:
            logger.error(f"LLM extraction error on attempt {attempt+1}: {e}")
            if attempt == 2:
                return None

    return None


def format_delta(prior, current) -> tuple[float | None, str]:
    """
    Returns (delta_value, formatted_string).
    """
    if prior is None or current is None:
        return None, "n/d"
    delta = round(current - prior, 2)
    if delta > 0:
        return delta, f"+{delta:.1f}"
    elif delta < 0:
        return delta, f"{delta:.1f}"
    else:
        return 0.0, "0,0"
