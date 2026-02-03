"""
iyisiniye Scrapy Pipeline Tanimlari

Scrape edilen verilerin sirasiyla islenme adimlari:
    1. ValidationPipeline  (100) - Zorunlu alan kontrolu ve veri temizligi
    2. DeduplicationPipeline (200) - Tekrar eden kayitlarin elenmesi
    3. DatabasePipeline (300) - PostgreSQL veritabanina kayit

Her pipeline process_item() metodunda item'i isler ve bir sonraki
pipeline'a iletir veya DropItem ile eleyebilir.
"""

import re
import time
import unicodedata
from datetime import datetime, timezone
from typing import Any

from itemadapter import ItemAdapter
from loguru import logger
from scrapy import Spider
from scrapy.exceptions import DropItem

from .items import RestaurantItem, ReviewItem


class ValidationPipeline:
    """
    Veri dogrulama pipeline'i.

    Zorunlu alanlarin varligini kontrol eder, veri temizligi yapar
    ve gecersiz kayitlari DropItem ile eler.
    """

    # RestaurantItem icin zorunlu alanlar
    RESTAURANT_REQUIRED_FIELDS = ["name", "source", "source_id"]

    # ReviewItem icin zorunlu alanlar
    REVIEW_REQUIRED_FIELDS = [
        "restaurant_source",
        "restaurant_source_id",
        "text",
    ]

    def __init__(self) -> None:
        self.logger = logger.bind(pipeline="Validation")
        self.stats: dict[str, int] = {
            "kabul_edilen": 0,
            "reddedilen": 0,
        }

    def open_spider(self, spider: Spider) -> None:
        """Spider basladiginda pipeline'i hazirlar."""
        self.logger.info("Dogrulama pipeline'i baslatildi")

    def close_spider(self, spider: Spider) -> None:
        """Spider kapandiginda istatistikleri loglar."""
        self.logger.info(
            f"Dogrulama istatistikleri: "
            f"{self.stats['kabul_edilen']} kabul, "
            f"{self.stats['reddedilen']} ret"
        )

    def process_item(self, item: Any, spider: Spider) -> Any:
        """
        Item'i dogrular ve temizler.

        Args:
            item: Scrapy Item nesnesi (RestaurantItem veya ReviewItem)
            spider: Aktif spider referansi

        Returns:
            Dogrulanmis ve temizlenmis item

        Raises:
            DropItem: Zorunlu alan eksik veya gecersizse
        """
        adapter = ItemAdapter(item)

        if isinstance(item, RestaurantItem):
            self._validate_restaurant(adapter)
            self._clean_restaurant(adapter)
        elif isinstance(item, ReviewItem):
            self._validate_review(adapter)
            self._clean_review(adapter)

        self.stats["kabul_edilen"] += 1
        return item

    def _validate_restaurant(self, adapter: ItemAdapter) -> None:
        """Restoran item'inin zorunlu alanlarini kontrol eder."""
        for alan in self.RESTAURANT_REQUIRED_FIELDS:
            deger = adapter.get(alan)
            if not deger or (isinstance(deger, str) and not deger.strip()):
                self.stats["reddedilen"] += 1
                raise DropItem(
                    f"Restoran zorunlu alan eksik: '{alan}' - "
                    f"kaynak: {adapter.get('source')}/{adapter.get('source_id')}"
                )

    def _validate_review(self, adapter: ItemAdapter) -> None:
        """Yorum item'inin zorunlu alanlarini kontrol eder."""
        for alan in self.REVIEW_REQUIRED_FIELDS:
            deger = adapter.get(alan)
            if not deger or (isinstance(deger, str) and not deger.strip()):
                self.stats["reddedilen"] += 1
                raise DropItem(
                    f"Yorum zorunlu alan eksik: '{alan}' - "
                    f"kaynak: {adapter.get('restaurant_source')}/"
                    f"{adapter.get('restaurant_source_id')}"
                )

        # Yorum metni minimum uzunluk kontrolu
        metin = adapter.get("text", "")
        if len(metin.strip()) < 3:
            self.stats["reddedilen"] += 1
            raise DropItem(
                f"Yorum metni cok kisa ({len(metin)} karakter): "
                f"{adapter.get('external_review_id')}"
            )

    def _clean_restaurant(self, adapter: ItemAdapter) -> None:
        """Restoran verisini temizler ve normallestirir."""
        # Boslukları temizle
        if adapter.get("name"):
            adapter["name"] = adapter["name"].strip()
        if adapter.get("address"):
            adapter["address"] = adapter["address"].strip()

        # Telefon numarasini normallestirir
        if adapter.get("phone"):
            adapter["phone"] = re.sub(r"[^\d+]", "", adapter["phone"])

        # Scrape zamanini ekle (yoksa)
        if not adapter.get("scraped_at"):
            adapter["scraped_at"] = datetime.now(timezone.utc).isoformat()

    def _clean_review(self, adapter: ItemAdapter) -> None:
        """Yorum verisini temizler ve normallestirir."""
        # Yorum metnini temizle
        if adapter.get("text"):
            adapter["text"] = adapter["text"].strip()

        # Varsayilan dil
        if not adapter.get("language"):
            adapter["language"] = "tr"

        # Puan kontrolu (1-5 arasi)
        puan = adapter.get("rating")
        if puan is not None:
            try:
                puan = int(puan)
                adapter["rating"] = max(1, min(5, puan))
            except (ValueError, TypeError):
                adapter["rating"] = None

        # Scrape zamanini ekle (yoksa)
        if not adapter.get("scraped_at"):
            adapter["scraped_at"] = datetime.now(timezone.utc).isoformat()


class DeduplicationPipeline:
    """
    Tekrar eden kayitlari elen pipeline.

    Ayni source + source_id (restoranlar) veya
    ayni restaurant_source_id + external_review_id (yorumlar)
    kombinasyonuna sahip kayitlar ikinci kez islenmez.
    """

    def __init__(self) -> None:
        self.logger = logger.bind(pipeline="Deduplication")
        # Gorulmus restoran kimlikleri: {(source, source_id)}
        self.seen_restaurants: set[tuple[str, str]] = set()
        # Gorulmus yorum kimlikleri: {(restaurant_source_id, external_review_id)}
        self.seen_reviews: set[tuple[str, str]] = set()
        self.stats: dict[str, int] = {
            "benzersiz": 0,
            "tekrar": 0,
        }

    def open_spider(self, spider: Spider) -> None:
        """Spider basladiginda pipeline'i hazirlar."""
        self.logger.info("Tekrar eleme pipeline'i baslatildi")

    def close_spider(self, spider: Spider) -> None:
        """Spider kapandiginda istatistikleri loglar."""
        self.logger.info(
            f"Tekrar eleme istatistikleri: "
            f"{self.stats['benzersiz']} benzersiz, "
            f"{self.stats['tekrar']} tekrar elendi"
        )

    def process_item(self, item: Any, spider: Spider) -> Any:
        """
        Tekrar eden kayitlari tespit edip eler.

        Args:
            item: Scrapy Item nesnesi
            spider: Aktif spider referansi

        Returns:
            Benzersiz item

        Raises:
            DropItem: Daha once islenmiş kayit tespit edilirse
        """
        adapter = ItemAdapter(item)

        if isinstance(item, RestaurantItem):
            anahtar = (
                adapter.get("source", ""),
                adapter.get("source_id", ""),
            )
            if anahtar in self.seen_restaurants:
                self.stats["tekrar"] += 1
                raise DropItem(
                    f"Tekrar restoran: {anahtar[0]}/{anahtar[1]}"
                )
            self.seen_restaurants.add(anahtar)

        elif isinstance(item, ReviewItem):
            anahtar = (
                adapter.get("restaurant_source_id", ""),
                adapter.get("external_review_id", ""),
            )
            if anahtar in self.seen_reviews:
                self.stats["tekrar"] += 1
                raise DropItem(
                    f"Tekrar yorum: {anahtar[0]}/{anahtar[1]}"
                )
            self.seen_reviews.add(anahtar)

        self.stats["benzersiz"] += 1
        return item


# ============================================================================
# Turkce karakter normalizasyon haritasi (slug olusturma icin)
# ============================================================================
_TURKCE_KARAKTER_HARITASI = str.maketrans({
    "ç": "c", "Ç": "C",
    "ş": "s", "Ş": "S",
    "ğ": "g", "Ğ": "G",
    "ü": "u", "Ü": "U",
    "ö": "o", "Ö": "O",
    "ı": "i", "I": "I",
    "İ": "i",
})


def _slug_olustur(metin: str, ilce: str = "", source_id: str = "") -> str:
    """
    Turkceden URL-dostu slug olusturur.

    Islem adimlari:
        1. Ilce varsa metne ekler (benzersizlik icin)
        2. Turkce karakterleri ASCII karsiliklarina donusturur
        3. Unicode normalizasyonu uygular (aksanlari kaldirir)
        4. Kucuk harfe cevirir
        5. Alfanumerik olmayan karakterleri tire ile degistirir
        6. Ard arda tireleri teke dusurur
        7. Bas ve sondaki tireleri siler

    Args:
        metin: Orijinal restoran adi
        ilce: Ilce adi (opsiyonel, slug benzersizligi icin)
        source_id: Kaynak ID (bos slug durumunda fallback)

    Returns:
        URL-dostu slug dizesi
    """
    # Once sadece restoran adindan slug olustur (ilcesiz)
    isim_slug = metin.translate(_TURKCE_KARAKTER_HARITASI)
    isim_slug = unicodedata.normalize("NFKD", isim_slug).encode("ascii", "ignore").decode("ascii")
    isim_slug = isim_slug.lower()
    isim_slug = re.sub(r"[^a-z0-9]+", "-", isim_slug)
    isim_slug = re.sub(r"-+", "-", isim_slug).strip("-")

    # Eger restoran adi Latin karaktere donusmuyorsa (Arapca, Cince vb.)
    # source_id'yi isim olarak kullan
    if not isim_slug and source_id:
        isim_slug = re.sub(r"[^a-z0-9]+", "-", source_id.lower()).strip("-")

    # Ilce varsa slug'a ekle
    if ilce:
        ilce_slug = ilce.translate(_TURKCE_KARAKTER_HARITASI)
        ilce_slug = ilce_slug.lower()
        ilce_slug = re.sub(r"[^a-z0-9]+", "-", ilce_slug).strip("-")
        if ilce_slug:
            slug = f"{isim_slug}-{ilce_slug}" if isim_slug else ilce_slug
        else:
            slug = isim_slug
    else:
        slug = isim_slug

    return slug


class DatabasePipeline:
    """
    PostgreSQL veritabani kayit pipeline'i.

    Dogrulanmis ve tekrarsiz item'lari PostgreSQL veritabanina
    psycopg2 connection pool uzerinden toplu (batch) olarak kaydeder.

    Ozellikler:
        - Connection pool (min 2, max 10)
        - Batch insert (her 50 item'da bir flush)
        - UPSERT (ON CONFLICT DO UPDATE) ile cakisma yonetimi
        - Restoran slug'i icin Turkce karakter normalizasyonu
        - PostGIS koordinat yazimi
        - scrape_jobs tablosuna is takibi
        - Hata yonetimi: retry, skip, continue stratejileri
    """

    # Toplu ekleme esik degeri
    BATCH_BOYUTU = 50

    # DB baglanti retry sayisi
    MAX_RETRY = 3

    def __init__(self) -> None:
        self.logger = logger.bind(pipeline="Database")
        self.pool = None
        self.scrape_job_id: int | None = None
        self._baslangic_zamani: float = 0.0

        # Batch buffer'lari
        self._restoran_buffer: list[dict[str, Any]] = []
        self._yorum_buffer: list[dict[str, Any]] = []

        # Istatistikler
        self.stats: dict[str, int] = {
            "restoran_kaydedilen": 0,
            "yorum_kaydedilen": 0,
            "hata": 0,
        }

    # ----------------------------------------------------------------
    # Spider yasam dongusu
    # ----------------------------------------------------------------

    def open_spider(self, spider: Spider) -> None:
        """
        Spider basladiginda:
        1. psycopg2 connection pool olusturur
        2. scrape_jobs tablosuna yeni kayit acar (status='running')
        """
        import psycopg2
        from psycopg2 import pool as pg_pool

        self._baslangic_zamani = time.time()

        # Scrapy settings'den DB URL'ini al
        db_url = spider.settings.get(
            "DATABASE_URL",
            "postgresql://iyisiniye_app:IyS2026!SecureDB#@157.173.116.230:5433/iyisiniye",
        )

        # Connection pool olustur
        retry_sayaci = 0
        while retry_sayaci < self.MAX_RETRY:
            try:
                self.pool = pg_pool.ThreadedConnectionPool(
                    minconn=2,
                    maxconn=10,
                    dsn=db_url,
                )
                self.logger.info("Veritabani baglanti havuzu olusturuldu (min=2, max=10)")
                break
            except psycopg2.OperationalError as e:
                retry_sayaci += 1
                self.logger.warning(
                    f"DB baglanti denemesi {retry_sayaci}/{self.MAX_RETRY} basarisiz: {e}"
                )
                if retry_sayaci >= self.MAX_RETRY:
                    self.logger.error(
                        "Veritabani baglantisi kurulamadi. "
                        "Pipeline devre disi - item'lar kaydedilmeyecek."
                    )
                    self.pool = None
                    return
                time.sleep(2 ** retry_sayaci)  # Ustel geri cekilme

        # scrape_jobs tablosuna kayit ac
        self._scrape_job_baslat(spider)

    def close_spider(self, spider: Spider) -> None:
        """
        Spider kapandiginda:
        1. Kalan buffer'lari flush eder
        2. scrape_jobs kaydini gunceller (completed)
        3. Connection pool'u kapatir
        """
        if self.pool is None:
            self.logger.warning("Pool mevcut degil, close_spider atlaniyor")
            return

        # Kalan buffer'lari flush et
        try:
            self._flush_restoran_buffer()
            self._flush_yorum_buffer()
        except Exception as e:
            self.logger.error(f"Son flush sirasinda hata: {e}")

        # scrape_jobs kaydini guncelle
        self._scrape_job_tamamla(spider)

        # Istatistikleri logla
        self.logger.info(
            f"Veritabani istatistikleri: "
            f"{self.stats['restoran_kaydedilen']} restoran, "
            f"{self.stats['yorum_kaydedilen']} yorum kaydedildi, "
            f"{self.stats['hata']} hata"
        )

        # Pool'u kapat
        try:
            self.pool.closeall()
            self.logger.info("Veritabani baglanti havuzu kapatildi")
        except Exception as e:
            self.logger.error(f"Pool kapatma hatasi: {e}")

    # ----------------------------------------------------------------
    # Item isleme
    # ----------------------------------------------------------------

    def process_item(self, item: Any, spider: Spider) -> Any:
        """
        Item'i buffer'a ekler, esik degerine ulasildiysa toplu yazar.

        Args:
            item: Dogrulanmis ve benzersiz Scrapy Item
            spider: Aktif spider referansi

        Returns:
            Islenen item (bir sonraki pipeline icin)
        """
        if self.pool is None:
            # Pool yoksa sadece logla ve devam et
            self.logger.debug("Pool yok, item kaydedilmiyor (DB devre disi)")
            return item

        adapter = ItemAdapter(item)

        try:
            if isinstance(item, RestaurantItem):
                self._restoran_buffer.append(dict(adapter))
                if len(self._restoran_buffer) >= self.BATCH_BOYUTU:
                    self._flush_restoran_buffer()

            elif isinstance(item, ReviewItem):
                self._yorum_buffer.append(dict(adapter))
                if len(self._yorum_buffer) >= self.BATCH_BOYUTU:
                    self._flush_yorum_buffer()

        except Exception as e:
            self.stats["hata"] += 1
            self.logger.error(
                f"Item buffer/flush hatasi: {e} | "
                f"item_tipi={type(item).__name__}"
            )

        return item

    # ----------------------------------------------------------------
    # Restoran batch islemleri
    # ----------------------------------------------------------------

    def _flush_restoran_buffer(self) -> None:
        """
        Restoran buffer'indaki tum item'lari veritabanina toplu yazar.

        Her restoran icin:
            1. restaurants tablosuna UPSERT (slug bazli)
            2. restaurant_platforms tablosuna UPSERT (platform + external_id bazli)
        """
        if not self._restoran_buffer:
            return

        islenecekler = self._restoran_buffer[:]
        self._restoran_buffer.clear()

        conn = None
        try:
            conn = self.pool.getconn()
            conn.autocommit = False
            cur = conn.cursor()

            for veri in islenecekler:
                try:
                    self._restoran_upsert(cur, veri)
                    self.stats["restoran_kaydedilen"] += 1
                except Exception as e:
                    # UNIQUE violation veya diger hata: logla, atla
                    conn.rollback()
                    self.stats["hata"] += 1
                    self.logger.warning(
                        f"Restoran kayit hatasi (atlanıyor): {e} | "
                        f"restoran={veri.get('name')}"
                    )
                    # Yeni bir isleme devam et (rollback sonrasi)
                    continue

            conn.commit()
            self.logger.debug(
                f"{len(islenecekler)} restoran flush edildi "
                f"({self.stats['restoran_kaydedilen']} toplam)"
            )

        except Exception as e:
            if conn:
                conn.rollback()
            self.stats["hata"] += 1
            self.logger.error(f"Restoran toplu kayit hatasi: {e}")
        finally:
            if conn:
                self.pool.putconn(conn)

    def _restoran_upsert(self, cur: Any, veri: dict[str, Any]) -> None:
        """
        Tek bir restoran kaydini restaurants + restaurant_platforms tablolarina yazar.

        Args:
            cur: psycopg2 cursor
            veri: RestaurantItem dict verisi
        """
        import psycopg2.extras

        # Slug olustur (item'da varsa onu kullan, yoksa isimden turet)
        slug = veri.get("slug") or _slug_olustur(
            veri["name"],
            ilce=veri.get("district", ""),
            source_id=veri.get("source_id", ""),
        )

        # cuisine_types list -> PostgreSQL text[] donusumu
        mutfak_turleri = veri.get("cuisine_types")
        if mutfak_turleri and isinstance(mutfak_turleri, list):
            mutfak_turleri = mutfak_turleri
        else:
            mutfak_turleri = None

        # ---- 1) restaurants tablosuna UPSERT ----
        # Koordinat varsa PostGIS ile yaz, yoksa NULL
        enlem = veri.get("latitude")
        boylam = veri.get("longitude")
        konum_ifadesi = None
        if enlem is not None and boylam is not None:
            try:
                enlem = float(enlem)
                boylam = float(boylam)
                konum_ifadesi = f"SRID=4326;POINT({boylam} {enlem})"
            except (ValueError, TypeError):
                konum_ifadesi = None

        # Restoran UPSERT sorgusu
        # ON CONFLICT (slug) durumunda mevcut kaydi guncelle
        restoran_sql = """
            INSERT INTO restaurants (
                name, slug, address, district, neighborhood,
                location, phone, website, cuisine_type,
                price_range, overall_score, total_reviews,
                image_url, is_active, created_at, updated_at
            ) VALUES (
                %(name)s, %(slug)s, %(address)s, %(district)s, %(neighborhood)s,
                %(location)s::geography, %(phone)s, %(website)s, %(cuisine_type)s,
                %(price_range)s, %(overall_score)s, %(total_reviews)s,
                %(image_url)s, TRUE, NOW(), NOW()
            )
            ON CONFLICT (slug) DO UPDATE SET
                name = EXCLUDED.name,
                address = COALESCE(EXCLUDED.address, restaurants.address),
                district = COALESCE(EXCLUDED.district, restaurants.district),
                neighborhood = COALESCE(EXCLUDED.neighborhood, restaurants.neighborhood),
                location = COALESCE(EXCLUDED.location, restaurants.location),
                phone = COALESCE(EXCLUDED.phone, restaurants.phone),
                website = COALESCE(EXCLUDED.website, restaurants.website),
                cuisine_type = COALESCE(EXCLUDED.cuisine_type, restaurants.cuisine_type),
                price_range = COALESCE(EXCLUDED.price_range, restaurants.price_range),
                overall_score = COALESCE(EXCLUDED.overall_score, restaurants.overall_score),
                total_reviews = COALESCE(EXCLUDED.total_reviews, restaurants.total_reviews),
                image_url = COALESCE(EXCLUDED.image_url, restaurants.image_url),
                updated_at = NOW()
            RETURNING id
        """

        restoran_params = {
            "name": veri["name"],
            "slug": slug,
            "address": veri.get("address"),
            "district": veri.get("district"),
            "neighborhood": veri.get("neighborhood"),
            "location": konum_ifadesi,
            "phone": veri.get("phone"),
            "website": veri.get("website"),
            "cuisine_type": mutfak_turleri,
            "price_range": veri.get("price_range"),
            "overall_score": veri.get("rating"),
            "total_reviews": veri.get("total_reviews") or 0,
            "image_url": veri.get("image_url"),
        }

        cur.execute(restoran_sql, restoran_params)
        restoran_id = cur.fetchone()[0]

        # ---- 2) restaurant_platforms tablosuna UPSERT ----
        platform = veri.get("source", "")
        external_id = veri.get("source_id", "")

        # raw_data JSON donusumu
        raw_data = veri.get("raw_data")
        if raw_data and not isinstance(raw_data, str):
            import json
            raw_data = json.dumps(raw_data, ensure_ascii=False)

        platform_sql = """
            INSERT INTO restaurant_platforms (
                restaurant_id, platform, external_id,
                external_url, platform_score, platform_reviews,
                last_scraped, raw_data
            ) VALUES (
                %(restaurant_id)s, %(platform)s, %(external_id)s,
                %(external_url)s, %(platform_score)s, %(platform_reviews)s,
                NOW(), %(raw_data)s::jsonb
            )
            ON CONFLICT (platform, external_id) DO UPDATE SET
                restaurant_id = EXCLUDED.restaurant_id,
                external_url = COALESCE(EXCLUDED.external_url, restaurant_platforms.external_url),
                platform_score = COALESCE(EXCLUDED.platform_score, restaurant_platforms.platform_score),
                platform_reviews = COALESCE(EXCLUDED.platform_reviews, restaurant_platforms.platform_reviews),
                last_scraped = NOW(),
                raw_data = COALESCE(EXCLUDED.raw_data, restaurant_platforms.raw_data)
        """

        platform_params = {
            "restaurant_id": restoran_id,
            "platform": platform,
            "external_id": external_id,
            "external_url": veri.get("source_url"),
            "platform_score": veri.get("rating"),
            "platform_reviews": veri.get("total_reviews") or 0,
            "raw_data": raw_data,
        }

        cur.execute(platform_sql, platform_params)
        cur.connection.commit()

        self.logger.debug(
            f"Restoran UPSERT: id={restoran_id}, slug={slug}, "
            f"platform={platform}/{external_id}"
        )

    # ----------------------------------------------------------------
    # Yorum batch islemleri
    # ----------------------------------------------------------------

    def _flush_yorum_buffer(self) -> None:
        """
        Yorum buffer'indaki tum item'lari veritabanina toplu yazar.

        Her yorum icin:
            1. restaurant_platforms uzerinden restaurant_platform_id bulunur
            2. reviews tablosuna UPSERT yapilir
        """
        if not self._yorum_buffer:
            return

        islenecekler = self._yorum_buffer[:]
        self._yorum_buffer.clear()

        conn = None
        try:
            conn = self.pool.getconn()
            conn.autocommit = False
            cur = conn.cursor()

            for veri in islenecekler:
                try:
                    self._yorum_upsert(cur, veri)
                    self.stats["yorum_kaydedilen"] += 1
                except Exception as e:
                    conn.rollback()
                    self.stats["hata"] += 1
                    self.logger.warning(
                        f"Yorum kayit hatasi (atlaniyor): {e} | "
                        f"review_id={veri.get('external_review_id')}"
                    )
                    continue

            conn.commit()
            self.logger.debug(
                f"{len(islenecekler)} yorum flush edildi "
                f"({self.stats['yorum_kaydedilen']} toplam)"
            )

        except Exception as e:
            if conn:
                conn.rollback()
            self.stats["hata"] += 1
            self.logger.error(f"Yorum toplu kayit hatasi: {e}")
        finally:
            if conn:
                self.pool.putconn(conn)

    def _yorum_upsert(self, cur: Any, veri: dict[str, Any]) -> None:
        """
        Tek bir yorum kaydini reviews tablosuna yazar.

        Yorum -> restaurant_platforms -> restaurants zinciri uzerinden
        restaurant_platform_id belirlenir.

        Args:
            cur: psycopg2 cursor
            veri: ReviewItem dict verisi
        """
        platform = veri.get("restaurant_source", "")
        external_id = veri.get("restaurant_source_id", "")

        # ---- 1) restaurant_platform_id bul ----
        cur.execute(
            """
            SELECT id FROM restaurant_platforms
            WHERE platform = %s AND external_id = %s
            LIMIT 1
            """,
            (platform, external_id),
        )
        sonuc = cur.fetchone()

        if sonuc is None:
            raise ValueError(
                f"restaurant_platforms kaydı bulunamadi: "
                f"platform={platform}, external_id={external_id}. "
                f"Restoran henuz kaydedilmemis olabilir."
            )

        restaurant_platform_id = sonuc[0]

        # ---- 2) Tarih donusumu (ISO 8601 -> timestamp) ----
        yorum_tarihi = veri.get("review_date")
        if yorum_tarihi and isinstance(yorum_tarihi, str):
            try:
                # ISO 8601 formati dene
                yorum_tarihi = datetime.fromisoformat(
                    yorum_tarihi.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                # Baska formatlar dene
                for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
                    try:
                        yorum_tarihi = datetime.strptime(yorum_tarihi, fmt).replace(
                            tzinfo=timezone.utc
                        )
                        break
                    except ValueError:
                        continue
                else:
                    # Hicbir format uyusmadi
                    self.logger.warning(
                        f"Tarih parse edilemedi, NULL olarak kaydedilecek: "
                        f"{veri.get('review_date')}"
                    )
                    yorum_tarihi = None

        # scraped_at donusumu
        scraped_at = veri.get("scraped_at")
        if scraped_at and isinstance(scraped_at, str):
            try:
                scraped_at = datetime.fromisoformat(
                    scraped_at.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                scraped_at = datetime.now(timezone.utc)
        elif not scraped_at:
            scraped_at = datetime.now(timezone.utc)

        # ---- 3) reviews tablosuna UPSERT ----
        yorum_sql = """
            INSERT INTO reviews (
                restaurant_platform_id, external_review_id,
                author_name, rating, text,
                review_date, language, scraped_at, processed
            ) VALUES (
                %(restaurant_platform_id)s, %(external_review_id)s,
                %(author_name)s, %(rating)s, %(text)s,
                %(review_date)s, %(language)s, %(scraped_at)s, FALSE
            )
            ON CONFLICT (restaurant_platform_id, external_review_id) DO UPDATE SET
                author_name = COALESCE(EXCLUDED.author_name, reviews.author_name),
                rating = COALESCE(EXCLUDED.rating, reviews.rating),
                text = EXCLUDED.text,
                review_date = COALESCE(EXCLUDED.review_date, reviews.review_date),
                language = COALESCE(EXCLUDED.language, reviews.language),
                scraped_at = EXCLUDED.scraped_at
        """

        yorum_params = {
            "restaurant_platform_id": restaurant_platform_id,
            "external_review_id": veri.get("external_review_id"),
            "author_name": veri.get("author_name"),
            "rating": veri.get("rating"),
            "text": veri["text"],
            "review_date": yorum_tarihi,
            "language": veri.get("language", "tr"),
            "scraped_at": scraped_at,
        }

        cur.execute(yorum_sql, yorum_params)
        cur.connection.commit()

        self.logger.debug(
            f"Yorum UPSERT: platform_id={restaurant_platform_id}, "
            f"review_id={veri.get('external_review_id')}"
        )

    # ----------------------------------------------------------------
    # Scrape job takibi
    # ----------------------------------------------------------------

    def _scrape_job_baslat(self, spider: Spider) -> None:
        """
        scrape_jobs tablosuna yeni bir is kaydi acar.

        Spider adi ve meta bilgilerinden platform ve hedef tipi cikarilir.
        """
        if self.pool is None:
            return

        conn = None
        try:
            conn = self.pool.getconn()
            cur = conn.cursor()

            # Spider'dan platform bilgisi cikar
            platform = getattr(spider, "platform", spider.name)
            target_type = getattr(spider, "target_type", "full_scrape")
            target_id = getattr(spider, "target_id", None)

            import json
            metadata = json.dumps({
                "spider_name": spider.name,
                "bot_name": spider.settings.get("BOT_NAME", ""),
                "baslangic": datetime.now(timezone.utc).isoformat(),
            }, ensure_ascii=False)

            cur.execute(
                """
                INSERT INTO scrape_jobs (
                    platform, target_type, target_id,
                    status, started_at, items_scraped, metadata
                ) VALUES (
                    %s, %s, %s, 'running', NOW(), 0, %s::jsonb
                )
                RETURNING id
                """,
                (platform, target_type, target_id, metadata),
            )
            self.scrape_job_id = cur.fetchone()[0]
            conn.commit()

            self.logger.info(
                f"Scrape job baslatildi: id={self.scrape_job_id}, "
                f"platform={platform}, hedef={target_type}"
            )

        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Scrape job kayit hatasi: {e}")
            self.scrape_job_id = None
        finally:
            if conn:
                self.pool.putconn(conn)

    def _scrape_job_tamamla(self, spider: Spider) -> None:
        """
        Mevcut scrape_jobs kaydini tamamlanmis olarak gunceller.

        Toplam sure, kazinmis item sayisi ve hata sayisi yazilir.
        """
        if self.pool is None or self.scrape_job_id is None:
            return

        conn = None
        try:
            conn = self.pool.getconn()
            cur = conn.cursor()

            gecen_sure = time.time() - self._baslangic_zamani
            toplam_item = self.stats["restoran_kaydedilen"] + self.stats["yorum_kaydedilen"]

            # Hata mesaji (varsa)
            hata_mesaji = None
            if self.stats["hata"] > 0:
                hata_mesaji = f"{self.stats['hata']} kayit sirasinda hata olustu"

            import json
            metadata = json.dumps({
                "spider_name": spider.name,
                "sure_saniye": round(gecen_sure, 2),
                "restoran_sayisi": self.stats["restoran_kaydedilen"],
                "yorum_sayisi": self.stats["yorum_kaydedilen"],
                "hata_sayisi": self.stats["hata"],
                "bitis": datetime.now(timezone.utc).isoformat(),
            }, ensure_ascii=False)

            cur.execute(
                """
                UPDATE scrape_jobs SET
                    status = 'completed',
                    completed_at = NOW(),
                    items_scraped = %s,
                    error_message = %s,
                    metadata = %s::jsonb
                WHERE id = %s
                """,
                (toplam_item, hata_mesaji, metadata, self.scrape_job_id),
            )
            conn.commit()

            self.logger.info(
                f"Scrape job tamamlandi: id={self.scrape_job_id}, "
                f"toplam={toplam_item} item, "
                f"sure={gecen_sure:.1f}s, "
                f"hata={self.stats['hata']}"
            )

        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Scrape job guncelleme hatasi: {e}")
        finally:
            if conn:
                self.pool.putconn(conn)
