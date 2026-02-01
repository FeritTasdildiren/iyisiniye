"""
iyisiniye Temel Scraper Sinifi

Tum scraper'lar bu siniftan turetilir.
Rate limiting, hata yonetimi ve loglama burada tanimlanir.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential


@dataclass
class ScrapedRestaurant:
    """Scrape edilen restoran verisi"""
    name: str
    address: str
    city: str
    district: str
    source: str
    source_id: str
    latitude: float | None = None
    longitude: float | None = None
    phone: str | None = None
    rating: float | None = None
    total_reviews: int = 0
    cuisine_types: list[str] = field(default_factory=list)
    price_range: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)
    scraped_at: datetime = field(default_factory=datetime.now)


@dataclass
class ScrapedReview:
    """Scrape edilen yorum verisi"""
    restaurant_source_id: str
    source: str
    source_review_id: str
    author_name: str
    rating: float
    comment: str
    visit_date: datetime | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)
    scraped_at: datetime = field(default_factory=datetime.now)


class BaseScraper(ABC):
    """
    Tum scraper'lar icin temel sinif.

    Alt siniflar su metodlari implement etmelidir:
    - scrape_restaurants(): Restoran listesi toplar
    - scrape_reviews(): Bir restoranin yorumlarini toplar
    """

    def __init__(self, rate_limit: float = 2.0, max_retries: int = 3):
        """
        Args:
            rate_limit: Istekler arasi minimum bekleme suresi (saniye)
            max_retries: Basarisiz isteklerde tekrar deneme sayisi
        """
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self.logger = logger.bind(scraper=self.__class__.__name__)
        self.logger.info(f"{self.__class__.__name__} baslatildi")

    @abstractmethod
    async def scrape_restaurants(
        self, city: str, **kwargs: Any
    ) -> list[ScrapedRestaurant]:
        """Belirtilen sehirdeki restoranlari toplar"""
        ...

    @abstractmethod
    async def scrape_reviews(
        self, restaurant_source_id: str, **kwargs: Any
    ) -> list[ScrapedReview]:
        """Belirtilen restoranin yorumlarini toplar"""
        ...

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def _safe_request(self, url: str, **kwargs: Any) -> Any:
        """Guvenli HTTP istegi (retry mekanizmali)"""
        import asyncio
        import httpx

        await asyncio.sleep(self.rate_limit)
        self.logger.debug(f"Istek gonderiliyor: {url}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, **kwargs)
            response.raise_for_status()
            return response

    def _log_stats(self, restaurants: int = 0, reviews: int = 0) -> None:
        """Scraping istatistiklerini loglar"""
        self.logger.info(
            f"Istatistik: {restaurants} restoran, {reviews} yorum toplandi"
        )
