"""
iyisiniye Scraper Yapilandirma Dosyasi

Tum scraper ayarlari burada merkezi olarak yonetilir.
Ortam degiskenleri .env dosyasindan yuklenir.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# .env dosyasini yukle
load_dotenv()

# Temel dizinler
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Veritabani
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://iyisiniye_app:IyS2026!SecureDB#@157.173.116.230:5433/iyisiniye",
)

# Scraper genel ayarlari
RATE_LIMIT = float(os.getenv("SCRAPER_RATE_LIMIT", "2.0"))  # Saniye
MAX_RETRIES = int(os.getenv("SCRAPER_MAX_RETRIES", "3"))
USER_AGENT = os.getenv(
    "SCRAPER_USER_AGENT",
    "Mozilla/5.0 (compatible; iyisiniye-bot/1.0)",
)
REQUEST_TIMEOUT = int(os.getenv("SCRAPER_REQUEST_TIMEOUT", "30"))  # Saniye

# Google Maps
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
GOOGLE_MAPS_MAX_RESULTS = int(os.getenv("GOOGLE_MAPS_MAX_RESULTS", "100"))

# Yemeksepeti
YEMEKSEPETI_BASE_URL = "https://www.yemeksepeti.com"
YEMEKSEPETI_MAX_PAGES = int(os.getenv("YEMEKSEPETI_MAX_PAGES", "50"))

# Trendyol Yemek
TRENDYOL_BASE_URL = "https://www.trendyol.com/yemek"
TRENDYOL_MAX_PAGES = int(os.getenv("TRENDYOL_MAX_PAGES", "50"))

# NLP ayarlari
NLP_MODEL_NAME = os.getenv("NLP_MODEL_NAME", "dbmdz/bert-base-turkish-cased")
SENTIMENT_MODEL_NAME = os.getenv(
    "SENTIMENT_MODEL_NAME",
    "savasy/bert-base-turkish-sentiment-cased",
)

# Eslestirme ayarlari
FUZZY_MATCH_THRESHOLD = float(os.getenv("FUZZY_MATCH_THRESHOLD", "85.0"))
MAX_MATCH_DISTANCE_KM = float(os.getenv("MAX_MATCH_DISTANCE_KM", "0.5"))

# Hedef sehirler (baslangic)
TARGET_CITIES = [
    "istanbul",
    "ankara",
    "izmir",
    "antalya",
    "bursa",
    "gaziantep",
]

# SkyStone Proxy API
PROXY_API_URL = os.getenv("PROXY_API_URL", "http://127.0.0.1:8000")
PROXY_API_KEY = os.getenv("PROXY_API_KEY", "")
PROXY_MIN_POOL_SIZE = int(os.getenv("PROXY_MIN_POOL_SIZE", "5"))
PROXY_REFRESH_INTERVAL = int(os.getenv("PROXY_REFRESH_INTERVAL", "300"))  # Saniye
PROXY_BAN_THRESHOLD = int(os.getenv("PROXY_BAN_THRESHOLD", "3"))

# Loglama
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "scraper.log"))
