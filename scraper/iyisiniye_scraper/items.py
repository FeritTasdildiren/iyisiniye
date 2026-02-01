"""
iyisiniye Scrapy Item Tanimlari

Scrape edilen verilerin yapilandirilmis formatlari.
BaseScraper'daki ScrapedRestaurant ve ScrapedReview dataclass'larindan
Scrapy Item yapisina donusturulmus halidir.

Scrapy Item'lari pipeline'larda dogrulama, deduplication
ve veritabani kaydi icin kullanilir.
"""

import scrapy


class RestaurantItem(scrapy.Item):
    """
    Scrape edilen restoran verisi.

    Alanlar BaseScraper'daki ScrapedRestaurant dataclass'ina karsilik gelir.
    Pipeline'larda dogrulama ve veritabanina kayit islemlerinden gecer.
    """

    # Temel bilgiler
    name = scrapy.Field()            # Restoran adi
    slug = scrapy.Field()            # URL-dostu isim
    address = scrapy.Field()         # Tam adres
    district = scrapy.Field()        # Ilce
    neighborhood = scrapy.Field()    # Mahalle
    city = scrapy.Field()            # Sehir

    # Konum bilgileri (PostGIS icin)
    latitude = scrapy.Field()        # Enlem
    longitude = scrapy.Field()       # Boylam

    # Iletisim
    phone = scrapy.Field()           # Telefon numarasi
    website = scrapy.Field()         # Web sitesi URL'i

    # Kategori ve fiyat
    cuisine_types = scrapy.Field()   # Mutfak turleri listesi (list[str])
    price_range = scrapy.Field()     # Fiyat araligi (1-4)

    # Puanlama
    rating = scrapy.Field()          # Platform puani
    total_reviews = scrapy.Field()   # Toplam yorum sayisi

    # Gorsel
    image_url = scrapy.Field()       # Ana gorsel URL'i

    # Platform bilgileri
    source = scrapy.Field()          # Platform adi (google_maps, yemeksepeti, vb.)
    source_id = scrapy.Field()       # Platformdaki benzersiz ID
    source_url = scrapy.Field()      # Platformdaki sayfa URL'i

    # Ham veri
    raw_data = scrapy.Field()        # Islenmemis ham JSON verisi

    # Meta bilgiler
    scraped_at = scrapy.Field()      # Scrape edildigi zaman


class ReviewItem(scrapy.Item):
    """
    Scrape edilen yorum verisi.

    Alanlar BaseScraper'daki ScrapedReview dataclass'ina karsilik gelir.
    Pipeline'larda dogrulama, tekrar eleme ve veritabanina kayit
    islemlerinden gecer.
    """

    # Restoran iliskisi
    restaurant_source = scrapy.Field()     # Platform adi
    restaurant_source_id = scrapy.Field()  # Restoranin platformdaki ID'si

    # Yorum bilgileri
    external_review_id = scrapy.Field()    # Yorumun platformdaki benzersiz ID'si
    author_name = scrapy.Field()           # Yorum yazarinin adi
    rating = scrapy.Field()                # Puan (1-5 arasi smallint)
    text = scrapy.Field()                  # Yorum metni (NOT NULL)
    review_date = scrapy.Field()           # Yorum tarihi

    # Dil bilgisi
    language = scrapy.Field()              # Yorum dili (varsayilan: 'tr')

    # Ham veri
    raw_data = scrapy.Field()              # Islenmemis ham JSON verisi

    # Meta bilgiler
    scraped_at = scrapy.Field()            # Scrape edildigi zaman
