"""
Trendyol Yemek Scraper

Trendyol Yemek platformundan restoran bilgilerini ve yorumlarini toplar.
"""

from typing import Any

from .base import BaseScraper, ScrapedRestaurant, ScrapedReview


class TrendyolYemekScraper(BaseScraper):
    """Trendyol Yemek restoran ve yorum scraper'i"""

    SOURCE = "trendyol_yemek"
    BASE_URL = "https://www.trendyol.com/yemek"

    async def scrape_restaurants(
        self, city: str, **kwargs: Any
    ) -> list[ScrapedRestaurant]:
        """
        Trendyol Yemek'ten restoran listesi toplar.

        Strateji:
        1. Sehir ve bolge bazli arama
        2. Restoran listesini sayfalama ile tara
        3. Her restoran icin detay bilgilerini cek

        Args:
            city: Hedef sehir (ornek: "istanbul")
            district: Ilce filtresi (opsiyonel)
        """
        self.logger.info(f"Trendyol Yemek scraping basliyor: {city}")
        # TODO: Implementasyon
        return []

    async def scrape_reviews(
        self, restaurant_source_id: str, **kwargs: Any
    ) -> list[ScrapedReview]:
        """
        Belirtilen restoranin Trendyol Yemek yorumlarini toplar.

        Args:
            restaurant_source_id: Trendyol restoran ID'si
        """
        self.logger.info(f"Yorumlar toplaniyor: {restaurant_source_id}")
        # TODO: Implementasyon
        return []
