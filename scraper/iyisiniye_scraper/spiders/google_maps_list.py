"""
Google Maps Restoran Listeleme Spider'i

Istanbul sinirlarinda grid tabanli koordinat taramasi yaparak
Google Maps uzerinden restoran listelerini toplar.

Grid Sistemi:
    - Istanbul bounding box: KD(41.20, 29.15), GB(40.80, 28.60)
    - 15x15 = 225 arama noktasi
    - Her nokta zoom=15 ile taranir

Playwright Gereksinimleri:
    - JS render zorunlu (Google Maps dinamik icerik yukler)
    - Stealth mod (navigator.webdriver gizleme)
    - Sonuc paneli scroll ile sayfalama

Anti-Bot Onlemleri:
    - Rastgele gecikmeler (insan benzeri davranis)
    - Fare hareketi simulasyonu
    - Cookie kabul diyalogu otomatik kapatma
    - CAPTCHA algilama ve loglama
"""

import asyncio
import math
import json
import random
import re
import time as _time
from collections import defaultdict
from typing import Any, Generator
from urllib.parse import unquote

import requests as http_requests
import scrapy
from loguru import logger
from scrapy.http import Response

from ..items import RestaurantItem, ReviewItem
from .base_spider import BaseSpider


# --- Istanbul Ilce Koordinatlari (yaklasik merkez) ---
# Koordinat bazli ilce tespiti icin kullanilir

ISTANBUL_ILCE_KOORDINATLARI: dict[str, tuple[float, float]] = {
    "adalar": (40.8764, 29.0906),
    "arnavutkoy": (41.1848, 28.7397),
    "atasehir": (40.9923, 29.1124),
    "avcilar": (40.9797, 28.7216),
    "bagcilar": (41.0346, 28.8568),
    "bahcelievler": (41.0015, 28.8601),
    "bakirkoy": (40.9811, 28.8770),
    "basaksehir": (41.0934, 28.8024),
    "bayrampasa": (41.0410, 28.9082),
    "besiktas": (41.0420, 29.0060),
    "beykoz": (41.1270, 29.0950),
    "beylikduzu": (40.9835, 28.6439),
    "beyoglu": (41.0370, 28.9770),
    "buyukcekmece": (41.0200, 28.5850),
    "catalca": (41.1433, 28.4600),
    "cekmekoy": (41.0350, 29.1700),
    "esenler": (41.0430, 28.8760),
    "esenyurt": (41.0280, 28.6770),
    "eyupsultan": (41.0820, 28.9330),
    "fatih": (41.0096, 28.9490),
    "gaziosmanpasa": (41.0665, 28.9104),
    "gungoren": (41.0150, 28.8830),
    "kadikoy": (40.9817, 29.0636),
    "kagithane": (41.0800, 28.9710),
    "kartal": (40.8900, 29.1910),
    "kucukcekmece": (41.0000, 28.7800),
    "maltepe": (40.9340, 29.1340),
    "pendik": (40.8760, 29.2600),
    "sancaktepe": (41.0000, 29.2200),
    "sariyer": (41.1670, 29.0500),
    "silivri": (41.0750, 28.2470),
    "sultanbeyli": (40.9600, 29.2630),
    "sultangazi": (41.0980, 28.8710),
    "sile": (41.1780, 29.6100),
    "sisli": (41.0600, 28.9870),
    "tuzla": (40.8180, 29.3000),
    "umraniye": (41.0270, 29.0930),
    "uskudar": (41.0234, 29.0156),
    "zeytinburnu": (40.9940, 28.9050),
}

# Turkce ilce adi → normalize edilmis ilce adi eslestirmesi
# (kart metninde Turkce karakterli ilce adlari icin)
_ILCE_METIN_ESLESTIRME: dict[str, str] = {
    "kadıköy": "kadikoy", "kadikoy": "kadikoy",
    "beşiktaş": "besiktas", "besiktas": "besiktas",
    "şişli": "sisli", "sisli": "sisli",
    "beyoğlu": "beyoglu", "beyoglu": "beyoglu",
    "üsküdar": "uskudar", "uskudar": "uskudar",
    "sarıyer": "sariyer", "sariyer": "sariyer",
    "bakırköy": "bakirkoy", "bakirkoy": "bakirkoy",
    "ataşehir": "atasehir", "atasehir": "atasehir",
    "ümraniye": "umraniye", "umraniye": "umraniye",
    "küçükçekmece": "kucukcekmece", "kucukcekmece": "kucukcekmece",
    "büyükçekmece": "buyukcekmece", "buyukcekmece": "buyukcekmece",
    "başakşehir": "basaksehir", "basaksehir": "basaksehir",
    "bayrampaşa": "bayrampasa", "bayrampasa": "bayrampasa",
    "bağcılar": "bagcilar", "bagcilar": "bagcilar",
    "bahçelievler": "bahcelievler", "bahcelievler": "bahcelievler",
    "güngören": "gungoren", "gungoren": "gungoren",
    "gaziosmanpaşa": "gaziosmanpasa", "gaziosmanpasa": "gaziosmanpasa",
    "kağıthane": "kagithane", "kagithane": "kagithane",
    "eyüpsultan": "eyupsultan", "eyupsultan": "eyupsultan",
    "sultangazi": "sultangazi",
    "çekmeköy": "cekmekoy", "cekmekoy": "cekmekoy",
    "sancaktepe": "sancaktepe",
    "sultanbeyli": "sultanbeyli",
    "beylikdüzü": "beylikduzu", "beylikduzu": "beylikduzu",
    "esenyurt": "esenyurt",
    "avcılar": "avcilar", "avcilar": "avcilar",
    "arnavutköy": "arnavutkoy", "arnavutkoy": "arnavutkoy",
    "çatalca": "catalca", "catalca": "catalca",
    "silivri": "silivri",
    "şile": "sile", "sile": "sile",
    "zeytinburnu": "zeytinburnu",
    "esenler": "esenler",
    "pendik": "pendik",
    "kartal": "kartal",
    "maltepe": "maltepe",
    "tuzla": "tuzla",
    "beykoz": "beykoz",
    "adalar": "adalar",
    "fatih": "fatih",
}


def _ilce_belirle_koordinat(lat: float, lng: float) -> str:
    """
    Koordinattan en yakin Istanbul ilcesini belirler.

    Basit oklid mesafesi ile en yakin ilce merkezi bulunur.

    Args:
        lat: Enlem
        lng: Boylam

    Returns:
        Normalize edilmis ilce adi (orn: "kadikoy", "besiktas")
    """
    min_mesafe = float("inf")
    en_yakin = ""
    for ilce, (ilat, ilng) in ISTANBUL_ILCE_KOORDINATLARI.items():
        mesafe = (lat - ilat) ** 2 + (lng - ilng) ** 2
        if mesafe < min_mesafe:
            min_mesafe = mesafe
            en_yakin = ilce
    return en_yakin


def _ilce_belirle_metin(adres: str) -> str:
    """
    Adres metninden ilce adini cikarir.

    Args:
        adres: Restoran adres metni

    Returns:
        Normalize edilmis ilce adi veya bos string
    """
    if not adres:
        return ""
    adres_kucuk = adres.lower()
    for metin, ilce in _ILCE_METIN_ESLESTIRME.items():
        if metin in adres_kucuk:
            return ilce
    return ""


# --- Playwright sayfa baslatma callback'i ---

async def stealth_init_callback(page: Any, request: Any = None) -> None:
    """
    Playwright sayfasi olusturuldugunda stealth ayarlarini uygular.

    navigator.webdriver ozelligini gizleyerek bot algilamasini zorlasitirir.
    Ayrica WebGL ve Canvas fingerprinting'e karsi temel onlemler ekler.
    """
    await page.add_init_script("""
        // navigator.webdriver gizle
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });

        // Chrome runtime taklit et
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {},
        };

        // Permissions API'yi gercekci yap
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );

        // plugins dizisini doldur (bos olursa bot algilanir)
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });

        // languages dizisini ayarla
        Object.defineProperty(navigator, 'languages', {
            get: () => ['tr-TR', 'tr', 'en-US', 'en'],
        });
    """)


class GoogleMapsListSpider(BaseSpider):
    """
    Google Maps restoran listeleme spider'i.

    Istanbul sinirlarinda grid tabanli arama yaparak restoran
    bilgilerini toplar. Playwright ile JS render yapar ve
    sonuc panelini scroll ederek tum sonuclari yukler.

    Kullanim:
        scrapy crawl google_maps_list
        scrapy crawl google_maps_list -a grid_size=10
        scrapy crawl google_maps_list -a max_scroll=40
    """

    name = "google_maps_list"
    platform_name = "google_maps"

    # robots.txt Google Maps icin devre disi (JS uygulamasi)
    # Proxy uzerinden yeniden deneme limiti (grid noktasi basina)
    MAX_PROXY_RETRY = 100

    # 0 restoran bulunan grid icin ek deneme sayisi
    MAX_EMPTY_RETRY = 2  # toplam 3 deneme (1 orijinal + 2 ek)

    # Proxy rate limit: ayni proxy 1 dakikada max bu kadar kullanilabilir
    PROXY_RATE_LIMIT = 2
    PROXY_RATE_WINDOW = 60  # saniye

    # --- Alt-Grid Sistemi ---
    # Bu sayi ve uzerinde kart bulunan gridler 2x2 alt-grid'e bolunur
    CARD_LIMIT_THRESHOLD = 100
    # Alt-grid'ler arasi yuzdelik ortusme (kenar kayiplarini onlemek icin)
    ALT_GRID_OVERLAP = 0.15
    # Google Maps maksimum zoom seviyesi (dogal derinlik siniri)
    MAX_ZOOM = 21

    custom_settings: dict[str, Any] = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS": 3,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 3,
        "DOWNLOAD_DELAY": 5,
        "DOWNLOAD_TIMEOUT": 10,
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 15000,
        "PLAYWRIGHT_CONTEXTS": {},  # Context'ler request bazli olusturulacak
        # Proxy spider tarafindan playwright_context_kwargs ile yonetiliyor,
        # Scrapy middleware'i devre disi.
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
            "iyisiniye_scraper.middlewares.RotatingUserAgentMiddleware": 400,
            "iyisiniye_scraper.middlewares.SkyStoneProxyDownloaderMiddleware": None,
            "scrapy.downloadermiddlewares.retry.RetryMiddleware": 500,
        },
    }

    # --- Istanbul Bounding Box ---
    ISTANBUL_NE_LAT = 41.20
    ISTANBUL_NE_LNG = 29.15
    ISTANBUL_SW_LAT = 40.80
    ISTANBUL_SW_LNG = 28.60

    # --- Varsayilan Grid ve Scroll Ayarlari ---
    DEFAULT_GRID_SIZE = 15
    DEFAULT_MAX_SCROLL = 60
    DEFAULT_ZOOM = 15

    # --- Checkpoint ---
    CHECKPOINT_DOSYA = "/opt/iyisiniye/scraper/checkpoint_grids.json"

    # --- Arama URL Sablonu ---
    SEARCH_URL_TEMPLATE = (
        "https://www.google.com/maps/search/restoran/@{lat},{lng},{zoom}z?hl=tr"
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Spider parametrelerini yukler ve grid noktalarini hesaplar.

        Args:
            grid_size: Grid boyutu (varsayilan: 15, toplam = grid_size^2)
            max_scroll: Sonuc panelinde maksimum scroll sayisi (varsayilan: 60)
            zoom: Harita zoom seviyesi (varsayilan: 15)
        """
        super().__init__(*args, **kwargs)

        # Playwright zorunlu
        self.use_playwright = True

        # Parametreleri al
        self.grid_size: int = int(kwargs.get("grid_size", self.DEFAULT_GRID_SIZE))
        self.max_scroll: int = int(kwargs.get("max_scroll", self.DEFAULT_MAX_SCROLL))
        self.zoom: int = int(kwargs.get("zoom", self.DEFAULT_ZOOM))

        # Tekrar kontrol seti (source_id bazli deduplication)
        self.gorulmus_restoranlar: set[str] = set()

        # Grid tabanli istatistikler
        self.scrape_stats.update({
            "toplam_grid_noktasi": self.grid_size ** 2,
            "taranan_grid_noktasi": 0,
            "benzersiz_restoran": 0,
            "tekrar_eden_restoran": 0,
            "captcha_tespit": 0,
            "ardisik_hata": 0,
        })

        # Proxy havuzu
        self.proxy_pool: list[str] = []
        self._basarili_proxyler: list[str] = []  # Calistigi kanitlanmis proxy'ler
        self._proxy_kullanim: defaultdict[str, list[float]] = defaultdict(list)  # Rate limit
        self._context_sayaci: int = 0
        self._proxy_havuzu_doldur()

        # Grid noktalarini hesapla
        self.grid_noktalari: list[tuple[float, float]] = self._grid_noktalari_hesapla()

        # Alt-grid sistemi
        self.scrape_stats.update({
            "alt_grid_olusturuldu": 0,
            "alt_grid_tamamlandi": 0,
            "alt_grid_max_derinlik": 0,
        })
        # Dogrulama gecisi kontrolu
        self._dogrulama_gecisi_aktif: bool = False
        self._ana_tarama_tamamlandi: bool = False
        # Ana taramada kac grid tamamlandi (alt-grid'ler haric)
        self._tamamlanan_ana_gridler: int = 0
        # Bekleyen alt-grid sayaci (0 oldugunda ana tarama bitmis demek)
        self._bekleyen_alt_gridler: int = 0

        # Checkpoint: tamamlanan grid koordinatlari
        self._checkpoint_yukle()

        # Alt-grid parent takibi: parent_key -> bekleyen alt-grid sayisi
        self._parent_bekleyen: defaultdict[str, int] = defaultdict(int)

        # DB'den mevcut source_id'leri yukle (restart dedup)
        self._db_dedup_yukle()

        self.spider_logger.info(
            f"GoogleMapsListSpider baslatildi: "
            f"grid={self.grid_size}x{self.grid_size} ({len(self.grid_noktalari)} nokta), "
            f"zoom={self.zoom}, maks_scroll={self.max_scroll}, "
            f"proxy_havuzu={len(self.proxy_pool)}"
        )

    def _checkpoint_yukle(self) -> None:
        """Checkpoint dosyasindan tamamlanan grid koordinatlarini yukler."""
        self._tamamlanan_gridler: set[str] = set()
        try:
            with open(self.CHECKPOINT_DOSYA, "r") as f:
                veri = json.load(f)
                self._tamamlanan_gridler = set(veri.get("gridler", []))
                kayitli = veri.get("restoranlar", [])
                self.gorulmus_restoranlar.update(kayitli)
            self.spider_logger.info(
                f"Checkpoint yuklendi: {len(self._tamamlanan_gridler)} grid, {len(kayitli)} restoran"
            )
        except FileNotFoundError:
            self.spider_logger.info("Checkpoint dosyasi bulunamadi, sifirdan baslanacak")
        except Exception as e:
            self.spider_logger.warning(f"Checkpoint yukleme hatasi: {e}")

    def _checkpoint_kaydet(self) -> None:
        """Tamamlanan grid koordinatlarini checkpoint dosyasina yazar."""
        try:
            veri = {
                "gridler": list(self._tamamlanan_gridler),
                "restoranlar": list(self.gorulmus_restoranlar),
            }
            with open(self.CHECKPOINT_DOSYA, "w") as f:
                json.dump(veri, f)
        except Exception as e:
            self.spider_logger.warning(f"Checkpoint kaydetme hatasi: {e}")

    def _grid_key(self, lat: float, lng: float) -> str:
        """Grid koordinatlarindan benzersiz key olusturur."""
        return "%.6f,%.6f" % (lat, lng)

    def _db_dedup_yukle(self) -> None:
        """DB'den mevcut source_id'leri yukleyerek dedup setini doldurur."""
        import os
        try:
            import psycopg2
            db_url = os.getenv(
                "DATABASE_URL",
                "postgresql://iyisiniye_app:IyS2026SecureDB@localhost:5433/iyisiniye",
            )
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            cur.execute(
                "SELECT source_id FROM restaurant_platforms WHERE platform = 'google_maps'"
            )
            rows = cur.fetchall()
            for row in rows:
                if row[0]:
                    self.gorulmus_restoranlar.add(row[0])
            cur.close()
            conn.close()
            self.spider_logger.info(f"DB'den {len(rows)} source_id yuklendi (dedup)")
        except Exception as e:
            self.spider_logger.warning(f"DB dedup yukleme hatasi (devam ediliyor): {e}")

    def _proxy_havuzu_doldur(self) -> None:
        """SkyStone Proxy API'den HTTP proxy listesini ceker."""
        import os
        api_url = os.getenv("PROXY_API_URL", "http://127.0.0.1:8000")
        api_key = os.getenv("PROXY_API_KEY", "")

        for tier in ("high", "medium", "low"):
            try:
                resp = http_requests.get(
                    f"{api_url}/api/v1/proxies/{tier}",
                    params={"limit": 500},
                    headers={"X-API-Key": api_key},
                    timeout=15,
                )
                resp.raise_for_status()
                veri = resp.json()
                if veri.get("success"):
                    for p in veri.get("proxies", []):
                        proto = p.get("protocol", "http").lower()
                        ip = p.get("ip")
                        port = p.get("port")
                        if proto in ("http", "https") and ip and port:
                            self.proxy_pool.append(f"{proto}://{ip}:{port}")
            except Exception as e:
                self.spider_logger.warning(f"Proxy API hatasi ({tier}): {e}")

        if not self.proxy_pool:
            raise RuntimeError(
                "Proxy havuzu bos! Sunucu IP'sinden istek yapilamaz. "
                "PROXY_API_URL ve PROXY_API_KEY ayarlarini kontrol edin."
            )

        random.shuffle(self.proxy_pool)
        self._son_proxy_yenileme: float = _time.time()
        self.PROXY_YENILEME_PERIYODU: int = 1800  # 30 dakika
        self.spider_logger.info(f"Proxy havuzu dolduruldu: {len(self.proxy_pool)} HTTP proxy")

    def _rate_limit_uygun(self, proxy_url: str) -> bool:
        """Proxy'nin rate limit'e uygun olup olmadigini kontrol eder."""
        simdi = _time.time()
        kullanim = self._proxy_kullanim[proxy_url]
        # Eski kayitlari temizle
        kullanim = [t for t in kullanim if simdi - t < self.PROXY_RATE_WINDOW]
        self._proxy_kullanim[proxy_url] = kullanim
        return len(kullanim) < self.PROXY_RATE_LIMIT

    def _proxy_kullanim_kaydet(self, proxy_url: str) -> None:
        """Proxy kullanim zamanini kaydeder."""
        self._proxy_kullanim[proxy_url].append(_time.time())

    def _proxy_basarili_isaretle(self, proxy_url: str) -> None:
        """Basarili olan proxy'yi oncelikli listeye ekler."""
        if proxy_url not in self._basarili_proxyler:
            self._basarili_proxyler.append(proxy_url)
            self.spider_logger.debug(
                f"Proxy basarili listesine eklendi: {proxy_url} "
                f"(toplam {len(self._basarili_proxyler)} basarili)"
            )

    def _proxy_sec(self, hariç_tutulanlar: set[str] | None = None) -> str:
        """
        Havuzdan proxy secer. Oncelik sirasi:
        1. Basarili proxy'ler (rate limit uygunsa)
        2. Genel havuz (rate limit uygunsa)
        3. Havuz yenile + tekrar dene
        4. Son care: rate limit'i goz ardi et
        """
        excluded = hariç_tutulanlar or set()

        # 0. Periyodik yenileme kontrolu
        if _time.time() - self._son_proxy_yenileme > self.PROXY_YENILEME_PERIYODU:
            eski_sayi = len(self.proxy_pool)
            self._proxy_havuzu_doldur()
            self._son_proxy_yenileme = _time.time()
            self.spider_logger.info(
                f"Periyodik proxy yenileme: {eski_sayi} -> {len(self.proxy_pool)} proxy"
            )

        # 1. Basarili proxy'lerden sec (rate limit kontrolu ile)
        basarili_adaylar = [
            p for p in self._basarili_proxyler
            if p not in excluded and self._rate_limit_uygun(p)
        ]
        if basarili_adaylar:
            proxy = random.choice(basarili_adaylar)
            self._proxy_kullanim_kaydet(proxy)
            return proxy

        # 2. Genel havuzdan sec (rate limit kontrolu ile)
        adaylar = [
            p for p in self.proxy_pool
            if p not in excluded and self._rate_limit_uygun(p)
        ]

        # Adaylar azaldiysa havuzu yenile
        if len(adaylar) < max(len(self.proxy_pool) // 4, 5):
            self.spider_logger.info(
                f"Aday proxy az kaldi ({len(adaylar)}/{len(self.proxy_pool)}), "
                f"havuz yenileniyor..."
            )
            self._proxy_havuzu_doldur()
            adaylar = [
                p for p in self.proxy_pool
                if p not in excluded and self._rate_limit_uygun(p)
            ]

        # 3. Hala aday yoksa hariç tutulanlari temizle + havuzu yenile
        if not adaylar:
            self.spider_logger.warning(
                "Tum proxy'ler tukendi/rate limited. Havuz yenileniyor..."
            )
            self._proxy_havuzu_doldur()
            adaylar = [
                p for p in self.proxy_pool if self._rate_limit_uygun(p)
            ]

        # 4. Son care: rate limit'i goz ardi et
        if not adaylar:
            self.spider_logger.warning("Rate limit gevsetiliyor, tum havuz kullaniliyor")
            adaylar = [p for p in self.proxy_pool if p not in excluded]
            if not adaylar:
                adaylar = list(self.proxy_pool)

        proxy = random.choice(adaylar)
        self._proxy_kullanim_kaydet(proxy)
        return proxy

    def _yeni_context_adi(self) -> str:
        """Her request icin benzersiz bir Playwright context adi uretir."""
        self._context_sayaci += 1
        return f"ctx_{self._context_sayaci}"

    def _proxy_ile_request_olustur(
        self, url: str, idx: int, lat: float, lng: float, retry: int = 0,
        basarisiz_proxyler: set[str] | None = None,
        empty_retry_count: int = 0,
    ) -> scrapy.Request:
        """Belirtilen URL icin proxy atanmis bir Playwright request olusturur."""
        if basarisiz_proxyler is None:
            basarisiz_proxyler = set()

        proxy_url = self._proxy_sec(hariç_tutulanlar=basarisiz_proxyler)
        context_adi = self._yeni_context_adi()

        self.spider_logger.info(
            f"Proxy atandi: {proxy_url} (deneme {retry + 1}/{self.MAX_PROXY_RETRY}) "
            f"-> grid {idx + 1}"
        )

        return scrapy.Request(
            url=url,
            callback=self.parse,
            meta={
                "playwright": True,
                "playwright_context": context_adi,
                "playwright_context_kwargs": {
                    "proxy": {"server": proxy_url},
                    "viewport": {"width": 1920, "height": 1080},
                    "locale": "tr-TR",
                    "timezone_id": "Europe/Istanbul",
                    "java_script_enabled": True,
                },
                "playwright_include_page": True,
                "playwright_page_init_callback": stealth_init_callback,
                "playwright_page_goto_kwargs": {
                    "wait_until": "domcontentloaded",
                },
                "grid_index": idx,
                "grid_lat": lat,
                "grid_lng": lng,
                "_proxy_url": proxy_url,
                "_retry_count": retry,
                "_basarisiz_proxyler": basarisiz_proxyler,
                "_empty_retry_count": empty_retry_count,
            },
            dont_filter=True,
            errback=self.hata_yakala,
        )

    def _grid_noktalari_hesapla(self) -> list[tuple[float, float]]:
        """
        Istanbul bounding box'inda esit aralikli grid noktalari olusturur.

        Returns:
            (enlem, boylam) tuple'larindan olusan liste.
            Noktalar rasgele sirada karistirilir (anti-pattern algilama).
        """
        noktalar: list[tuple[float, float]] = []

        lat_araligi = self.ISTANBUL_NE_LAT - self.ISTANBUL_SW_LAT
        lng_araligi = self.ISTANBUL_NE_LNG - self.ISTANBUL_SW_LNG

        lat_adim = lat_araligi / (self.grid_size - 1) if self.grid_size > 1 else 0
        lng_adim = lng_araligi / (self.grid_size - 1) if self.grid_size > 1 else 0

        for i in range(self.grid_size):
            for j in range(self.grid_size):
                lat = self.ISTANBUL_SW_LAT + (i * lat_adim)
                lng = self.ISTANBUL_SW_LNG + (j * lng_adim)
                # Koordinatlari 6 ondalik basamaga yuvarla
                lat = round(lat, 6)
                lng = round(lng, 6)
                noktalar.append((lat, lng))

        # Noktlalari karistir (ardisik tarama patterni olusturmamak icin)
        random.shuffle(noktalar)

        self.spider_logger.info(
            f"Grid hesaplandi: {len(noktalar)} nokta "
            f"(lat: {self.ISTANBUL_SW_LAT}-{self.ISTANBUL_NE_LAT}, "
            f"lng: {self.ISTANBUL_SW_LNG}-{self.ISTANBUL_NE_LNG})"
        )

        return noktalar

    def _alt_grid_noktalari_hesapla(
        self, merkez_lat: float, merkez_lng: float, ust_zoom: int
    ) -> list[tuple[float, float, int]]:
        """
        Bir grid noktasini 2x2 alt-grid'e boler.

        Ust grid'in kapsama alanini tamamen kapsamak icin %15 overlap
        eklenir. Boylece kenar bolgelerdeki restoranlar kacmaz.

        Args:
            merkez_lat: Ust grid'in merkez enlemi
            merkez_lng: Ust grid'in merkez boylami
            ust_zoom: Ust grid'in zoom seviyesi

        Returns:
            [(lat, lng, zoom), ...] — 4 alt-grid noktasi
        """
        yeni_zoom = ust_zoom + 1

        # Google Maps'te zoom seviyesine gore yaklasik kapsam (derece)
        # zoom=15 ~ 0.027 derece, her zoom seviyesinde yarisina iner
        ust_kapsam_lat = 0.027 * (2 ** (15 - ust_zoom))
        ust_kapsam_lng = 0.035 * (2 ** (15 - ust_zoom))

        # Overlap ile adim hesapla (ust grid'in yarisini kapsayacak sekilde)
        overlap = 1.0 - self.ALT_GRID_OVERLAP
        adim_lat = ust_kapsam_lat / 2 * overlap
        adim_lng = ust_kapsam_lng / 2 * overlap

        alt_gridler = [
            (round(merkez_lat - adim_lat, 6), round(merkez_lng - adim_lng, 6), yeni_zoom),
            (round(merkez_lat - adim_lat, 6), round(merkez_lng + adim_lng, 6), yeni_zoom),
            (round(merkez_lat + adim_lat, 6), round(merkez_lng - adim_lng, 6), yeni_zoom),
            (round(merkez_lat + adim_lat, 6), round(merkez_lng + adim_lng, 6), yeni_zoom),
        ]

        return alt_gridler

    def _alt_grid_request_olustur(
        self, lat: float, lng: float, zoom: int,
        ust_grid_index: int, derinlik: int,
        parent_grid_key: str = "",
    ) -> scrapy.Request:
        """Alt-grid icin proxy atanmis request olusturur."""
        url = self.SEARCH_URL_TEMPLATE.format(lat=lat, lng=lng, zoom=zoom)
        context_adi = self._yeni_context_adi()
        proxy_url = self._proxy_sec()

        self.spider_logger.info(
            f"Alt-grid olusturuldu: derinlik={derinlik}, zoom={zoom}, "
            f"({lat}, {lng}) <- ust_grid={ust_grid_index + 1}"
        )

        return scrapy.Request(
            url=url,
            callback=self.parse,
            meta={
                "playwright": True,
                "playwright_context": context_adi,
                "playwright_context_kwargs": {
                    "proxy": {"server": proxy_url},
                    "viewport": {"width": 1920, "height": 1080},
                    "locale": "tr-TR",
                    "timezone_id": "Europe/Istanbul",
                    "java_script_enabled": True,
                },
                "playwright_include_page": True,
                "playwright_page_init_callback": stealth_init_callback,
                "playwright_page_goto_kwargs": {
                    "wait_until": "domcontentloaded",
                },
                "grid_index": ust_grid_index,
                "grid_lat": lat,
                "grid_lng": lng,
                "_proxy_url": proxy_url,
                "_retry_count": 0,
                "_basarisiz_proxyler": set(),
                "_empty_retry_count": 0,
                # Alt-grid ozel meta
                "_alt_grid": True,
                "_alt_grid_derinlik": derinlik,
                "_alt_grid_zoom": zoom,
                "_parent_grid_key": parent_grid_key,
            },
            dont_filter=True,
            errback=self.hata_yakala,
        )

    def _dogrulama_gecisi_baslat(self):
        """
        Tum ana tarama + alt-gridler tamamlandiktan sonra
        225 grid noktasini bastan tarayarak kacak kontrol eder.
        """
        self.spider_logger.info(
            "=" * 60 + "\n"
            "DOGRULAMA GECISI BASLATIILIYOR\n"
            f"Mevcut benzersiz restoran: {self.scrape_stats['benzersiz_restoran']}\n"
            f"Tamamlanan alt-gridler: {self.scrape_stats['alt_grid_tamamlandi']}\n"
            "Tum 225 grid noktasi tekrar taranacak...\n"
            + "=" * 60
        )
        self._dogrulama_gecisi_aktif = True

    def start_requests(self) -> Generator[scrapy.Request, None, None]:
        """
        Grid noktalarindan baslangic istekleri uretir.

        Her grid noktasi icin Google Maps arama URL'i olusturulur
        ve proxy atanmis Playwright istegi yapilir.
        Sunucu IP'sinden asla dogrudan istek yapilmaz.
        """
        atlanan = 0
        for idx, (lat, lng) in enumerate(self.grid_noktalari):
            grid_key = self._grid_key(lat, lng)
            if grid_key in self._tamamlanan_gridler:
                atlanan += 1
                self._tamamlanan_ana_gridler += 1
                continue

            url = self.SEARCH_URL_TEMPLATE.format(
                lat=lat, lng=lng, zoom=self.zoom
            )

            self.spider_logger.info(
                f"Grid noktasi {idx + 1}/{len(self.grid_noktalari)}: "
                f"({lat}, {lng}) -> {url}"
            )

            yield self._proxy_ile_request_olustur(url, idx, lat, lng)

        if atlanan:
            self.spider_logger.info(f"Checkpoint: {atlanan} grid atlandi (onceden tamamlanmis)")

    async def parse(self, response: Response) -> Generator[
        RestaurantItem | scrapy.Request, None, None
    ]:
        """
        Google Maps arama sonuc sayfasini isle.

        Adimlar:
            1. Cookie kabul diyalogunu kapat
            2. Sayfanin yuklenmesini bekle
            3. Sonuc panelini scroll ederek tum sonuclari yukle
            4. Her restoran kartindan veri cikar

        Args:
            response: Playwright ile render edilmis Scrapy Response
        """
        page = response.meta.get("playwright_page")
        grid_index = response.meta.get("grid_index", 0)
        grid_lat = response.meta.get("grid_lat", 0)
        grid_lng = response.meta.get("grid_lng", 0)

        if not page:
            self.spider_logger.error(
                f"Playwright sayfasi alinamadi! Grid noktasi: {grid_index}"
            )
            self.scrape_stats["hata"] += 1
            return

        try:
            # --- Adim 1: Cookie kabul diyalogunu kapat ---
            await self._cookie_diyalogu_kapat(page)

            # --- Adim 2: Sayfa yuklenme kontrolu ---
            yuklendi = await self._sayfa_yuklenmesini_bekle(page)
            if not yuklendi:
                self.spider_logger.warning(
                    f"Sayfa yuklenemedi, grid noktasi atlanıyor: {grid_index}"
                )
                self.scrape_stats["hata"] += 1
                self._ardisik_hata_kontrolu()
                return

            # --- Adim 3: CAPTCHA kontrolu ---
            if await self._captcha_kontrol(page):
                self.spider_logger.warning(
                    f"CAPTCHA tespit edildi! Grid noktasi: {grid_index} ({grid_lat}, {grid_lng})"
                )
                self.scrape_stats["captcha_tespit"] += 1
                self.scrape_stats["hata"] += 1
                self._ardisik_hata_kontrolu()
                return

            # --- Adim 4: Sonuc panelini scroll et ---
            await self._sonuc_paneli_scroll(page)

            # --- Adim 5: Restoran kartlarindan veri cikar ---
            items, restoran_sayisi, kart_sayisi = await self._restoran_verilerini_cikar(
                page, response
            )
            for item in items:
                yield item

            # Proxy'yi basarili olarak isaretle (sayfa yuklendi)
            proxy_url = response.meta.get("_proxy_url")
            if proxy_url:
                self._proxy_basarili_isaretle(proxy_url)

            # --- 0 restoran kontrolu: farkli proxy ile tekrar dene ---
            empty_retry = response.meta.get("_empty_retry_count", 0)
            if restoran_sayisi == 0 and kart_sayisi == 0 and empty_retry < self.MAX_EMPTY_RETRY:
                self.spider_logger.warning(
                    f"Grid {grid_index + 1}: 0 restoran bulundu, "
                    f"farkli proxy ile tekrar deneniyor "
                    f"({empty_retry + 1}/{self.MAX_EMPTY_RETRY})"
                )
                yield self._proxy_ile_request_olustur(
                    url=response.url,
                    idx=grid_index, lat=grid_lat, lng=grid_lng,
                    retry=0,
                    basarisiz_proxyler=set(),
                    empty_retry_count=empty_retry + 1,
                )
                return  # Bu deneme tamamlandi, yenisini bekle

            # Basarili tarama - ardisik hata sayacini sifirla
            self.scrape_stats["ardisik_hata"] = 0
            self.scrape_stats["taranan_grid_noktasi"] += 1

            # Alt-grid meta bilgileri
            is_alt_grid = response.meta.get("_alt_grid", False)
            current_zoom = response.meta.get("_alt_grid_zoom", self.zoom) if is_alt_grid else self.zoom
            derinlik = response.meta.get("_alt_grid_derinlik", 0)

            if restoran_sayisi == 0 and kart_sayisi == 0 and empty_retry >= self.MAX_EMPTY_RETRY:
                self.spider_logger.info(
                    f"Grid {grid_index + 1}: {self.MAX_EMPTY_RETRY + 1} denemede de "
                    f"0 restoran. Bos bolge olarak kabul ediliyor. "
                    f"({grid_lat}, {grid_lng})"
                )
            else:
                alt_grid_bilgi = f" [alt-grid d={derinlik} z={current_zoom}]" if is_alt_grid else ""
                self.spider_logger.info(
                    f"Grid noktasi {grid_index + 1} tamamlandi{alt_grid_bilgi}: "
                    f"{restoran_sayisi} restoran bulundu (kart={kart_sayisi}), "
                    f"toplam benzersiz: {self.scrape_stats['benzersiz_restoran']}"
                )

            # --- Adim 6: Alt-grid kontrolu ---
            # Kart sayisi esik degerini asiyorsa ve zoom limiti dolmadiysa
            # ve dogrulama gecisinde degilsek -> 2x2 alt-grid olustur
            # Alt-grid'de yeni restoran bulunamadiysa daha derine inme
            if (
                kart_sayisi >= self.CARD_LIMIT_THRESHOLD
                and current_zoom < self.MAX_ZOOM
                and not self._dogrulama_gecisi_aktif
            ):
                alt_gridler = self._alt_grid_noktalari_hesapla(
                    grid_lat, grid_lng, current_zoom
                )
                self.spider_logger.info(
                    f"ALT-GRID TETIKLENDI: grid {grid_index + 1}, "
                    f"kart={kart_sayisi} >= {self.CARD_LIMIT_THRESHOLD}, "
                    f"zoom {current_zoom} -> {current_zoom + 1}, "
                    f"derinlik {derinlik} -> {derinlik + 1}, "
                    f"4 alt-grid olusturuluyor"
                )

                parent_key = self._grid_key(grid_lat, grid_lng) if not is_alt_grid else response.meta.get("_parent_grid_key", "")
                for alt_lat, alt_lng, alt_zoom in alt_gridler:
                    self._bekleyen_alt_gridler += 1
                    self._parent_bekleyen[parent_key] += 1
                    self.scrape_stats["alt_grid_olusturuldu"] += 1
                    yield self._alt_grid_request_olustur(
                        alt_lat, alt_lng, alt_zoom,
                        ust_grid_index=grid_index,
                        derinlik=derinlik + 1,
                        parent_grid_key=parent_key,
                    )
            # --- Adim 7: Tamamlanma sayaclarini guncelle + checkpoint ---
            parent_key = response.meta.get("_parent_grid_key", "")
            if is_alt_grid:
                self._bekleyen_alt_gridler -= 1
                self.scrape_stats["alt_grid_tamamlandi"] += 1
                if derinlik > self.scrape_stats["alt_grid_max_derinlik"]:
                    self.scrape_stats["alt_grid_max_derinlik"] = derinlik
                # Parent grid'in alt-grid sayacini azalt
                if parent_key and parent_key in self._parent_bekleyen:
                    self._parent_bekleyen[parent_key] -= 1
                    if self._parent_bekleyen[parent_key] <= 0:
                        self._tamamlanan_gridler.add(parent_key)
                        self._checkpoint_kaydet()
                        self.spider_logger.info(f"CHECKPOINT: {parent_key} tamamlandi (alt-gridler dahil)")
                        del self._parent_bekleyen[parent_key]
            elif not self._dogrulama_gecisi_aktif:
                self._tamamlanan_ana_gridler += 1
                ana_key = self._grid_key(grid_lat, grid_lng)
                # Alt-grid tetiklenmediyse hemen checkpoint
                if kart_sayisi < self.CARD_LIMIT_THRESHOLD or current_zoom >= self.MAX_ZOOM:
                    self._tamamlanan_gridler.add(ana_key)
                    self._checkpoint_kaydet()
                    self.spider_logger.info(f"CHECKPOINT: {ana_key} tamamlandi")

            # --- Adim 8: Dogrulama gecisi kontrolu ---
            # Ana tarama + tum alt-gridler tamamlandiysa dogrulama baslat
            if (
                not self._dogrulama_gecisi_aktif
                and not self._ana_tarama_tamamlandi
                and self._tamamlanan_ana_gridler >= len(self.grid_noktalari)
                and self._bekleyen_alt_gridler <= 0
            ):
                self._ana_tarama_tamamlandi = True
                self._dogrulama_gecisi_baslat()

                for v_idx, (v_lat, v_lng) in enumerate(self.grid_noktalari):
                    v_url = self.SEARCH_URL_TEMPLATE.format(
                        lat=v_lat, lng=v_lng, zoom=self.zoom
                    )
                    yield self._proxy_ile_request_olustur(
                        v_url, v_idx, v_lat, v_lng
                    )

            # Arama noktalari arasi rastgele bekleme (5-15 saniye)
            bekleme = random.uniform(5, 15)
            self.spider_logger.debug(f"Sonraki grid noktasi icin {bekleme:.1f}s bekleniyor...")
            await asyncio.sleep(bekleme)

        except Exception as e:
            self.spider_logger.error(
                f"Grid noktasi {grid_index} islenirken hata: {type(e).__name__}: {e}"
            )
            self.scrape_stats["hata"] += 1
            self._ardisik_hata_kontrolu()

        finally:
            # Sayfayi kapat (bellek sizintisi onleme)
            await page.close()

    async def _cookie_diyalogu_kapat(self, page: Any) -> None:
        """
        Google cookie kabul diyalogunu tespit edip kapatir.

        Google Maps ilk acilista GDPR uyumlu cookie onay diyalogu gosterir.
        Bu diyalog kapatilmadan sonuc listesine erisilemez.
        Consent sayfasi proxy ulkesine gore farkli dillerde gorunebilir.
        """
        try:
            # Consent sayfasinda miyiz kontrol et
            current_url = page.url
            is_consent_page = "consent" in current_url.lower()

            if not is_consent_page:
                # Belki sayfa icinde cookie dialog'u vardir
                content = await page.content()
                if "consent" not in content[:5000].lower():
                    self.spider_logger.debug(
                        "Cookie/consent sayfasi tespit edilmedi"
                    )
                    return

            self.spider_logger.info("Consent sayfasi tespit edildi, kabul ediliyor...")

            # Google'in cookie onay diyalogu icin farkli selectorlar dene
            # Sirasi onemli: spesifik olanlar once
            cookie_selectorlar = [
                # Turkce
                'button[aria-label="Tümünü kabul et"]',
                # Ingilizce
                'button[aria-label="Accept all"]',
                # Almanca
                'button[aria-label="Alle akzeptieren"]',
                # Fransizca
                'button[aria-label="Tout accepter"]',
                # Form bazli selectorlar (dil bagimsiz)
                'form[action*="consent"] button',
            ]

            clicked = False
            for selector in cookie_selectorlar:
                try:
                    buton = await page.query_selector(selector)
                    if buton:
                        # Insan benzeri: butona yaklasip tikla
                        kutu = await buton.bounding_box()
                        if kutu:
                            await page.mouse.move(
                                kutu["x"] + kutu["width"] / 2 + random.uniform(-5, 5),
                                kutu["y"] + kutu["height"] / 2 + random.uniform(-3, 3),
                            )
                            await asyncio.sleep(random.uniform(0.3, 0.8))
                        await buton.click()
                        self.spider_logger.info(
                            f"Consent butonu tiklandi (selector: {selector})"
                        )
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                # Son care: "kabul" / "accept" metni iceren butonlari dene
                buttons = await page.query_selector_all("button")
                for btn in buttons:
                    try:
                        txt = (await btn.inner_text()).strip().lower()
                        if any(w in txt for w in [
                            "kabul", "accept", "akzep", "accepter",
                        ]):
                            await btn.click()
                            self.spider_logger.info(
                                f"Consent butonu tiklandi (metin: {repr(txt)})"
                            )
                            clicked = True
                            break
                    except Exception:
                        continue

            if not clicked:
                self.spider_logger.warning("Consent butonu bulunamadi!")
                return

            # Consent sonrasi: sayfanin Maps'e yonlenmesini bekle
            try:
                await page.wait_for_url(
                    "**/maps/**", timeout=15000,
                )
                self.spider_logger.debug(
                    f"Consent sonrasi Maps'e yonlendirildi: {page.url}"
                )
            except Exception:
                self.spider_logger.warning(
                    f"Consent sonrasi Maps yonlendirmesi zaman asimi. URL: {page.url}"
                )

            # Maps sayfasi yuklendikten sonra networkidle bekle
            try:
                await page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                self.spider_logger.debug("Consent sonrasi networkidle zaman asimi (devam ediliyor)")

        except Exception as e:
            self.spider_logger.debug(f"Cookie diyalogu kapatma hatasi (onemli degil): {e}")

    async def _sayfa_yuklenmesini_bekle(self, page: Any) -> bool:
        """
        Sayfa iceriginin yuklenmesini bekler.

        Network idle durumunu ve sonuc panelinin gorunur olmasini
        kontrol eder. Basarisiz olursa False doner.

        Returns:
            True: Sayfa basariyla yuklendi
            False: Sayfa yuklenemedi (timeout veya hata)
        """
        try:
            # Hala consent sayfasindaysak bekle
            if "consent" in page.url.lower():
                self.spider_logger.warning("Hala consent sayfasinda, sayfa yuklenemedi")
                return False

            # networkidle bekle (zaten consent handler'da yapildi ama
            # consent yoksa burada da yapmamiz gerekir)
            try:
                await page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                self.spider_logger.debug("networkidle zaman asimi (devam ediliyor)")

            # Sonuc panelini (feed) bekle - bu Maps'in JS icerigini
            # tamamen render ettiginin en iyi gostergesi
            try:
                await page.wait_for_selector(
                    'div[role="feed"]', timeout=15000,
                )
                self.spider_logger.debug("Sonuc paneli (feed) bulundu")
                return True
            except Exception:
                self.spider_logger.debug("Feed paneli 15s icinde bulunamadi")

            # Ekstra bekleme (JS render tamamlanmasi icin)
            ekstra_bekleme = random.uniform(3.0, 5.0)
            await asyncio.sleep(ekstra_bekleme)

            # Fallback selectorlari kontrol et
            sonuc_selektorlari = [
                'div[role="feed"]',
                'div[role="main"]',
                'div.m6QErb',
                'a[href*="/maps/place/"]',
            ]

            for selector in sonuc_selektorlari:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        self.spider_logger.debug(
                            f"Sonuc paneli bulundu (fallback): {selector}"
                        )
                        return True
                except Exception:
                    continue

            # Son care: body icerigini kontrol et
            body = await page.content()
            if "restoran" in body.lower() or "restaurant" in body.lower():
                self.spider_logger.debug("Sayfa icerigi restoran verisi iceriyor")
                return True

            self.spider_logger.warning(
                f"Sonuc paneli bulunamadi. URL: {page.url}, "
                f"Content length: {len(body)}"
            )
            return False

        except Exception as e:
            self.spider_logger.error(f"Sayfa yukleme hatasi: {e}")
            return False

    async def _captcha_kontrol(self, page: Any) -> bool:
        """
        Sayfada CAPTCHA olup olmadigini kontrol eder.

        Returns:
            True: CAPTCHA tespit edildi
            False: CAPTCHA yok
        """
        try:
            sayfa_icerigi = await page.content()
            sayfa_icerigi_kucuk = sayfa_icerigi.lower()

            captcha_isaretleri = [
                "recaptcha",
                "g-recaptcha",
                "hcaptcha",
                "captcha-form",
                "unusual traffic",
                "olagan disi trafik",
                "automated queries",
                "sorry/index",
                "google.com/sorry",
            ]

            for isaret in captcha_isaretleri:
                if isaret in sayfa_icerigi_kucuk:
                    return True

            # reCAPTCHA iframe kontrolu
            captcha_iframe = await page.query_selector(
                'iframe[src*="recaptcha"], iframe[src*="captcha"]'
            )
            if captcha_iframe:
                return True

            return False

        except Exception:
            return False

    async def _sonuc_paneli_scroll(self, page: Any) -> int:
        """
        Sonuc panelini scroll ederek tum sonuclari yukler.

        Google Maps sonuc paneli sonsuz scroll kullaniyor.
        Scroll yapildikca yeni restoran kartlari yuklenir.

        Returns:
            Yuklenen toplam sonuc sayisi (tahmini)
        """
        try:
            # Sonuc panelini bul
            feed_panel = await page.query_selector('div[role="feed"]')
            if not feed_panel:
                # Alternatif selektor dene
                feed_panel = await page.query_selector('div.m6QErb.DxyBCb')
                if not feed_panel:
                    self.spider_logger.warning(
                        "Scroll icin sonuc paneli bulunamadi"
                    )
                    return 0

            onceki_yukseklik = 0
            degismez_sayac = 0
            scroll_sayisi = 0

            for _ in range(self.max_scroll):
                # Paneli scroll et
                await page.evaluate(
                    """(panel) => {
                        panel.scrollTop = panel.scrollHeight;
                    }""",
                    feed_panel,
                )
                scroll_sayisi += 1

                # Insan benzeri bekleme (her scroll sonrasi)
                bekleme = random.uniform(2.0, 3.5)
                await asyncio.sleep(bekleme)

                # Insan benzeri fare hareketi (her 3 scroll'da bir)
                if scroll_sayisi % 3 == 0:
                    await self._insan_benzeri_fare_hareketi(page)

                # Mevcut panel yuksekligini kontrol et
                mevcut_yukseklik = await page.evaluate(
                    "(panel) => panel.scrollHeight",
                    feed_panel,
                )

                # "Sonuca ulasildi" mesaji kontrolu
                sayfa_icerik = await page.content()
                if "Bu bölgede başka sonuç yok" in sayfa_icerik or \
                   "Listenin sonuna ulaştınız" in sayfa_icerik or \
                   "end of list" in sayfa_icerik.lower() or \
                   "no more results" in sayfa_icerik.lower():
                    self.spider_logger.debug(
                        f"Scroll sonu tespit edildi ({scroll_sayisi} scroll)"
                    )
                    break

                # Yeni icerik yuklendi mi?
                if mevcut_yukseklik == onceki_yukseklik:
                    degismez_sayac += 1
                    if degismez_sayac >= 3:
                        # 3 ardisik scroll'da yeni icerik yok -> dur
                        self.spider_logger.debug(
                            f"Scroll durdu: yeni icerik yuklenmiyor "
                            f"({scroll_sayisi} scroll)"
                        )
                        break
                else:
                    degismez_sayac = 0

                onceki_yukseklik = mevcut_yukseklik

            self.spider_logger.debug(
                f"Scroll tamamlandi: {scroll_sayisi} scroll yapildi"
            )
            return scroll_sayisi

        except Exception as e:
            self.spider_logger.error(f"Scroll hatasi: {e}")
            return 0

    async def _insan_benzeri_fare_hareketi(self, page: Any) -> None:
        """
        Insan benzeri fare hareketi simulasyonu.

        Rastgele koordinatlara dogru fare hareketleri yapar.
        Bot algilama sistemlerini atlatmaya yardimci olur.
        """
        try:
            # Ekran icinde rastgele bir noktaya hareket et
            hedef_x = random.randint(200, 1700)
            hedef_y = random.randint(200, 900)

            # Kademeli hareket (bir hamle)
            await page.mouse.move(hedef_x, hedef_y)
            await asyncio.sleep(random.uniform(0.1, 0.3))

            # Bazen ikinci bir noktaya da git
            if random.random() < 0.3:
                hedef_x2 = random.randint(200, 1700)
                hedef_y2 = random.randint(200, 900)
                await page.mouse.move(hedef_x2, hedef_y2)
                await asyncio.sleep(random.uniform(0.1, 0.2))

        except Exception:
            pass  # Fare hareketi basarisiz olursa sessizce devam et

    async def _restoran_verilerini_cikar(
        self, page: Any, response: Response
    ) -> tuple[list, int, int]:
        """
        Sonuc panelindeki restoran kartlarindan veri cikarir.

        Her kart icin: ad, adres, puan, yorum sayisi, kategori,
        fiyat seviyesi, URL ve koordinat bilgilerini toplar.

        Args:
            page: Playwright sayfa nesnesi
            response: Scrapy Response nesnesi

        Returns:
            (items listesi, yeni restoran sayisi, toplam kart sayisi) tuple'i
            toplam kart sayisi: Sayfadaki ham kart adedi (dedup oncesi)
        """
        items = []
        bulunan_sayisi = 0

        try:
            # Restoran kartlarini sec (Google Maps sonuc listesi)
            kart_selektorlari = [
                'div[role="feed"] > div > div > a[href*="/maps/place/"]',
                'a[href*="/maps/place/"]',
            ]

            kartlar = []
            for selector in kart_selektorlari:
                kartlar = await page.query_selector_all(selector)
                if kartlar:
                    self.spider_logger.debug(
                        f"{len(kartlar)} restoran karti bulundu (selector: {selector})"
                    )
                    break

            if not kartlar:
                self.spider_logger.warning("Restoran karti bulunamadi")
                return ([], 0, 0)

            for kart in kartlar:
                try:
                    restoran_verisi = await self._tek_kart_isle(kart, page)
                    if restoran_verisi is None:
                        continue

                    source_id = restoran_verisi.get("source_id", "")
                    if not source_id:
                        continue

                    # Tekrar kontrolu
                    if source_id in self.gorulmus_restoranlar:
                        self.scrape_stats["tekrar_eden_restoran"] += 1
                        continue

                    self.gorulmus_restoranlar.add(source_id)
                    self.scrape_stats["benzersiz_restoran"] += 1
                    bulunan_sayisi += 1

                    # Ilce tespiti: once adres metninden, sonra koordinattan
                    adres = restoran_verisi.get("address", "")
                    lat = restoran_verisi.get("latitude")
                    lng = restoran_verisi.get("longitude")
                    ilce = _ilce_belirle_metin(adres)
                    if not ilce and lat and lng:
                        try:
                            ilce = _ilce_belirle_koordinat(float(lat), float(lng))
                        except (ValueError, TypeError):
                            ilce = ""

                    # RestaurantItem olustur
                    item = self.build_restaurant_item(
                        name=restoran_verisi.get("name", ""),
                        source_id=source_id,
                        address=adres,
                        district=ilce,
                        neighborhood="",
                        city="istanbul",
                        latitude=lat,
                        longitude=lng,
                        phone=None,
                        website=None,
                        cuisine_types=restoran_verisi.get("cuisine_types", []),
                        price_range=restoran_verisi.get("price_range"),
                        rating=restoran_verisi.get("rating"),
                        total_reviews=restoran_verisi.get("total_reviews", 0),
                        image_url=restoran_verisi.get("image_url"),
                        source_url=restoran_verisi.get("source_url", ""),
                        raw_data=restoran_verisi.get("raw_data", {}),
                    )

                    # Item'i listeye ekle (parse metodunda yield edilecek)
                    items.append(item)

                except Exception as e:
                    self.spider_logger.debug(
                        f"Kart isleme hatasi: {type(e).__name__}: {e}"
                    )
                    continue

        except Exception as e:
            self.spider_logger.error(f"Restoran veri cikartma hatasi: {e}")

        return (items, bulunan_sayisi, len(kartlar))

    async def _tek_kart_isle(self, kart: Any, page: Any) -> dict[str, Any] | None:
        """
        Tek bir restoran kartindan veri cikarir.

        Args:
            kart: Playwright element handle (a[href] elementi)
            page: Playwright sayfa nesnesi

        Returns:
            Restoran verisi sozlugu veya None (cikarilma basarisiz)
        """
        try:
            # --- URL ve Place ID ---
            href = await kart.get_attribute("href") or ""
            if not href or "/maps/place/" not in href:
                return None

            source_url = href
            source_id = self._place_id_cikar(href)
            if not source_id:
                # Fallback: URL'den benzersiz kısım al
                source_id = self._url_den_id_cikar(href)
                if not source_id:
                    return None

            # --- Koordinatlar (URL'den parse et) ---
            latitude, longitude = self._koordinat_cikar(href)

            # --- Kart icindeki bilgileri topla ---
            # Restoran adi
            ad = ""
            ad_element = await kart.query_selector(
                'div.fontHeadlineSmall, div.qBF1Pd, span.fontHeadlineSmall'
            )
            if ad_element:
                ad = (await ad_element.inner_text()).strip()

            if not ad:
                # aria-label'dan dene
                aria_label = await kart.get_attribute("aria-label") or ""
                ad = aria_label.strip()

            if not ad:
                return None

            # Ust element (kartın tum icerigini kapsar)
            kart_metni = await kart.inner_text()
            satirlar = [s.strip() for s in kart_metni.split("\n") if s.strip()]

            # --- Puan ve Yorum Sayisi ---
            puan = None
            yorum_sayisi = 0
            puan_metin = ""

            puan_element = await kart.query_selector(
                'span.MW4etd, span[role="img"][aria-label*="yıldız"], '
                'span.ZkP5Je'
            )
            if puan_element:
                puan_metin = (await puan_element.inner_text()).strip()
            else:
                # Metin icinden regex ile bul
                for satir in satirlar:
                    puan_eslesme = re.search(r'(\d[,\.]\d)\s*', satir)
                    if puan_eslesme:
                        puan_metin = puan_eslesme.group(1)
                        break

            if puan_metin:
                try:
                    puan = float(puan_metin.replace(",", "."))
                except (ValueError, TypeError):
                    puan = None

            # Yorum sayisi
            yorum_element = await kart.query_selector(
                'span.UY7F9, span[aria-label*="yorum"]'
            )
            if yorum_element:
                yorum_metin = (await yorum_element.inner_text()).strip()
                yorum_metin = yorum_metin.strip("()")
                yorum_sayisi = self._sayi_parse(yorum_metin)
            else:
                # Satirlar icinden yorum sayisini bul
                for satir in satirlar:
                    yorum_eslesme = re.search(r'\((\d[\d.,]*)\)', satir)
                    if yorum_eslesme:
                        yorum_sayisi = self._sayi_parse(yorum_eslesme.group(1))
                        break

            # --- Kategori ---
            kategori = ""
            kategoriler: list[str] = []
            kategori_element = await kart.query_selector(
                'div.W4Efsd:nth-child(1) > div > div > span,'
                'span.DkEaL'
            )
            if kategori_element:
                kategori = (await kategori_element.inner_text()).strip()

            if not kategori:
                # Metin satirlarindan kategori tahmini
                kategori_anahtar = [
                    "restoran", "restaurant", "lokanta", "cafe", "kafe",
                    "kebap", "pizza", "burger", "balik", "et", "turk",
                    "mutfak", "gida", "yemek",
                ]
                for satir in satirlar:
                    satir_kucuk = satir.lower()
                    if any(a in satir_kucuk for a in kategori_anahtar):
                        if satir != ad:  # Restoran adiyla ayni degilse
                            kategori = satir
                            break

            if kategori:
                # Kategoriyi ayir (orn: "Turk Restorani · ₺₺")
                kategori_parcalar = re.split(r'[·•|]', kategori)
                for parca in kategori_parcalar:
                    parca = parca.strip()
                    if parca and not re.match(r'^[₺$€]+$', parca):
                        kategoriler.append(parca)

            # --- Fiyat Seviyesi ---
            fiyat_seviyesi = None
            for satir in satirlar:
                fiyat_eslesme = re.search(r'(₺{1,4})', satir)
                if fiyat_eslesme:
                    fiyat_seviyesi = len(fiyat_eslesme.group(1))
                    break

            if fiyat_seviyesi is None:
                # Dolar/Euro isareti de olabilir
                for satir in satirlar:
                    fiyat_eslesme = re.search(r'(\${1,4}|€{1,4})', satir)
                    if fiyat_eslesme:
                        fiyat_seviyesi = len(fiyat_eslesme.group(1))
                        break

            # --- Adres ---
            adres = ""
            adres_element = await kart.query_selector(
                'div.W4Efsd:nth-child(2) > div > div > span:not(.MW4etd):not(.UY7F9),'
                'span.W4Efsd'
            )
            if adres_element:
                adres_metin = (await adres_element.inner_text()).strip()
                # Adres genellikle "· Adres bilgisi" seklinde gelir
                adres_metin = adres_metin.lstrip("·•| ").strip()
                if adres_metin and len(adres_metin) > 5:
                    adres = adres_metin

            if not adres:
                # Satirlardan adres bul (ilce/mahalle isimleri iceren satir)
                istanbul_ilceleri = [
                    "kadikoy", "besiktas", "sisli", "beyoglu", "fatih",
                    "uskudar", "sariyer", "bakirkoy", "atasehir", "kartal",
                    "maltepe", "pendik", "umraniye", "beykoz", "adalar",
                    "tuzla", "sultanbeyli", "sancaktepe", "cekmekoy",
                ]
                for satir in satirlar:
                    satir_kucuk = satir.lower()
                    for ilce in istanbul_ilceleri:
                        if ilce in satir_kucuk and satir != ad:
                            adres = satir
                            break
                    if adres:
                        break

            # --- Gorsel URL ---
            gorsel_url = None
            gorsel_element = await kart.query_selector("img")
            if gorsel_element:
                gorsel_url = await gorsel_element.get_attribute("src")
                if gorsel_url and "data:" in gorsel_url:
                    gorsel_url = None  # Base64 placeholder'larini atla

            # --- Sonuc Sozlugu ---
            return {
                "name": ad,
                "source_id": source_id,
                "source_url": source_url,
                "latitude": latitude,
                "longitude": longitude,
                "rating": puan,
                "total_reviews": yorum_sayisi,
                "cuisine_types": kategoriler,
                "price_range": fiyat_seviyesi,
                "address": adres,
                "image_url": gorsel_url,
                "raw_data": {
                    "kart_metni": kart_metni[:500],
                    "href": href[:300],
                },
            }

        except Exception as e:
            self.spider_logger.debug(f"Kart veri cikartma hatasi: {e}")
            return None

    # ---- Yardimci Metodlar ----

    @staticmethod
    def _place_id_cikar(url: str) -> str:
        """
        Google Maps URL'sinden Place ID'yi cikarir.

        Google Maps URL'leri genelde su formatlardadir:
            /maps/place/.../data=...!1s0x...:0x...
            /maps/place/...?cid=12345

        Args:
            url: Google Maps URL'si

        Returns:
            Place ID dizesi veya bos dize
        """
        # data parametresinden Place ID cikart
        # Ornek: !1s0x14cab7...
        place_id_eslesme = re.search(r'!1s(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)', url)
        if place_id_eslesme:
            return place_id_eslesme.group(1)

        # cid parametresinden
        cid_eslesme = re.search(r'[?&]cid=(\d+)', url)
        if cid_eslesme:
            return f"cid_{cid_eslesme.group(1)}"

        # ftid parametresinden
        ftid_eslesme = re.search(r'ftid=(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)', url)
        if ftid_eslesme:
            return ftid_eslesme.group(1)

        return ""

    @staticmethod
    def _url_den_id_cikar(url: str) -> str:
        """
        URL'den benzersiz bir tanimlayici olusturur (Place ID bulunamadiginda fallback).

        /maps/place/ sonrasindaki ilk path segmentini (restoran adi) kullanir.

        Args:
            url: Google Maps URL'si

        Returns:
            URL tabanli benzersiz ID veya bos dize
        """
        try:
            eslesme = re.search(r'/maps/place/([^/]+)', url)
            if eslesme:
                metin = unquote(eslesme.group(1))
                # Ozel karakterleri temizle
                temiz = re.sub(r'[^a-zA-Z0-9\u00C0-\u024F\u0400-\u04FF\u0600-\u06FF_-]', '_', metin)
                temiz = re.sub(r'_+', '_', temiz).strip('_')
                if len(temiz) > 3:
                    return f"url_{temiz[:80]}"
            return ""
        except Exception:
            return ""

    @staticmethod
    def _koordinat_cikar(url: str) -> tuple[float | None, float | None]:
        """
        Google Maps URL'sinden koordinatlari cikarir.

        URL formatlari:
            @41.0082,28.9784,15z
            !3d41.0082!4d28.9784

        Args:
            url: Google Maps URL'si

        Returns:
            (enlem, boylam) tuple'i veya (None, None)
        """
        # @lat,lng,zoom formatini dene
        eslesme = re.search(r'@(-?\d+\.?\d*),(-?\d+\.?\d*)', url)
        if eslesme:
            try:
                lat = float(eslesme.group(1))
                lng = float(eslesme.group(2))
                # Istanbul sinirlarinda mi kontrol et (genis marj)
                if 39.0 < lat < 43.0 and 26.0 < lng < 31.0:
                    return (lat, lng)
            except (ValueError, TypeError):
                pass

        # !3d...!4d... formatini dene
        lat_eslesme = re.search(r'!3d(-?\d+\.?\d*)', url)
        lng_eslesme = re.search(r'!4d(-?\d+\.?\d*)', url)
        if lat_eslesme and lng_eslesme:
            try:
                lat = float(lat_eslesme.group(1))
                lng = float(lng_eslesme.group(1))
                if 39.0 < lat < 43.0 and 26.0 < lng < 31.0:
                    return (lat, lng)
            except (ValueError, TypeError):
                pass

        return (None, None)

    @staticmethod
    def _sayi_parse(metin: str) -> int:
        """
        Metin icindeki sayiyi parse eder.

        Turkce/Ingilizce formatlarini destekler:
            "1.234" -> 1234
            "1,234" -> 1234
            "1234"  -> 1234
            "1.2B"  -> 1200 (bin kisaltmasi)

        Args:
            metin: Sayi iceren metin

        Returns:
            Parse edilen tam sayi veya 0
        """
        if not metin:
            return 0

        try:
            # Sadece rakamlari, nokta, virgul ve B/K harflerini koru
            temiz = re.sub(r'[^\d.,BbKk]', '', metin)

            # Bin kisaltmasini isle (1.2B -> 1200)
            if temiz.upper().endswith('B') or temiz.upper().endswith('K'):
                sayi_kismi = temiz[:-1].replace(",", ".").replace(".", "", temiz.count(".") - 1)
                return int(float(sayi_kismi) * 1000)

            # Nokta ve virgul ayiricilari
            # Turkce: 1.234 (binlik ayirici nokta)
            # Ingilizce: 1,234 (binlik ayirici virgul)
            if "." in temiz and "," in temiz:
                # Her iki ayirici da var - sonuncusu ondalik
                if temiz.rindex(".") > temiz.rindex(","):
                    temiz = temiz.replace(",", "")
                else:
                    temiz = temiz.replace(".", "").replace(",", ".")
            elif "." in temiz:
                # Sadece nokta var
                # 1.234 -> 1234 (Turkce binlik) veya 4.5 -> 4.5 (ondalik)
                parcalar = temiz.split(".")
                if len(parcalar[-1]) == 3 and len(parcalar) > 1:
                    temiz = temiz.replace(".", "")
                # Aksi halde ondalik olarak birak
            elif "," in temiz:
                # Sadece virgul var - binlik ayirici olabilir
                parcalar = temiz.split(",")
                if len(parcalar[-1]) == 3 and len(parcalar) > 1:
                    temiz = temiz.replace(",", "")
                else:
                    temiz = temiz.replace(",", ".")

            return int(float(temiz))

        except (ValueError, TypeError):
            return 0

    def _ardisik_hata_kontrolu(self) -> None:
        """
        Ardisik hata sayisini kontrol eder.

        3 ardisik hatada 60 saniye bekleme suresi uygular.
        Bu, Google tarafindan geçici engelleme durumunda
        sistemin toparlanmasini saglar.
        """
        self.scrape_stats["ardisik_hata"] += 1

        if self.scrape_stats["ardisik_hata"] >= 3:
            self.spider_logger.warning(
                f"3 ardisik hata tespit edildi! 60 saniye bekleniyor... "
                f"(toplam hata: {self.scrape_stats['hata']})"
            )
            # Not: asyncio.sleep senkron context'te kullanilamaz
            # Scrapy'nin DOWNLOAD_DELAY mekanizmasi uzerinden gecikme uygulanir
            import time
            time.sleep(60)
            self.scrape_stats["ardisik_hata"] = 0
            self.spider_logger.info("Bekleme tamamlandi, devam ediliyor...")

    async def hata_yakala(self, failure: Any) -> Generator[scrapy.Request, None, None]:
        """
        Scrapy Request hata callback'i.

        Timeout veya baglanti hatasinda farkli proxy ile yeniden dener.
        MAX_PROXY_RETRY asildiginda grid noktasini atlar.
        """
        meta = failure.request.meta
        retry = meta.get("_retry_count", 0)
        proxy_url = meta.get("_proxy_url", "bilinmiyor")
        basarisiz = meta.get("_basarisiz_proxyler", set()).copy()
        basarisiz.add(proxy_url)

        self.spider_logger.warning(
            f"Proxy basarisiz: {proxy_url} - {failure.type.__name__} "
            f"(deneme {retry + 1}/{self.MAX_PROXY_RETRY}) URL: {failure.request.url}"
        )
        self.scrape_stats["hata"] += 1

        # Playwright sayfasini temizle
        page = meta.get("playwright_page")
        if page:
            try:
                await page.close()
            except Exception:
                pass

        # Yeniden deneme limiti kontrolu
        if retry + 1 < self.MAX_PROXY_RETRY:
            idx = meta.get("grid_index", 0)
            lat = meta.get("grid_lat", 0)
            lng = meta.get("grid_lng", 0)

            self.spider_logger.info(
                f"Farkli proxy ile tekrar deneniyor (grid {idx + 1})..."
            )

            # Alt-grid request'i ise meta bilgilerini koru
            empty_retry = meta.get("_empty_retry_count", 0)
            new_request = self._proxy_ile_request_olustur(
                url=failure.request.url,
                idx=idx, lat=lat, lng=lng,
                retry=retry + 1,
                basarisiz_proxyler=basarisiz,
                empty_retry_count=empty_retry,
            )
            # Alt-grid meta'sini yeni request'e aktar
            if meta.get("_alt_grid"):
                new_request.meta["_alt_grid"] = True
                new_request.meta["_alt_grid_derinlik"] = meta.get("_alt_grid_derinlik", 1)
                new_request.meta["_alt_grid_zoom"] = meta.get("_alt_grid_zoom", self.zoom)

            yield new_request
        else:
            self.spider_logger.error(
                f"Grid noktasi {meta.get('grid_index', '?') + 1} icin "
                f"{self.MAX_PROXY_RETRY} proxy denendi, hepsi basarisiz. Atlaniyor."
            )
            # Alt-grid sayacini guncelle (atlanilan alt-grid)
            if meta.get("_alt_grid"):
                self._bekleyen_alt_gridler -= 1
                self.spider_logger.warning(
                    f"Alt-grid atlanildi (bekleyen: {self._bekleyen_alt_gridler})"
                )
            elif not self._dogrulama_gecisi_aktif:
                self._tamamlanan_ana_gridler += 1

            self._ardisik_hata_kontrolu()

    # ---- BaseSpider Soyut Metod Implementasyonlari ----

    def parse_restaurant(
        self, response: Response
    ) -> Generator[RestaurantItem | scrapy.Request, None, None]:
        """
        Tekil restoran sayfasi parse etme (bu spider'da kullanilmiyor).

        GoogleMapsListSpider listeleme odaklidir. Tekil restoran
        detaylari ayri bir spider (google_maps_detail) tarafindan islenir.
        Bu metod BaseSpider'in soyut metod gereksinimini karsilamak icin
        bos implement edilmistir.
        """
        yield from []

    def parse_reviews(
        self, response: Response
    ) -> Generator[scrapy.Item | scrapy.Request, None, None]:
        """
        Yorum sayfasi parse etme (bu spider'da kullanilmiyor).

        GoogleMapsListSpider yalnizca restoran listeleme yapar.
        Yorum toplama ayri bir spider tarafindan yapilir.
        Bu metod BaseSpider'in soyut metod gereksinimini karsilamak icin
        bos implement edilmistir.
        """
        yield from []

    def closed(self, reason: str) -> None:
        """
        Spider kapandiginda ozet istatistik raporu olusturur.

        Toplam tarama, benzersiz restoran, tekrar eden restoran,
        hata ve CAPTCHA sayilarini loglar.
        """
        self.spider_logger.info("=" * 60)
        self.spider_logger.info("GOOGLE MAPS LISTELEME SPIDER - OZET ISTATISTIKLER")
        self.spider_logger.info("=" * 60)
        self.spider_logger.info(
            f"  Toplam grid noktasi    : {self.scrape_stats['toplam_grid_noktasi']}"
        )
        self.spider_logger.info(
            f"  Taranan grid noktasi   : {self.scrape_stats['taranan_grid_noktasi']}"
        )
        self.spider_logger.info(
            f"  Bulunan restoran       : {self.scrape_stats['restoran_bulunan']}"
        )
        self.spider_logger.info(
            f"  Benzersiz restoran     : {self.scrape_stats['benzersiz_restoran']}"
        )
        self.spider_logger.info(
            f"  Tekrar eden restoran   : {self.scrape_stats['tekrar_eden_restoran']}"
        )
        self.spider_logger.info(
            f"  Toplam hata            : {self.scrape_stats['hata']}"
        )
        self.spider_logger.info(
            f"  CAPTCHA tespit         : {self.scrape_stats['captcha_tespit']}"
        )
        self.spider_logger.info(
            f"  Kapatma sebebi         : {reason}"
        )
        self.spider_logger.info("=" * 60)

        # Ust sinifin closed metodunu da cagir
        super().closed(reason)
