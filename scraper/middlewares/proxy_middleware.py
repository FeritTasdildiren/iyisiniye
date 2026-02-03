"""
SkyStone Proxy Middleware

SkyStone Proxy API ile entegre calisarak her Scrapy istegine
otomatik proxy atayan, basarisiz proxy'leri devre disi birakan
ve havuzu otomatik yenileyen middleware.

Proxy API Endpointleri:
    - GET /api/v1/proxies/high   -> Yuksek kaliteli proxy listesi
    - GET /api/v1/proxies/medium -> Orta kaliteli proxy listesi
    - GET /api/v1/random/{tier}  -> Rastgele tek proxy
    - GET /api/v1/stats          -> Istatistikler

Rate limit: 60 istek/dakika
"""

from __future__ import annotations

import random
import time
from collections import defaultdict
from typing import Any
from urllib.parse import urljoin

import requests
from loguru import logger
from scrapy import Spider, signals
from scrapy.crawler import Crawler
from scrapy.exceptions import NotConfigured
from scrapy.http import Request, Response


class SkyStoneProxyMiddleware:
    """
    SkyStone Proxy API ile calisan Scrapy downloader middleware.

    Ozellikler:
        - Proxy havuzunu API'den otomatik doldurur (high + medium tier)
        - Her istekte havuzdan rastgele proxy atar
        - Basarisiz proxy'leri otomatik devre disi birakir
        - Havuz minimum esik altina dustugunde otomatik yeniler
        - Ban algilama: 403, 429, CAPTCHA icerigi tespit eder
        - Detayli loglama ve istatistik tutar
    """

    # Ban algilamada kullanilan HTTP durum kodlari
    BAN_HTTP_CODES: set[int] = {403, 407, 429}

    # Ban algilamada kullanilan sayfa icerigi kaliplari
    BAN_CONTENT_PATTERNS: list[str] = [
        "captcha",
        "recaptcha",
        "hcaptcha",
        "challenge",
        "blocked",
        "access denied",
        "rate limit",
        "too many requests",
        "erisim engellendi",
        "robot",
    ]

    # Minimum proxy havuz buyuklugu (bu sayinin altina dustugunde yenileme tetiklenir)
    MIN_POOL_SIZE: int = 5

    # API istekleri arasi minimum bekleme suresi (saniye) - rate limit korumasi
    API_RATE_LIMIT_INTERVAL: float = 1.1

    def __init__(
        self,
        api_url: str,
        api_key: str,
        min_pool_size: int = 5,
        refresh_interval: int = 300,
        ban_threshold: int = 3,
    ) -> None:
        """
        Args:
            api_url: SkyStone Proxy API temel URL'i
            api_key: API anahtari (X-API-Key header'i icin)
            min_pool_size: Minimum proxy havuz buyuklugu
            refresh_interval: Havuz yenileme suresi (saniye)
            ban_threshold: Bir proxy'nin devre disi birakilmadan once
                          tolere edecegi maksimum hata sayisi
        """
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.min_pool_size = min_pool_size
        self.refresh_interval = refresh_interval
        self.ban_threshold = ban_threshold

        # Proxy havuzu: {proxy_url: proxy_bilgileri}
        self.proxy_pool: dict[str, dict[str, Any]] = {}

        # Basarisiz proxy sayaci: {proxy_url: hata_sayisi}
        self.failure_counts: defaultdict[str, int] = defaultdict(int)

        # Devre disi birakilan proxy'ler
        self.blacklisted_proxies: set[str] = set()

        # Son API istegi zamani (rate limit korumasi)
        self._last_api_call: float = 0.0

        # Son havuz yenileme zamani
        self._last_refresh: float = 0.0

        # Istatistikler
        self.stats: dict[str, int] = {
            "toplam_istek": 0,
            "basarili_istek": 0,
            "basarisiz_istek": 0,
            "ban_tespit": 0,
            "proxy_devre_disi": 0,
            "havuz_yenileme": 0,
        }

        self.logger = logger.bind(middleware="SkyStoneProxy")

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "SkyStoneProxyMiddleware":
        """Scrapy crawler'dan middleware ornegi olusturur."""
        api_url = crawler.settings.get("PROXY_API_URL")
        api_key = crawler.settings.get("PROXY_API_KEY")

        if not api_url or not api_key:
            raise NotConfigured(
                "PROXY_API_URL ve PROXY_API_KEY ayarlari zorunludur. "
                "settings.py dosyasinda veya ortam degiskenlerinde tanimlayin."
            )

        middleware = cls(
            api_url=api_url,
            api_key=api_key,
            min_pool_size=crawler.settings.getint("PROXY_MIN_POOL_SIZE", 5),
            refresh_interval=crawler.settings.getint("PROXY_REFRESH_INTERVAL", 300),
            ban_threshold=crawler.settings.getint("PROXY_BAN_THRESHOLD", 3),
        )

        # Crawler sinyallerine baglan
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)

        return middleware

    def spider_opened(self, spider: Spider) -> None:
        """Spider basladiginda proxy havuzunu doldurur."""
        self.logger.info("SkyStone Proxy Middleware baslatiliyor...")
        self._refresh_proxy_pool()

        aktif_proxy = len(self.proxy_pool)
        if aktif_proxy == 0:
            self.logger.warning(
                "Proxy havuzu bos! API erisimi kontrol edin. "
                "Istekler proxy'siz devam edecek."
            )
        else:
            self.logger.info(f"Proxy havuzu hazir: {aktif_proxy} proxy yuklendi")

    def spider_closed(self, spider: Spider) -> None:
        """Spider kapandiginda istatistikleri loglar."""
        self.logger.info("=== SkyStone Proxy Middleware Istatistikleri ===")
        for anahtar, deger in self.stats.items():
            self.logger.info(f"  {anahtar}: {deger}")
        self.logger.info(f"  aktif_proxy: {len(self.proxy_pool)}")
        self.logger.info(f"  kara_liste: {len(self.blacklisted_proxies)}")
        self.logger.info("=" * 50)

    def process_request(self, request: Request, spider: Spider) -> None:
        """
        Her giden istege proxy atar.

        Havuz bosalmissa veya minimum esigin altindaysa otomatik yeniler.
        Proxy bulunamazsa istek proxy'siz devam eder.
        """
        self.stats["toplam_istek"] += 1

        # Havuz kontrolu ve gerekirse yenileme
        if len(self.proxy_pool) < self.min_pool_size:
            self._refresh_proxy_pool()

        # Zamana dayali periyodik yenileme
        simdi = time.time()
        if simdi - self._last_refresh > self.refresh_interval:
            self._refresh_proxy_pool()

        # Havuzdan rastgele proxy sec
        proxy_url = self._get_random_proxy()
        if proxy_url:
            request.meta["proxy"] = proxy_url
            request.meta["_proxy_url"] = proxy_url  # Takip icin sakliyoruz
            self.logger.debug(f"Proxy atandi: {proxy_url} -> {request.url}")
        else:
            self.logger.warning(
                f"Kullanilabilir proxy yok! Istek proxy'siz gonderiliyor: {request.url}"
            )

    def process_response(
        self, request: Request, response: Response, spider: Spider
    ) -> Response:
        """
        Gelen yaniti kontrol eder.

        Ban veya engelleme tespit edilirse proxy devre disi birakilir.
        Basarili yanitlarda proxy'nin hata sayaci sifirlanir.
        """
        proxy_url = request.meta.get("_proxy_url")
        if not proxy_url:
            return response

        # Ban algilama: HTTP durum kodu kontrolu
        if response.status in self.BAN_HTTP_CODES:
            self.logger.warning(
                f"Ban tespit edildi (HTTP {response.status}): "
                f"proxy={proxy_url}, url={request.url}"
            )
            self.stats["ban_tespit"] += 1
            self._handle_proxy_failure(proxy_url)
            return response

        # Ban algilama: Icerik kontrolu (sadece HTML yanitlarda)
        content_type = response.headers.get(b"Content-Type", b"").decode("utf-8", errors="ignore")
        if "text/html" in content_type:
            body_lower = response.text[:5000].lower() if hasattr(response, "text") else ""
            for kalip in self.BAN_CONTENT_PATTERNS:
                if kalip in body_lower:
                    self.logger.warning(
                        f"Ban icerik tespit edildi (kalip: '{kalip}'): "
                        f"proxy={proxy_url}, url={request.url}"
                    )
                    self.stats["ban_tespit"] += 1
                    self._handle_proxy_failure(proxy_url)
                    return response

        # Basarili yanit - proxy hata sayacini sifirla
        if 200 <= response.status < 400:
            self.stats["basarili_istek"] += 1
            if proxy_url in self.failure_counts:
                self.failure_counts[proxy_url] = 0

        return response

    def process_exception(
        self, request: Request, exception: Exception, spider: Spider
    ) -> None:
        """
        Istekte hata olustugunda proxy'yi basarisiz olarak isaretler.

        Baglanti hatasi, timeout vb. durumlarda proxy'nin hata sayaci artirilir.
        """
        proxy_url = request.meta.get("_proxy_url")
        if proxy_url:
            self.logger.warning(
                f"Proxy hatasi: {type(exception).__name__} - "
                f"proxy={proxy_url}, url={request.url}"
            )
            self.stats["basarisiz_istek"] += 1
            self._handle_proxy_failure(proxy_url)

    # ---- Dahili Yardimci Metodlar ----

    def _get_random_proxy(self) -> str | None:
        """Havuzdan rastgele bir proxy URL'i dondurur."""
        aktif_proxyler = [
            url for url in self.proxy_pool
            if url not in self.blacklisted_proxies
        ]
        if not aktif_proxyler:
            return None
        return random.choice(aktif_proxyler)

    def _handle_proxy_failure(self, proxy_url: str) -> None:
        """
        Basarisiz proxy'yi isler.

        Hata sayaci esik degerini asarsa proxy kara listeye alinir.
        """
        self.failure_counts[proxy_url] += 1

        if self.failure_counts[proxy_url] >= self.ban_threshold:
            self.logger.info(
                f"Proxy devre disi birakiliyor ({self.failure_counts[proxy_url]} hata): "
                f"{proxy_url}"
            )
            self.blacklisted_proxies.add(proxy_url)
            self.proxy_pool.pop(proxy_url, None)
            self.stats["proxy_devre_disi"] += 1

            # Havuz minimum esigin altina dustuyse yenile
            if len(self.proxy_pool) < self.min_pool_size:
                self.logger.info(
                    f"Proxy havuzu kritik seviyede ({len(self.proxy_pool)} kaldi). "
                    "Havuz yenileniyor..."
                )
                self._refresh_proxy_pool()

    def _refresh_proxy_pool(self) -> None:
        """
        Proxy havuzunu SkyStone API'den yeniler.

        Oncelik sirasi: high tier -> medium tier
        Kara listedeki proxy'ler havuza eklenmez.
        """
        self.logger.info("Proxy havuzu yenileniyor...")
        self.stats["havuz_yenileme"] += 1
        self._last_refresh = time.time()

        yeni_proxyler: dict[str, dict[str, Any]] = {}

        # Yuksek kaliteli proxy'leri al
        high_proxyler = self._api_get_proxies("high")
        for proxy in high_proxyler:
            proxy_url = self._format_proxy_url(proxy)
            if proxy_url and proxy_url not in self.blacklisted_proxies:
                yeni_proxyler[proxy_url] = proxy

        # Orta kaliteli proxy'leri al
        medium_proxyler = self._api_get_proxies("medium")
        for proxy in medium_proxyler:
            proxy_url = self._format_proxy_url(proxy)
            if proxy_url and proxy_url not in self.blacklisted_proxies:
                yeni_proxyler[proxy_url] = proxy

        if yeni_proxyler:
            # Mevcut basarili proxy'leri koru, yenilerini ekle
            self.proxy_pool.update(yeni_proxyler)
            self.logger.info(
                f"Proxy havuzu guncellendi: {len(self.proxy_pool)} aktif proxy "
                f"(+{len(yeni_proxyler)} yeni, {len(self.blacklisted_proxies)} kara listede)"
            )
        else:
            self.logger.error(
                "API'den proxy alinamadi! "
                "Mevcut havuzdaki proxy'lerle devam ediliyor."
            )

    def _api_get_proxies(self, tier: str, limit: int = 500) -> list[dict[str, Any]]:
        """
        SkyStone API'den belirtilen tier'daki proxy'leri getirir.

        Args:
            tier: Proxy kalite seviyesi ('high' veya 'medium')
            limit: Maksimum proxy sayisi (API limiti: 500)

        Returns:
            Proxy bilgilerini iceren sozluk listesi
        """
        self._rate_limit_wait()

        endpoint = urljoin(self.api_url + "/", f"api/v1/proxies/{tier}")
        params = {"limit": min(limit, 500)}
        headers = {"X-API-Key": self.api_key}

        try:
            response = requests.get(
                endpoint,
                params=params,
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()

            veri = response.json()
            if veri.get("success"):
                proxyler = veri.get("proxies", [])
                self.logger.debug(
                    f"API'den {len(proxyler)} {tier}-tier proxy alindi"
                )
                return proxyler
            else:
                self.logger.warning(
                    f"API basarisiz yanit dondurdu ({tier}): {veri}"
                )
                return []

        except requests.exceptions.Timeout:
            self.logger.error(f"API zaman asimi ({tier}): {endpoint}")
            return []
        except requests.exceptions.ConnectionError:
            self.logger.error(f"API baglanti hatasi ({tier}): {endpoint}")
            return []
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"API HTTP hatasi ({tier}): {e}")
            return []
        except (ValueError, KeyError) as e:
            self.logger.error(f"API yanit ayristirma hatasi ({tier}): {e}")
            return []

    def _format_proxy_url(self, proxy: dict[str, Any]) -> str | None:
        """
        Proxy bilgisini Scrapy'nin kullanabilecegi URL formatina donusturur.

        Args:
            proxy: API'den gelen proxy bilgisi sozlugu
                   {'ip': '1.2.3.4', 'port': 8080, 'protocol': 'http', ...}

        Returns:
            'http://1.2.3.4:8080' formatinda proxy URL'i veya None
        """
        try:
            ip = proxy.get("ip")
            port = proxy.get("port")
            protocol = proxy.get("protocol", "http").lower()

            if not ip or not port:
                return None

            # Playwright SOCKS proxy ile sorun yasayabiliyor,
            # sadece HTTP/HTTPS proxy'leri kabul et
            if protocol not in ("http", "https"):
                return None

            return f"{protocol}://{ip}:{port}"

        except (TypeError, AttributeError):
            return None

    def _rate_limit_wait(self) -> None:
        """API istekleri arasinda rate limit beklemesi uygular."""
        simdi = time.time()
        gecen_sure = simdi - self._last_api_call

        if gecen_sure < self.API_RATE_LIMIT_INTERVAL:
            bekleme = self.API_RATE_LIMIT_INTERVAL - gecen_sure
            self.logger.debug(f"API rate limit beklemesi: {bekleme:.2f}s")
            time.sleep(bekleme)

        self._last_api_call = time.time()

    def get_stats(self) -> dict[str, Any]:
        """Mevcut middleware istatistiklerini dondurur."""
        return {
            **self.stats,
            "aktif_proxy": len(self.proxy_pool),
            "kara_liste": len(self.blacklisted_proxies),
            "havuz_detay": {
                url: {
                    "kalite_skoru": bilgi.get("quality_score", 0),
                    "basari_orani": bilgi.get("success_rate", 0),
                    "hata_sayisi": self.failure_counts.get(url, 0),
                }
                for url, bilgi in self.proxy_pool.items()
            },
        }
