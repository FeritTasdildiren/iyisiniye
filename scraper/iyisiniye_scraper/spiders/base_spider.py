"""
iyisiniye Temel Spider Sinifi

Tum platform spider'lari bu siniftan turetilir.
Ortak islevsellik: rate limiting, hata yonetimi, loglama,
Playwright entegrasyonu ve item donusumleri burada tanimlanir.
"""

import re
from abc import abstractmethod
from datetime import datetime, timezone
from typing import Any, Generator

import scrapy
from loguru import logger
from scrapy.http import Response

from ..items import RestaurantItem, ReviewItem


class BaseSpider(scrapy.Spider):
    """
    Tum iyisiniye spider'lari icin temel sinif.

    Alt siniflar su metodlari implement etmelidir:
        - start_requests(): Baslangic URL'lerini uretir
        - parse_restaurant(): Restoran sayfasini parse eder
        - parse_reviews(): Yorum sayfasini parse eder

    Ozellikler:
        - Playwright entegrasyonu (JS render gerektiren sayfalar icin)
        - Otomatik slug uretimi
        - Ortak meta veri yonetimi
        - Istatistik toplama
    """

    # Alt siniflar bu degerleri override etmelidir
    name: str = "base"
    platform_name: str = "base"

    # Spider bazli ozel Scrapy ayarlari
    custom_settings: dict[str, Any] = {
        # Alt siniflar kendi ozel ayarlarini burada tanimlayabilir
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Args:
            city: Hedef sehir (varsayilan: 'istanbul')
            max_pages: Maksimum sayfa sayisi (varsayilan: 50)
            use_playwright: Playwright kullanilsin mi (varsayilan: False)
        """
        super().__init__(*args, **kwargs)

        # Parametreleri al
        self.city: str = kwargs.get("city", "istanbul")
        self.max_pages: int = int(kwargs.get("max_pages", 50))
        self.use_playwright: bool = kwargs.get("use_playwright", False)

        # Istatistikler
        self.scrape_stats: dict[str, int] = {
            "sayfa_islenen": 0,
            "restoran_bulunan": 0,
            "yorum_bulunan": 0,
            "hata": 0,
        }

        self.spider_logger = logger.bind(
            spider=self.name, platform=self.platform_name
        )

    @abstractmethod
    def start_requests(self) -> Generator[scrapy.Request, None, None]:
        """
        Baslangic URL'lerini uretir.

        Her platform spider'i kendi baslangic URL mantgini
        implement etmelidir.
        """
        ...

    @abstractmethod
    def parse_restaurant(
        self, response: Response
    ) -> Generator[RestaurantItem | scrapy.Request, None, None]:
        """
        Restoran sayfasini parse eder.

        Args:
            response: Scrapy Response nesnesi

        Yields:
            RestaurantItem veya ek sayfa istekleri
        """
        ...

    @abstractmethod
    def parse_reviews(
        self, response: Response
    ) -> Generator[ReviewItem | scrapy.Request, None, None]:
        """
        Yorum sayfasini parse eder.

        Args:
            response: Scrapy Response nesnesi

        Yields:
            ReviewItem veya ek sayfa istekleri (sayfalama)
        """
        ...

    # ---- Yardimci Metodlar ----

    def make_playwright_request(
        self,
        url: str,
        callback: Any,
        meta: dict[str, Any] | None = None,
        wait_for: str | None = None,
        context_name: str = "default",
    ) -> scrapy.Request:
        """
        Playwright ile render edilen sayfa istegi olusturur.

        Args:
            url: Hedef URL
            callback: Yanit isleme fonksiyonu
            meta: Ek meta verileri
            wait_for: Beklenen CSS selector (sayfa yuklenmesi icin)
            context_name: Playwright context adi ('default' veya 'mobile')

        Returns:
            Playwright meta verileri ile yapilandirilmis Scrapy Request
        """
        playwright_meta: dict[str, Any] = {
            "playwright": True,
            "playwright_context": context_name,
            "playwright_include_page": True,
        }

        if wait_for:
            playwright_meta["playwright_page_methods"] = [
                {
                    "method": "wait_for_selector",
                    "args": [wait_for],
                    "kwargs": {"timeout": 15000},
                },
            ]

        if meta:
            playwright_meta.update(meta)

        return scrapy.Request(
            url=url,
            callback=callback,
            meta=playwright_meta,
            dont_filter=True,
        )

    @staticmethod
    def generate_slug(text: str) -> str:
        """
        Metinden URL-dostu slug olusturur.

        Turkce karakterleri donusturur, ozel karakterleri kaldirir.

        Args:
            text: Slug'a donusturulecek metin

        Returns:
            URL-dostu slug dizesi
        """
        # Turkce karakter donusumleri
        tr_map = {
            "ç": "c", "Ç": "C",
            "ğ": "g", "Ğ": "G",
            "ı": "i", "İ": "I",
            "ö": "o", "Ö": "O",
            "ş": "s", "Ş": "S",
            "ü": "u", "Ü": "U",
        }
        for tr_char, en_char in tr_map.items():
            text = text.replace(tr_char, en_char)

        # Kucuk harfe cevir
        text = text.lower()
        # Harf ve rakam olmayanlari tire ile degistir
        text = re.sub(r"[^a-z0-9]+", "-", text)
        # Bastaki ve sondaki tireleri kaldir
        text = text.strip("-")
        # Art arda gelen tireleri tekle
        text = re.sub(r"-+", "-", text)

        return text

    def build_restaurant_item(
        self,
        name: str,
        source_id: str,
        address: str = "",
        district: str = "",
        neighborhood: str = "",
        city: str = "",
        latitude: float | None = None,
        longitude: float | None = None,
        phone: str | None = None,
        website: str | None = None,
        cuisine_types: list[str] | None = None,
        price_range: int | None = None,
        rating: float | None = None,
        total_reviews: int = 0,
        image_url: str | None = None,
        source_url: str = "",
        raw_data: dict[str, Any] | None = None,
    ) -> RestaurantItem:
        """
        Standart RestaurantItem olusturur.

        Platform spider'lari bu metodu kullanarak tutarli
        restoran item'lari uretir.
        """
        item = RestaurantItem()
        item["name"] = name
        item["slug"] = self.generate_slug(name)
        item["address"] = address
        item["district"] = district
        item["neighborhood"] = neighborhood
        item["city"] = city or self.city
        item["latitude"] = latitude
        item["longitude"] = longitude
        item["phone"] = phone
        item["website"] = website
        item["cuisine_types"] = cuisine_types or []
        item["price_range"] = price_range
        item["rating"] = rating
        item["total_reviews"] = total_reviews
        item["image_url"] = image_url
        item["source"] = self.platform_name
        item["source_id"] = source_id
        item["source_url"] = source_url
        item["raw_data"] = raw_data or {}
        item["scraped_at"] = datetime.now(timezone.utc).isoformat()

        self.scrape_stats["restoran_bulunan"] += 1
        return item

    def build_review_item(
        self,
        restaurant_source_id: str,
        text: str,
        external_review_id: str = "",
        author_name: str = "",
        rating: int | None = None,
        review_date: str | None = None,
        language: str = "tr",
        raw_data: dict[str, Any] | None = None,
    ) -> ReviewItem:
        """
        Standart ReviewItem olusturur.

        Platform spider'lari bu metodu kullanarak tutarli
        yorum item'lari uretir.
        """
        item = ReviewItem()
        item["restaurant_source"] = self.platform_name
        item["restaurant_source_id"] = restaurant_source_id
        item["external_review_id"] = external_review_id
        item["author_name"] = author_name
        item["rating"] = rating
        item["text"] = text
        item["review_date"] = review_date
        item["language"] = language
        item["raw_data"] = raw_data or {}
        item["scraped_at"] = datetime.now(timezone.utc).isoformat()

        self.scrape_stats["yorum_bulunan"] += 1
        return item

    def closed(self, reason: str) -> None:
        """Spider kapandiginda ozet istatistikleri loglar."""
        self.spider_logger.info(
            f"Spider kapatildi (sebep: {reason}). "
            f"Istatistikler: {self.scrape_stats}"
        )
