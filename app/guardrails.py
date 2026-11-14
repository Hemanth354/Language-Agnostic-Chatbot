import re
import logging
from typing import Dict, Any, Optional
from app.config import SUPPORTED_LANGUAGES

logger = logging.getLogger("guardrails")

# -------------------------------------------------------------
# 1. SENSITIVE INFORMATION PATTERNS
# -------------------------------------------------------------

# Indian PII Patterns
AADHAAR_PATTERN = re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")
PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
BANK_IFSC_PATTERN = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.IGNORECASE)

# Confidential & Privacy Keywords
CONFIDENTIAL_KEYWORDS = [
    # Personal & Staff Privacy
    "password", "otp", "pin number", "cvv", "atm pin", "secret key",
    "api key", "auth token", "access token", "private key",
    "personal phone number", "personal mobile number", "personal address",
    "warden phone number", "warden mobile", "warden personal",
    "female student phone", "girl student phone", "student address",
    "faculty salary", "professor salary", "teacher personal phone",
    
    # Examination & Academic Integrity
    "leaked paper", "leak exam paper", "tomorrow exam paper", "question paper leak",
    "hack exam", "hack portal", "change my marks", "increase my marks", "change my grade",
    "alter attendance", "tamper marks", "bypass attendance", "fake certificate",
    "duplicate degree", "answer key before exam", "steal question paper",

    # System & Database Exploitation (Prompt Injection / SQLi)
    "ignore previous instructions", "ignore all instructions", "system prompt",
    "developer mode", "jailbreak", "dan mode", "you are now uncensored",
    "drop table", "select * from", "union select", "-- -", "; drop",
    "delete from users", "database password", "admin credentials", "root password"
]

# Toxic, abusive, self-harm, or violent keywords (Slide 4 requirement)
ABUSE_AND_HARM_KEYWORDS = [
    "kill myself", "suicide", "hang myself", "bomb", "explosive", "weapon",
    "murder", "terrorist", "attack college", "poison", "harm others",
    "fuck", "bitch", "bastard", "asshole", "idiot", "stupid",
    "chutiya", "madarchod", "bhenchod", "gandu", "kamina", "donga", "lanja"
]

# -------------------------------------------------------------
# 2. UNSUPPORTED / FOREIGN SCRIPT DETECTION
# -------------------------------------------------------------

UNSUPPORTED_FOREIGN_SCRIPTS = [
    ("Chinese / CJK", 0x4E00, 0x9FFF),
    ("Japanese (Hiragana/Katakana)", 0x3040, 0x30FF),
    ("Korean (Hangul)", 0xAC00, 0xD7AF),
    ("Russian / Cyrillic", 0x0400, 0x04FF),
    ("Greek", 0x0370, 0x03FF),
    ("Thai", 0x0E00, 0x0E7F),
    ("Hebrew", 0x0590, 0x05FF),
]

# -------------------------------------------------------------
# 3. OUT-OF-DOMAIN / UNRELATED QUERY PATTERNS
# -------------------------------------------------------------

EXPLICIT_OUT_OF_DOMAIN_PATTERNS = [
    r"\b(crypto|bitcoin|ethereum|trading bot|forex|stock market buy)\b",
    r"\b(recipe for|how to cook|ingredients of|bake a cake)\b",
    r"\b(write a python script to|code in java to|write c\+\+ code for)\b",
    r"\b(who won the \d{4} world cup|fifa|ipl match winner|cricket score)\b",
    r"\b(write a love letter|dating advice|girlfriend|boyfriend)\b",
    r"\b(movie review|watch online movie|hollywood box office)\b",
    r"\b(lyrics of song|sing a song for me)\b"
]

# -------------------------------------------------------------
# FUNCTIONAL GUARDRAIL ENGINE (NO CLASSES)
# -------------------------------------------------------------

def validate_language(text: str, user_selected_lang: str = "auto") -> Dict[str, Any]:
    """
    Validates if text is in English or one of the 22 Scheduled Indian languages.
    Blocks unsupported foreign scripts or pure gibberish.
    """
    text = text.strip()
    if not text:
        return {"passed": False, "reason": "empty_query", "message": "Please enter a valid question."}

    # 1. Check for unsupported foreign scripts
    for script_name, start, end in UNSUPPORTED_FOREIGN_SCRIPTS:
        for char in text:
            cp = ord(char)
            if start <= cp <= end:
                logger.warning(f"Guardrail intercepted unsupported script: {script_name}")
                return {
                    "passed": False,
                    "violation_type": "unsupported_language",
                    "script": script_name,
                    "message": (
                        f"🌐 Language Guardrail: Input contains {script_name}, which is not supported. "
                        "Campus Bot supports English and all 22 official Indian languages (Telugu, Hindi, "
                        "Tamil, Bengali, Kannada, Marathi, Malayalam, Gujarati, Punjabi, Odia, Urdu, etc.). "
                        "Please ask your question in one of these languages."
                    )
                }

    # 2. Check for pure symbols / punctuation gibberish without letters or numbers
    alpha_chars = [c for c in text if c.isalnum()]
    if len(alpha_chars) < 2 and len(text) > 3:
        return {
            "passed": False,
            "violation_type": "gibberish",
            "message": "⚠️ Guardrail: Unrecognized query. Please ask a meaningful question using words or sentences."
        }

    # 3. Check for keyboard mash / repetitive consonants (e.g. "asdfghjkl", "zzzzxxxx")
    if len(text) > 6 and re.fullmatch(r"[bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ]+", text):
        return {
            "passed": False,
            "violation_type": "gibberish",
            "message": "⚠️ Guardrail: Query appears to be random keyboard characters. Please type a meaningful academic question."
        }

    return {"passed": True}

def check_sensitive_information(text: str) -> Dict[str, Any]:
    """
    Detects personal PII, credentials, exam leaks, database exploitation, and harmful requests.
    """
    lowered = text.lower()

    # 1. Check PII patterns (Aadhaar, Credit cards, PAN)
    if AADHAAR_PATTERN.search(text):
        return {
            "passed": False,
            "violation_type": "pii_leak",
            "reason": "Aadhaar number detected.",
            "message": "🔒 Privacy Guardrail: Aadhaar card numbers cannot be processed in the chat for security and privacy reasons."
        }

    if CREDIT_CARD_PATTERN.search(text):
        return {
            "passed": False,
            "violation_type": "pii_leak",
            "reason": "Payment card number detected.",
            "message": "🔒 Privacy Guardrail: Credit/Debit card numbers cannot be entered in the chat."
        }

    # 2. Check confidential keywords
    for kw in CONFIDENTIAL_KEYWORDS:
        if kw in lowered:
            logger.warning(f"Sensitive information guardrail triggered for keyword: '{kw}'")
            return {
                "passed": False,
                "violation_type": "sensitive_info",
                "reason": f"Restricted request containing '{kw}'.",
                "message": (
                    "🛡️ Security & Privacy Guardrail: Access to sensitive or restricted information "
                    "(such as personal staff numbers, passwords, confidential exam papers, or unauthorized grade modifications) "
                    "is strictly prohibited under RGUKT institutional policies."
                )
            }

    # 3. Check abuse, harassment, or self-harm
    for kw in ABUSE_AND_HARM_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", lowered):
            logger.warning(f"Abuse/Harm guardrail triggered for: '{kw}'")
            return {
                "passed": False,
                "violation_type": "toxic_or_harmful",
                "reason": "Abusive, inappropriate, or harmful content.",
                "message": (
                    "⚠️ Campus Safety Advisory: Please maintain academic decorum. "
                    "Queries involving abusive language, violence, or inappropriate topics are strictly restricted and logged."
                )
            }

    return {"passed": True}

def check_domain_relevance(query: str) -> Dict[str, Any]:
    """
    Verifies if query is within the domain of campus, academic, student welfare, or institutional circulars.
    """
    lowered = query.lower()

    for pattern in EXPLICIT_OUT_OF_DOMAIN_PATTERNS:
        if re.search(pattern, lowered):
            return {
                "passed": False,
                "violation_type": "out_of_domain",
                "reason": "Explicit out-of-scope query.",
                "message": (
                    "📚 Domain Guardrail: This query is outside the scope of the RGUKT Campus Helpline. "
                    "I am an institutional assistant designed to answer queries regarding college circulars, "
                    "fee deadlines, exam schedules, scholarships, hostel rules, and academic procedures."
                )
            }

    return {"passed": True}

def evaluate_query(raw_query: str, translated_query: str = "", user_lang: str = "auto") -> Dict[str, Any]:
    """
    Comprehensive procedural guardrail pipeline:
    1. Language & Script Validation
    2. Sensitive Information & Confidentiality Check (both raw & translated text)
    3. Domain Relevance Check
    """
    # Step 1: Language Guardrail
    lang_res = validate_language(raw_query, user_lang)
    if not lang_res["passed"]:
        return lang_res

    # Step 2: Sensitive Information Guardrail on raw text
    sens_raw = check_sensitive_information(raw_query)
    if not sens_raw["passed"]:
        return sens_raw

    # Step 3: Sensitive Information Guardrail on translated text (if available)
    if translated_query and translated_query != raw_query:
        sens_trans = check_sensitive_information(translated_query)
        if not sens_trans["passed"]:
            return sens_trans

    # Step 4: Out-of-Domain Guardrail on translated query
    check_text = translated_query or raw_query
    domain_res = check_domain_relevance(check_text)
    if not domain_res["passed"]:
        return domain_res

    return {"passed": True}
