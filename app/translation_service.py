import re
import os
import json
import logging
import urllib.parse
import requests
from typing import Tuple, Optional, Dict

from app.config import (
    HUGGINGFACEHUB_API_TOKEN,
    INDICTRANS_INDIC_EN,
    INDICTRANS_EN_INDIC,
    INDICTRANS_LANG_CODES,
    SUPPORTED_LANGUAGES
)

logger = logging.getLogger("translation_service")

# Unicode ranges for major Indian scripts
SCRIPT_UNICODE_MAP = {
    "te": (0x0C00, 0x0C7F),  # Telugu
    "hi": (0x0900, 0x097F),  # Devanagari (Hindi, Marathi, Sanskrit, Konkani, Bodo, Dogri, Maithili, Nepali)
    "ta": (0x0B80, 0x0BFF),  # Tamil
    "bn": (0x0980, 0x09FF),  # Bengali / Assamese
    "kn": (0x0C80, 0x0CFF),  # Kannada
    "ml": (0x0D00, 0x0D7F),  # Malayalam
    "gu": (0x0A80, 0x0AFF),  # Gujarati
    "pa": (0x0A00, 0x0A7F),  # Gurmukhi (Punjabi)
    "or": (0x0B00, 0x0B7F),  # Odia
    "ur": (0x0600, 0x06FF),  # Arabic / Urdu / Kashmiri / Sindhi
}

# Common transliteration phonetic markers (Hinglish/Telugish)
HINGLISH_KEYWORDS = {
    "kab", "kya", "kaise", "kahan", "kitna", "kisko", "kyun", "hoga", "hogi", "hai",
    "last", "date", "fees", "fee", "bharna", "deena", "padega", "chahiye", "batao",
    "eppudu", "ela", "ekkada", "chesukovali", "cheyyali", "ivvali", "vastundi", "chudali"
}

# Check deep-translator availability
_deep_translator_available = False
try:
    import deep_translator
    _deep_translator_available = True
    logger.info("deep-translator library is ready.")
except ImportError:
    logger.info("deep-translator not installed, using Google API fallback.")

def detect_script(text: str) -> str:
    """Detect language based on Unicode character distribution."""
    script_counts = {lang: 0 for lang in SCRIPT_UNICODE_MAP}
    total_indic = 0

    for char in text:
        cp = ord(char)
        for lang, (start, end) in SCRIPT_UNICODE_MAP.items():
            if start <= cp <= end:
                script_counts[lang] += 1
                total_indic += 1
                break

    if total_indic > 0:
        best_lang = max(script_counts, key=script_counts.get)
        if script_counts[best_lang] > 0:
            return best_lang

    # Check for Latin/Hinglish/Romanized text
    words = set(re.findall(r"\w+", text.lower()))
    if words.intersection(HINGLISH_KEYWORDS):
        return "hi"  # Default Hinglish to Hindi intent

    return "en"

def translate_via_hf_api(text: str, model_id: str, src_lang: str, tgt_lang: str) -> Optional[str]:
    """Translates via Hugging Face Inference API for IndicTrans2."""
    if not HUGGINGFACEHUB_API_TOKEN:
        return None

    url = f"https://api-inference.huggingface.co/models/{model_id}"
    headers = {
        "Authorization": f"Bearer {HUGGINGFACEHUB_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    src_tag = INDICTRANS_LANG_CODES.get(src_lang, "hin_Deva")
    tgt_tag = INDICTRANS_LANG_CODES.get(tgt_lang, "eng_Latn")
    
    payload = {
        "inputs": text,
        "parameters": {
            "src_lang": src_tag,
            "tgt_lang": tgt_tag
        }
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0 and "translation_text" in data[0]:
                return data[0]["translation_text"].strip()
            elif isinstance(data, dict) and "generated_text" in data:
                return data["generated_text"].strip()
    except Exception as e:
        logger.warning(f"HuggingFace IndicTrans API call exception: {e}")
    return None

def translate_via_free_api(text: str, source: str = "auto", target: str = "en") -> Optional[str]:
    """High-resilience fallback translator."""
    try:
        src = source if source != "auto" else "auto"
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={src}&tl={target}&dt=t&q={urllib.parse.quote(text)}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            parts = [part[0] for part in data[0] if part and part[0]]
            return "".join(parts)
    except Exception as e:
        logger.debug(f"Free API translation failed: {e}")
    return None

def translate_via_deep_translator(text: str, source: str = "auto", target: str = "en") -> Optional[str]:
    if not _deep_translator_available:
        return None
    try:
        from deep_translator import GoogleTranslator
        src = "auto" if source == "auto" else source
        translator = GoogleTranslator(source=src, target=target)
        return translator.translate(text)
    except Exception:
        return None

def translate_to_english(text: str, user_selected_lang: str = "auto") -> Tuple[str, str]:
    """
    Translates student's regional language query to English using IndicTrans (Hugging Face).
    Returns: (translated_query, detected_language_code)
    """
    text = text.strip()
    if not text:
        return "", "en"

    detected_lang = user_selected_lang if user_selected_lang != "auto" else detect_script(text)
    if not detected_lang:
        detected_lang = "en"

    # If already english with no Indic script or Hinglish
    if detected_lang == "en" and all(ord(c) < 128 for c in text):
        words = set(re.findall(r"\w+", text.lower()))
        if not words.intersection(HINGLISH_KEYWORDS):
            return text, "en"

    # 1. Try IndicTrans Hugging Face Model (ai4bharat/indictrans2-indic-en-1B)
    hf_trans = translate_via_hf_api(
        text=text,
        model_id=INDICTRANS_INDIC_EN,
        src_lang=detected_lang,
        tgt_lang="en"
    )
    if hf_trans:
        logger.info(f"[IndicTrans HF] Translated '{text[:30]}...' -> '{hf_trans}'")
        return hf_trans, detected_lang

    # 2. Try deep-translator
    res = translate_via_deep_translator(text, source=detected_lang, target="en")
    if res:
        return res, detected_lang

    # 3. Try HTTP fallback
    res = translate_via_free_api(text, source=detected_lang, target="en")
    if res:
        return res, detected_lang

    return text, detected_lang

def translate_from_english(text: str, target_lang: str) -> str:
    """
    Translates English answer back to student's native language using IndicTrans (Hugging Face).
    """
    if not text or not target_lang or target_lang in ("en", "auto"):
        return text

    # 1. Try IndicTrans Hugging Face Model (ai4bharat/indictrans2-en-indic-1B)
    hf_trans = translate_via_hf_api(
        text=text,
        model_id=INDICTRANS_EN_INDIC,
        src_lang="en",
        tgt_lang=target_lang
    )
    if hf_trans:
        logger.info(f"[IndicTrans HF] Answer translated back to {target_lang}")
        return hf_trans

    # 2. Try deep-translator
    res = translate_via_deep_translator(text, source="en", target=target_lang)
    if res:
        return res

    # 3. Try HTTP fallback
    res = translate_via_free_api(text, source="en", target=target_lang)
    if res:
        return res

    return text
