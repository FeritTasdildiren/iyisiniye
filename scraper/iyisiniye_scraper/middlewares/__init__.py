"""
iyisiniye Scrapy Middleware Tanimlari

Scrapy settings.py'de tanimlanan downloader middleware'leri:
    - RotatingUserAgentMiddleware (400): Her istekte farkli User-Agent kullanir
    - SkyStoneProxyDownloaderMiddleware (410): SkyStone Proxy API ile proxy rotasyonu
    - AdaptiveRateLimiter (420): Platform bazli adaptif rate limiting

Proxy middleware'in ana implementasyonu
scraper/middlewares/proxy_middleware.py dosyasindadir.
Bu dosya, Scrapy projesinden erisim icin wrapper saglar.
"""

import random
from typing import Any

from loguru import logger
from scrapy import Spider, signals
from scrapy.crawler import Crawler
from scrapy.http import Request, Response

# Ana proxy middleware'i import et
from middlewares.proxy_middleware import SkyStoneProxyMiddleware

# Rate limiting middleware
from .rate_limiter import AdaptiveRateLimiter


class RotatingUserAgentMiddleware:
    """
    User-Agent rotasyonu middleware'i.

    Her giden HTTP istegine settings.py'deki USER_AGENT_LIST'ten
    rastgele bir User-Agent atar. Bu, bot algilamasini zorlastirir.
    """

    def __init__(self, user_agent_list: list[str]) -> None:
        """
        Args:
            user_agent_list: Kullanilacak User-Agent dizelerinin listesi
        """
        self.user_agent_list = user_agent_list
        self.logger = logger.bind(middleware="UserAgentRotation")

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "RotatingUserAgentMiddleware":
        """Scrapy crawler'dan middleware ornegi olusturur."""
        user_agent_list = crawler.settings.getlist("USER_AGENT_LIST", [])

        if not user_agent_list:
            # Varsayilan User-Agent listesi yoksa tek bir tane kullan
            user_agent_list = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ]

        middleware = cls(user_agent_list)
        crawler.signals.connect(
            middleware.spider_opened, signal=signals.spider_opened
        )
        return middleware

    def spider_opened(self, spider: Spider) -> None:
        """Spider basladiginda bilgi loglar."""
        self.logger.info(
            f"User-Agent rotasyonu aktif: {len(self.user_agent_list)} farkli UA"
        )

    def process_request(self, request: Request, spider: Spider) -> None:
        """Her giden istege rastgele User-Agent atar."""
        ua = random.choice(self.user_agent_list)
        request.headers["User-Agent"] = ua
        self.logger.debug(f"UA atandi: {ua[:60]}... -> {request.url}")


class SkyStoneProxyDownloaderMiddleware:
    """
    SkyStone Proxy API ile calisan downloader middleware wrapper'i.

    Ana proxy mantigi middlewares/proxy_middleware.py dosyasindaki
    SkyStoneProxyMiddleware sinifindadir. Bu sinif, Scrapy settings
    uzerinden o sinifa erisim saglar.
    """

    def __init__(self, proxy_middleware: SkyStoneProxyMiddleware) -> None:
        self._proxy = proxy_middleware
        self.logger = logger.bind(middleware="SkyStoneProxyWrapper")

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "SkyStoneProxyDownloaderMiddleware":
        """Scrapy crawler'dan middleware ornegi olusturur."""
        proxy_mw = SkyStoneProxyMiddleware.from_crawler(crawler)
        return cls(proxy_mw)

    def process_request(self, request: Request, spider: Spider) -> None:
        """Istegi proxy middleware'e iletir."""
        return self._proxy.process_request(request, spider)

    def process_response(
        self, request: Request, response: Response, spider: Spider
    ) -> Response:
        """Yaniti proxy middleware'e iletir."""
        return self._proxy.process_response(request, response, spider)

    def process_exception(
        self, request: Request, exception: Exception, spider: Spider
    ) -> None:
        """Hatayi proxy middleware'e iletir."""
        return self._proxy.process_exception(request, exception, spider)

    def spider_opened(self, spider: Spider) -> None:
        """Spider basladiginda proxy havuzunu doldurur."""
        self._proxy.spider_opened(spider)

    def spider_closed(self, spider: Spider) -> None:
        """Spider kapandiginda istatistikleri loglar."""
        self._proxy.spider_closed(spider)

    def get_proxy_stats(self) -> dict[str, Any]:
        """Proxy istatistiklerini dondurur."""
        return self._proxy.get_stats()
