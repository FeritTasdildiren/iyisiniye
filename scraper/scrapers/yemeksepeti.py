"""
Yemeksepeti Scraper

Yemeksepeti'nden restoran bilgilerini ve yorumlarini toplar.
"""

from typing import Any

from .base import BaseScraper, ScrapedRestaurant, ScrapedReview


class YemeksepetiScraper(BaseScraper):
    """Yemeksepeti restoran ve yorum scraper'i"""

    SOURCE = "yemeksepeti"
    BASE_URL = "https://www.yemeksepeti.com"

    async def scrape_restaurants(
        self, city: str, **kwargs: Any
    ) -> list[ScrapedRestaurant]:
        """
        Yemeksepeti'nden restoran listesi toplar.

        Strateji:
        1. Sehir sayfasindaki kategorileri tara
        2. Her kategorideki restoranlari listele
        3. Restoran detay sayfalarindan bilgi cek

        Args:
            city: Hedef sehir (ornek: "istanbul")
            category: Kategori filtresi (opsiyonel)
        """
        self.logger.info(f"Yemeksepeti scraping basliyor: {city}")
        # TODO: Implementasyon
        return []

    async def scrape_reviews(
        self, restaurant_source_id: str, **kwargs: Any
    ) -> list[ScrapedReview]:
        """
        Belirtilen restoranin Yemeksepeti yorumlarini toplar.

        Args:
            restaurant_source_id: Yemeksepeti restoran slug'i
        """
        self.logger.info(f"Yorumlar toplaniyor: {restaurant_source_id}")
        # TODO: Implementasyon
        return []
