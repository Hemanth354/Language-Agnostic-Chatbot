import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

# Server Config
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")

# API Keys & Hugging Face Token
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
HUGGINGFACEHUB_API_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN", "").strip() or os.getenv("HF_TOKEN", "").strip()

# Model Configurations as requested
LLM_MODEL_NAME = os.getenv("LLM_MODEL", "gemma2-9b-it")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
INDICTRANS_INDIC_EN = os.getenv("INDICTRANS_INDIC_EN_MODEL", "ai4bharat/indictrans2-indic-en-1B")
INDICTRANS_EN_INDIC = os.getenv("INDICTRANS_EN_INDIC_MODEL", "ai4bharat/indictrans2-en-indic-1B")

# Channels
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "").strip()
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "").strip()
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "campus_bot_verify_token")

# Storage Paths
DATA_DIR = BASE_DIR / "data"
CIRCULAR_DIR = DATA_DIR / "circulars"
CHROMA_DIR = DATA_DIR / "chromadb"
DB_PATH = DATA_DIR / "campus_bot.db"

# Ensure essential directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
CIRCULAR_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# 22 Scheduled Indian Languages supported
SUPPORTED_LANGUAGES = {
    "auto": "Auto Detect",
    "en": "English",
    "te": "Telugu (తెలుగు)",
    "hi": "Hindi (हिन्दी)",
    "ta": "Tamil (தமிழ்)",
    "bn": "Bengali (বাংলা)",
    "mr": "Marathi (मराठी)",
    "kn": "Kannada (ಕನ್ನಡ)",
    "ml": "Malayalam (മലയാളം)",
    "gu": "Gujarati (ગુજરાતી)",
    "pa": "Punjabi (ਪੰਜਾਬੀ)",
    "or": "Odia (ଓଡ଼ିଆ)",
    "ur": "Urdu (اردو)",
    "as": "Assamese (অসমীয়া)",
    "sa": "Sanskrit (संस्कृतम्)",
    "ne": "Nepali (नेपाली)",
    "kok": "Konkani (कोंकणी)",
    "mai": "Maithili (मैथिली)",
    "doi": "Dogri (डोगरी)",
    "brx": "Bodo (बर')",
    "ks": "Kashmiri (کٲشُر)",
    "sd": "Sindhi (سنڌي)",
    "mni": "Manipuri (মৈতৈলোন্)",
    "sat": "Santali (ᱥᱟᱱᱛᱟᱲᱤ)"
}

# IndicTrans FLORES language code mapping
INDICTRANS_LANG_CODES = {
    "te": "tel_Telg",
    "hi": "hin_Deva",
    "ta": "tam_Taml",
    "bn": "ben_Beng",
    "mr": "mar_Deva",
    "kn": "kan_Knda",
    "ml": "mal_Mlym",
    "gu": "guj_Gujr",
    "pa": "pan_Guru",
    "or": "ory_Orya",
    "ur": "urd_Arab",
    "as": "asm_Beng",
    "sa": "san_Deva",
    "ne": "npi_Deva",
    "kok": "gom_Deva",
    "mai": "mai_Deva",
    "doi": "doi_Deva",
    "brx": "brx_Deva",
    "ks": "kas_Arab",
    "sd": "snd_Arab",
    "mni": "mni_Beng",
    "sat": "sat_Olck",
    "en": "eng_Latn"
}

# Web Speech API language tag mapping
SPEECH_LANG_CODES = {
    "en": "en-IN",
    "te": "te-IN",
    "hi": "hi-IN",
    "ta": "ta-IN",
    "bn": "bn-IN",
    "mr": "mr-IN",
    "kn": "kn-IN",
    "ml": "ml-IN",
    "gu": "gu-IN",
    "pa": "pa-IN",
    "ur": "ur-IN",
    "ne": "ne-NP"
}
