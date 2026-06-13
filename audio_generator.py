"""
audio_generator.py
Converts WASDE summary text to speech using Groq TTS.
Outputs an OGG/Opus file compatible with Telegram voice messages.
"""

import io
import logging
import subprocess
from pathlib import Path
from groq import Groq
from config import GROQ_API_KEY, TTS_MODEL, TTS_VOICE

logger = logging.getLogger(__name__)

client = Groq(api_key=GROQ_API_KEY)


def text_to_speech(text: str, output_path: str) -> bool:
    """
    Converts text to OGG/Opus audio file for Telegram.
    Returns True on success.

    Strategy:
    1. Call Groq TTS API → get WAV bytes
    2. Convert WAV → OGG Opus via ffmpeg (required for Telegram voice)
    """
    try:
        wav_path = output_path.replace(".ogg", "_tmp.wav")

        # ── Step 1: Groq TTS ─────────────────────────────────────────────────
        # Truncate text to avoid rate limits (~4000 chars is safe)
        tts_text = text[:4000]

        response = client.audio.speech.create(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            input=tts_text,
            response_format="wav",
        )
        audio_bytes = response.read()

        # Save WAV temporarily
        with open(wav_path, "wb") as f:
            f.write(audio_bytes)

        # ── Step 2: Convert to OGG Opus ──────────────────────────────────────
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", wav_path,
                "-c:a", "libopus",
                "-b:a", "32k",
                "-vbr", "on",
                output_path,
            ],
            capture_output=True, timeout=60
        )

        # Cleanup temp WAV
        Path(wav_path).unlink(missing_ok=True)

        if result.returncode != 0:
            logger.error(f"ffmpeg conversion failed: {result.stderr.decode()}")
            return False

        logger.info(f"Audio saved: {output_path} ({Path(output_path).stat().st_size:,} bytes)")
        return True

    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        return False


def build_tts_script(data: dict, market_prices: dict) -> str:
    """
    Builds the audio narration script in Portuguese (pt-BR).
    Avoids special characters that confuse TTS.
    """
    month  = data.get("report_month", "este mês")
    changes = data.get("key_changes", [])

    soy_price   = _price_str(market_prices.get("Soja"))
    corn_price  = _price_str(market_prices.get("Milho"))
    wheat_price = _price_str(market_prices.get("Trigo"))

    lines = [
        f"USDA WASDE, {month}.",
        "",
        "O Departamento de Agricultura dos Estados Unidos divulgou hoje o relatório "
        "mensal de oferta e demanda mundial para grãos e oleaginosas.",
        "",
        "Mercado no momento da divulgação:",
        f"Soja: {soy_price}.",
        f"Milho: {corn_price}.",
        f"Trigo: {wheat_price}.",
        "",
        "Principais alterações:",
    ]

    for change in changes:
        # Strip bullet and markdown symbols for cleaner TTS
        clean = change.lstrip("•●-– ").strip()
        lines.append(clean)

    return " ".join(lines)


def _price_str(price_info: dict | None) -> str:
    if not price_info or price_info.get("price") is None:
        return "preço indisponível"
    p = price_info["price"]
    contract = price_info.get("contract", "")
    return f"{p:,.2f} centavos por bushel, contrato {contract}"
