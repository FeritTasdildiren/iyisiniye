"""
iyisiniye Scrapy Ayarlari

Bu dosya Scrapy framework'unun tum yapilandirma parametrelerini icerir.
Proxy middleware, rate limiting, playwright entegrasyonu ve
pipeline yapilandirmalari burada tanimlanir.

Ayarlar hiyerarsisi:
    1. Bu dosyadaki degerler (varsayilan)
    2. Ortam degiskenleri (oncelikli)
    3. Spider bazli ozel ayarlar (en yuksek oncelik)
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ---- Proje Temel Ayarlari ----
BOT_NAME = "iyisiniye_scraper"
SPIDER_MODULES = ["iyisiniye_scraper.spiders"]
NEWSPIDER_MODULE = "iyisiniye_scraper.spiders"

# robots.txt'ye uy (platform TOS kontrolleri spider bazinda yapilir)
ROBOTSTXT_OBEY = True

# Varsayilan istek baslik bilgileri
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
}

# ---- Esitlik / Kibarlık Ayarlari ----
# Istekler arasi bekleme suresi (saniye)
DOWNLOAD_DELAY = 3

# Toplamda ayni anda yapilabilecek istek sayisi
CONCURRENT_REQUESTS = 8

# Tek bir alan adina ayni anda yapilabilecek istek sayisi
CONCURRENT_REQUESTS_PER_DOMAIN = 2

# Tek bir IP adresine ayni anda yapilabilecek istek sayisi
CONCURRENT_REQUESTS_PER_IP = 2

# ---- AutoThrottle Ayarlari ----
# Sunucu yanit surelerine gore otomatik hiz ayarlama
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 3
AUTOTHROTTLE_MAX_DELAY = 30
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

# AutoThrottle debug modunda istatistik gosterimi
AUTOTHROTTLE_DEBUG = False

# ---- Retry (Yeniden Deneme) Ayarlari ----
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# ---- Zaman Asimi ----
DOWNLOAD_TIMEOUT = 30

# ---- Downloader Middleware'leri ----
# Numara ne kucukse o kadar erken calisir (process_request icin)
DOWNLOADER_MIDDLEWARES = {
    # Varsayilan User-Agent middleware'ini devre disi birak
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
    # Ozel User-Agent rotasyonu (en once calismali)
    "iyisiniye_scraper.middlewares.RotatingUserAgentMiddleware": 400,
    # SkyStone Proxy middleware
    "iyisiniye_scraper.middlewares.SkyStoneProxyDownloaderMiddleware": 410,
    # Retry middleware (proxy'den sonra calismali)
    "scrapy.downloadermiddlewares.retry.RetryMiddleware": 500,
}

# ---- Item Pipeline'lari ----
# Numara ne kucukse o kadar erken calisir
ITEM_PIPELINES = {
    # Veri dogrulama (ilk adim)
    "iyisiniye_scraper.pipelines.ValidationPipeline": 100,
    # Tekrar eden verileri ele (ikinci adim)
    "iyisiniye_scraper.pipelines.DeduplicationPipeline": 200,
    # Veritabanina kaydet (son adim)
    "iyisiniye_scraper.pipelines.DatabasePipeline": 300,
}

# ---- SkyStone Proxy API Ayarlari ----
PROXY_API_URL = os.getenv("PROXY_API_URL", "http://127.0.0.1:8000")
PROXY_API_KEY = os.getenv("PROXY_API_KEY", "")
PROXY_MIN_POOL_SIZE = int(os.getenv("PROXY_MIN_POOL_SIZE", "5"))
PROXY_REFRESH_INTERVAL = int(os.getenv("PROXY_REFRESH_INTERVAL", "300"))
PROXY_BAN_THRESHOLD = int(os.getenv("PROXY_BAN_THRESHOLD", "3"))

# ---- User-Agent Rotasyonu ----
# Gercekci tarayici User-Agent listesi
USER_AGENT_LIST = [
    # Chrome (Windows)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Chrome (macOS)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Chrome (Linux)
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Firefox (Windows)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    # Firefox (macOS)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    # Safari (macOS)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    # Edge (Windows)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    # Chrome (Android)
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    # Safari (iOS)
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Mobile/15E148 Safari/604.1",
]

# ---- Playwright Entegrasyonu (scrapy-playwright) ----
# JavaScript render'i gerektiren sayfalar icin kullanilir
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

# Twisted reaktoru (scrapy-playwright icin zorunlu)
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    # Stealth mod icin argümanlar
    "args": [
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-accelerated-2d-canvas",
        "--disable-gpu",
        "--lang=tr-TR",
    ],
}

# Playwright varsayilan sayfa ayarlari
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000  # 30 saniye
PLAYWRIGHT_CONTEXTS = {
    "default": {
        "viewport": {"width": 1920, "height": 1080},
        "locale": "tr-TR",
        "timezone_id": "Europe/Istanbul",
        "user_agent": USER_AGENT_LIST[0],
        # Stealth mod: WebDriver algilamasini engelle
        "java_script_enabled": True,
        "bypass_csp": False,
    },
    "mobile": {
        "viewport": {"width": 390, "height": 844},
        "locale": "tr-TR",
        "timezone_id": "Europe/Istanbul",
        "user_agent": USER_AGENT_LIST[7],  # Android Chrome
        "is_mobile": True,
        "has_touch": True,
    },
}

# ---- Veritabani Ayarlari ----
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://iyisiniye_app:IyS2026!SecureDB#@157.173.116.230:5433/iyisiniye",
)

# ---- Loglama ----
LOG_LEVEL = os.getenv("SCRAPY_LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
LOG_DATEFORMAT = "%Y-%m-%d %H:%M:%S"

# ---- Feed Export (Veri Ciktisi) ----
# Gecici JSON ciktisi (debug icin)
FEEDS = {
    "data/%(name)s_%(time)s.jsonl": {
        "format": "jsonlines",
        "encoding": "utf-8",
        "store_empty": False,
        "overwrite": False,
    },
}

# ---- Diger Ayarlar ----
# Telemetri verisi gonderme
TELNETCONSOLE_ENABLED = False

# HTTP onbellek (gelistirme sirasinda faydali)
# Uretimde devre disi birakilmali
HTTPCACHE_ENABLED = False
HTTPCACHE_EXPIRATION_SECS = 3600
HTTPCACHE_DIR = "httpcache"

# Istekte kabul edilecek durum kodlari
HTTPERROR_ALLOWED_CODES = []

# Request fingerprinting (Scrapy 2.7+)
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
