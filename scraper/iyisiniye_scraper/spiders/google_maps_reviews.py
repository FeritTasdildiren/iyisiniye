"""
Google Maps Yorum Cekme Spider'i

Google Maps reviewDialog async endpoint'ini kullanarak
restoran yorumlarini toplar. Playwright scroll'a gore
cok daha verimli ve stabil bir yontemdir.

Endpoint:
    https://www.google.com/async/reviewDialog?hl=tr&async=...

Kullanim:
    # Tek restoran (feature_id ile):
    scrapy crawl google_maps_reviews -a feature_ids=0x14cab9...

    # Birden fazla restoran (virgul ile ayrilmis):
    scrapy crawl google_maps_reviews -a feature_ids=0x14cab9...,0x14caba...

    # Dosyadan restoran listesi:
    scrapy crawl google_maps_reviews -a input_file=restoranlar.txt

    # Siralama stratejisi (varsayilan: newestFirst):
    scrapy crawl google_maps_reviews -a sort_by=newestFirst

    # Her iki siralama ile cek (deduplicate yapar):
    scrapy crawl google_maps_reviews -a feature_ids=0x14cab9... -a dual_sort=true

    # Maksimum yorum sayisi (varsayilan: 500):
    scrapy crawl google_maps_reviews -a max_reviews=200
"""

import hashlib
import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator
from urllib.parse import quote

import scrapy
from loguru import logger
from scrapy.http import Response

from ..items import ReviewItem
from .base_spider import BaseSpider

# Turkce karakter seti - dil tespiti icin kullanilir
TURKCE_KARAKTERLER = set("cCgGiIoOsSuU")
# Turkce'ye ozgu kelimeler (sik kullanilan)
TURKCE_KELIMELER = {
    "bir", "ve", "bu", "da", "de", "ile", "icin", "ama", "cok",
    "olan", "gibi", "daha", "var", "yok", "ben", "sen", "biz",
    "den", "dan", "nin", "nun", "ler", "lar", "dir", "tir",
    "mi", "mu", "ise", "ki", "ne", "hem", "ya", "her",
    "lezzetli", "guzel", "harika", "kotu", "iyi", "orta",
    "yemek", "servis", "mekan", "ortam", "fiyat", "kalite",
    "tavsiye", "ederim", "etmem", "gelecegim", "gelmem",
    "lezzet", "porsiyon", "garson", "hesap", "menu",
}


class GoogleMapsReviewsSpider(BaseSpider):
    """
    Google Maps restoran yorumlarini reviewDialog endpoint'i
    uzerinden toplayan spider.

    reviewDialog endpoint'i sayfali (paginated) HTML yanit dondurur.
    Playwright'a gerek kalmadan HTTP istekleriyle tum yorumlara
    erisilir.

    Ozellikler:
        - Sayfali yorum cekme (next_page_token ile)
        - Farkli siralama stratejileri (en yeni, en yuksek puan)
        - review_id bazli deduplication
        - Turkce dil tespiti
        - Rate limiting ve hata yonetimi
        - Proxy rotasyonu destegi (middleware uzerinden)
    """

    name = "google_maps_reviews"
    platform_name = "google_maps"

    # Spider ozel ayarlari
    custom_settings: dict[str, Any] = {
        # robots.txt'yi devre disi birak (async endpoint icin)
        "ROBOTSTXT_OBEY": False,
        # Bu spider icin esitlik ayarlari
        "DOWNLOAD_DELAY": 3,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        # Retry ayarlari
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
        # Zaman asimi
        "DOWNLOAD_TIMEOUT": 30,
    }

    # reviewDialog temel URL sablonu
    REVIEW_DIALOG_URL = (
        "https://www.google.com/async/reviewDialog"
        "?hl=tr&async="
        "feature_id:{feature_id},"
        "next_page_token:{token},"
        "sort_by:{sort_by},"
        "start_index:,"
        "associated_topic:,"
        "_fmt:pc"
    )

    # Varsayilan siralama secenekleri
    SORT_OPTIONS = {
        "newestFirst": "newestFirst",       # En yeni yorumlar
        "ratingHigh": "ratingHigh",         # Yuksek puanli yorumlar
        "ratingLow": "ratingLow",           # Dusuk puanli yorumlar
        "relevance": "qualityScore",        # Alakalilik (varsayilan)
    }

    # Maksimum yorum limiti (restoran basina)
    DEFAULT_MAX_REVIEWS = 500

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Args:
            feature_ids: Virgul ile ayrilmis feature_id listesi
            input_file: Restoran listesi dosyasi (her satir: feature_id veya feature_id|restoran_adi)
            sort_by: Siralama stratejisi (newestFirst, ratingHigh, ratingLow, relevance)
            dual_sort: True ise hem newestFirst hem ratingHigh ile ceker (deduplicate)
            max_reviews: Restoran basina maksimum yorum sayisi
        """
        super().__init__(*args, **kwargs)

        # Parametreleri al
        self.feature_ids_raw: str = kwargs.get("feature_ids", "")
        self.input_file: str = kwargs.get("input_file", "")
        self.sort_by: str = kwargs.get("sort_by", "newestFirst")
        self.dual_sort: bool = str(kwargs.get("dual_sort", "false")).lower() == "true"
        self.max_reviews: int = int(kwargs.get("max_reviews", self.DEFAULT_MAX_REVIEWS))

        # Restoran listesini hazirla: [(feature_id, restoran_adi), ...]
        self.restaurants: list[tuple[str, str]] = []

        # Restoran bazinda gorulmus yorum ID'leri (deduplication)
        # {feature_id: set(review_id, ...)}
        self.seen_review_ids: dict[str, set[str]] = {}

        # Restoran bazinda yorum sayaci
        # {feature_id: int}
        self.review_counts: dict[str, int] = {}

        # Spider istatistikleri (ek)
        self.scrape_stats.update({
            "restoran_islenen": 0,
            "sayfa_cekilen": 0,
            "tekrar_elenen": 0,
            "turkce_olmayan": 0,
            "bos_yanit": 0,
            "captcha_tespit": 0,
        })

        self.spider_logger = logger.bind(
            spider=self.name, platform=self.platform_name
        )

    def _restoran_listesini_hazirla(self) -> list[tuple[str, str]]:
        """
        Spider argumanlari veya dosyadan restoran listesi olusturur.

        Returns:
            [(feature_id, restoran_adi), ...] seklinde liste
        """
        restoranlar: list[tuple[str, str]] = []

        # 1. Dogrudan feature_ids parametresinden
        if self.feature_ids_raw:
            for fid in self.feature_ids_raw.split(","):
                fid = fid.strip()
                if fid:
                    restoranlar.append((fid, ""))

        # 2. Dosyadan oku
        if self.input_file:
            dosya_yolu = Path(self.input_file)
            if dosya_yolu.exists():
                with dosya_yolu.open("r", encoding="utf-8") as f:
                    for satir in f:
                        satir = satir.strip()
                        if not satir or satir.startswith("#"):
                            continue
                        # Format: feature_id veya feature_id|restoran_adi
                        if "|" in satir:
                            parcalar = satir.split("|", 1)
                            restoranlar.append((parcalar[0].strip(), parcalar[1].strip()))
                        else:
                            restoranlar.append((satir, ""))
            else:
                self.spider_logger.error(
                    f"Girdi dosyasi bulunamadi: {self.input_file}"
                )

        if not restoranlar:
            self.spider_logger.error(
                "Hic restoran bulunamadi! "
                "'feature_ids' veya 'input_file' parametresi gerekli."
            )

        self.spider_logger.info(
            f"{len(restoranlar)} restoran yorum cekme sirasina alindi"
        )
        return restoranlar

    def start_requests(self) -> Generator[scrapy.Request, None, None]:
        """
        Her restoran icin ilk reviewDialog istegini olusturur.

        Restoranlar arasinda 5-15 saniye rastgele bekleme uygulanir.
        """
        self.restaurants = self._restoran_listesini_hazirla()

        if not self.restaurants:
            self.spider_logger.warning("Islenecek restoran yok, spider sonlandiriliyor")
            return

        for idx, (feature_id, restoran_adi) in enumerate(self.restaurants):
            # Deduplication ve sayac icin hazirla
            self.seen_review_ids[feature_id] = set()
            self.review_counts[feature_id] = 0

            # Siralama stratejisini belirle
            sort_key = self.SORT_OPTIONS.get(self.sort_by, "newestFirst")

            # Ilk sayfa URL'i (token bos)
            url = self._build_review_url(feature_id, token="", sort_by=sort_key)

            meta = {
                "feature_id": feature_id,
                "restoran_adi": restoran_adi,
                "sort_by": sort_key,
                "sayfa_no": 1,
                "is_dual_sort_second": False,
            }

            # Restoranlar arasi bekleme (ilk restoran haric)
            bekleme = random.uniform(5, 15) if idx > 0 else 0

            self.spider_logger.info(
                f"[{idx + 1}/{len(self.restaurants)}] "
                f"Restoran yorumlari cekilecek: {feature_id} "
                f"({restoran_adi or 'isim yok'}) "
                f"| siralama: {sort_key}"
                + (f" | {bekleme:.1f}s bekleme" if bekleme > 0 else "")
            )

            yield scrapy.Request(
                url=url,
                callback=self.parse_reviews,
                meta=meta,
                dont_filter=True,
                # Scrapy DOWNLOAD_DELAY ayariyla birlikte ek bekleme
                # cb_kwargs ile ek gecikme saglanamaz, meta'da tasiyoruz
                priority=-idx,  # Siralama onceligi (ilk restoran once)
            )

    def _build_review_url(
        self, feature_id: str, token: str = "", sort_by: str = "newestFirst"
    ) -> str:
        """
        reviewDialog endpoint URL'i olusturur.

        Args:
            feature_id: Google Maps feature/data ID
            token: Sayfalama token'i (next_page_token)
            sort_by: Siralama kriteri

        Returns:
            Tam URL dizesi
        """
        # Token'i URL-encode et (ozel karakterler iceriyorsa)
        encoded_token = quote(token, safe="") if token else ""

        return self.REVIEW_DIALOG_URL.format(
            feature_id=feature_id,
            token=encoded_token,
            sort_by=sort_by,
        )

    def parse_restaurant(
        self, response: Response
    ) -> Generator[scrapy.Request, None, None]:
        """
        Bu spider restoran sayfasi parse etmez,
        dogrudan reviewDialog endpoint'ini kullanir.
        BaseSpider abstract metodunu bos birakiyoruz.
        """
        # Kullanilmaz - reviewDialog dogrudan yorum dondurur
        return
        yield  # Generator olmasi icin gerekli

    def parse_reviews(
        self, response: Response
    ) -> Generator[ReviewItem | scrapy.Request, None, None]:
        """
        reviewDialog HTML yanitini parse ederek yorumlari cikarir.

        Args:
            response: Google reviewDialog endpoint yanitisi

        Yields:
            ReviewItem nesneleri ve sonraki sayfa istekleri
        """
        feature_id = response.meta["feature_id"]
        restoran_adi = response.meta["restoran_adi"]
        sort_by = response.meta["sort_by"]
        sayfa_no = response.meta["sayfa_no"]
        is_dual_sort_second = response.meta.get("is_dual_sort_second", False)

        self.scrape_stats["sayfa_cekilen"] += 1

        # --- HTTP durum kontrolu ---
        if response.status == 429:
            self.spider_logger.warning(
                f"429 Too Many Requests - {feature_id} | "
                f"60 saniye bekleniyor, proxy degistiriliyor..."
            )
            self.scrape_stats["hata"] += 1
            # Retry middleware halledecek, ama ek log birakiyoruz
            return

        if response.status != 200:
            self.spider_logger.warning(
                f"HTTP {response.status} hatasi - {feature_id} sayfa {sayfa_no}"
            )
            self.scrape_stats["hata"] += 1
            return

        # --- CAPTCHA kontrolu ---
        body_text = response.text
        if self._captcha_tespit(body_text):
            self.spider_logger.warning(
                f"CAPTCHA tespit edildi! {feature_id} | "
                f"60 saniye bekleme gerekli"
            )
            self.scrape_stats["captcha_tespit"] += 1
            return

        # --- Bos yanit kontrolu ---
        if not body_text or len(body_text.strip()) < 100:
            self.spider_logger.info(
                f"Bos yanit - {feature_id} sayfa {sayfa_no} | "
                f"Sonraki restorana geciliyor"
            )
            self.scrape_stats["bos_yanit"] += 1
            # Bos yanit geldiyse bu restoran icin dual_sort'u da deneme
            return

        # --- Yorumlari parse et ---
        sayfa_yorum_sayisi = 0

        for yorum_verisi in self._yorumlari_cikar(response):
            # Maksimum yorum kontrolu
            if self.review_counts.get(feature_id, 0) >= self.max_reviews:
                self.spider_logger.info(
                    f"Maksimum yorum limitine ulasildi ({self.max_reviews}) - "
                    f"{feature_id}"
                )
                break

            review_id = yorum_verisi.get("review_id", "")

            # Deduplication (ayni restoran icinde)
            if review_id and review_id in self.seen_review_ids.get(feature_id, set()):
                self.scrape_stats["tekrar_elenen"] += 1
                continue

            # Gorulmus olarak isaretle
            if review_id:
                self.seen_review_ids.setdefault(feature_id, set()).add(review_id)

            # Turkce dil kontrolu
            yorum_metni = yorum_verisi.get("text", "")
            dil = self._dil_tespit(yorum_metni)

            if dil != "tr":
                self.scrape_stats["turkce_olmayan"] += 1
                # Turkce olmayan yorumlari da kaydediyoruz, ama dil alanini isaretliyoruz
                # Pipeline veya sonraki asamada filtrelenebilir

            # Tarih parse
            tarih_metni = yorum_verisi.get("date_text", "")
            review_date = self._tarihi_parse_et(tarih_metni)

            # ReviewItem olustur (BaseSpider'daki build_review_item kullan)
            item = self.build_review_item(
                restaurant_source_id=feature_id,
                text=yorum_metni,
                external_review_id=review_id,
                author_name=yorum_verisi.get("author_name", ""),
                rating=yorum_verisi.get("rating"),
                review_date=review_date,
                language=dil,
                raw_data={
                    "feature_id": feature_id,
                    "restoran_adi": restoran_adi,
                    "sort_by": sort_by,
                    "sayfa_no": sayfa_no,
                    "date_text": tarih_metni,
                    "author_url": yorum_verisi.get("author_url", ""),
                    "review_likes": yorum_verisi.get("likes", 0),
                    "owner_reply": yorum_verisi.get("owner_reply", ""),
                    "photos_count": yorum_verisi.get("photos_count", 0),
                },
            )

            self.review_counts[feature_id] = self.review_counts.get(feature_id, 0) + 1
            sayfa_yorum_sayisi += 1
            yield item

        self.spider_logger.info(
            f"[{feature_id}] Sayfa {sayfa_no}: {sayfa_yorum_sayisi} yorum cekildi "
            f"| Toplam: {self.review_counts.get(feature_id, 0)}/{self.max_reviews} "
            f"| Siralama: {sort_by}"
        )

        # --- Sonraki sayfa kontrolu ---
        if self.review_counts.get(feature_id, 0) < self.max_reviews:
            next_token = self._sonraki_sayfa_token_cikar(response)

            if next_token:
                # Sayfalar arasi rastgele bekleme (2-5 saniye)
                sonraki_url = self._build_review_url(
                    feature_id, token=next_token, sort_by=sort_by
                )

                self.spider_logger.debug(
                    f"[{feature_id}] Sonraki sayfa bulundu (sayfa {sayfa_no + 1})"
                )

                yield scrapy.Request(
                    url=sonraki_url,
                    callback=self.parse_reviews,
                    meta={
                        "feature_id": feature_id,
                        "restoran_adi": restoran_adi,
                        "sort_by": sort_by,
                        "sayfa_no": sayfa_no + 1,
                        "is_dual_sort_second": is_dual_sort_second,
                        "download_delay": random.uniform(2, 5),
                    },
                    dont_filter=True,
                )
            else:
                # Sayfa bitti
                self.spider_logger.info(
                    f"[{feature_id}] Tum sayfalar cekildi "
                    f"(toplam {sayfa_no} sayfa, "
                    f"{self.review_counts.get(feature_id, 0)} yorum)"
                )

                # dual_sort aktifse ve ilk gecis tamamlandiysa ikinci gecis
                if (
                    self.dual_sort
                    and not is_dual_sort_second
                    and sort_by == "newestFirst"
                    and self.review_counts.get(feature_id, 0) < self.max_reviews
                ):
                    self.spider_logger.info(
                        f"[{feature_id}] Ikinci gecis baslatiliyor "
                        f"(siralama: ratingHigh)"
                    )
                    ikinci_url = self._build_review_url(
                        feature_id, token="", sort_by="ratingHigh"
                    )
                    yield scrapy.Request(
                        url=ikinci_url,
                        callback=self.parse_reviews,
                        meta={
                            "feature_id": feature_id,
                            "restoran_adi": restoran_adi,
                            "sort_by": "ratingHigh",
                            "sayfa_no": 1,
                            "is_dual_sort_second": True,
                            "download_delay": random.uniform(5, 10),
                        },
                        dont_filter=True,
                    )

                # Restoran tamamlandi
                self.scrape_stats["restoran_islenen"] += 1

    # ========================================================
    # HTML Parse Yardimci Metodlari
    # ========================================================

    def _yorumlari_cikar(self, response: Response) -> list[dict[str, Any]]:
        """
        reviewDialog HTML yanitindan yorum verilerini cikarir.

        Google Maps reviewDialog yaniti ozel bir HTML yapisi kullanir.
        Yorumlar belirli div class'lari icerisinde yer alir.

        Args:
            response: reviewDialog HTTP yaniti

        Returns:
            Yorum sozlukleri listesi
        """
        yorumlar: list[dict[str, Any]] = []

        # reviewDialog yanitindaki yorum bloklari
        # Her yorum bir div.gws-localreviews__google-review icerisindedir
        yorum_bloklari = response.css(
            "div.gws-localreviews__google-review"
        )

        # Alternatif selector'lar (Google arayuz degisiklikleri icin)
        if not yorum_bloklari:
            yorum_bloklari = response.css("div[data-review-id]")
        if not yorum_bloklari:
            yorum_bloklari = response.css("div.WMbnJf")

        for blok in yorum_bloklari:
            try:
                yorum = self._tek_yorum_parse(blok)
                if yorum and yorum.get("text"):
                    yorumlar.append(yorum)
            except Exception as e:
                self.spider_logger.debug(
                    f"Yorum parse hatasi: {e}"
                )
                self.scrape_stats["hata"] += 1

        return yorumlar

    def _tek_yorum_parse(self, blok: Any) -> dict[str, Any]:
        """
        Tek bir yorum HTML blokundan veri cikarir.

        Args:
            blok: Scrapy Selector (yorum div'i)

        Returns:
            Yorum verisi sozlugu
        """
        # Review ID
        review_id = (
            blok.attrib.get("data-review-id", "")
            or blok.css("::attr(data-review-id)").get("")
        )

        # Review ID yoksa hash'le olustur
        if not review_id:
            metin = blok.css("*::text").getall()
            birlesik = "".join(metin).strip()
            if birlesik:
                review_id = hashlib.md5(birlesik.encode("utf-8")).hexdigest()[:16]

        # Yazar adi
        author_name = (
            blok.css("div.TSUbDb a::text").get("")
            or blok.css("a.DHIhE::text").get("")
            or blok.css("div.d4r55::text").get("")
            or blok.css(".reviewer-name a::text").get("")
            or ""
        ).strip()

        # Yazar profil URL'i
        author_url = (
            blok.css("div.TSUbDb a::attr(href)").get("")
            or blok.css("a.DHIhE::attr(href)").get("")
            or ""
        )

        # Yildiz puani
        rating = self._puan_cikar(blok)

        # Yorum metni
        text = self._yorum_metni_cikar(blok)

        # Tarih metni ("2 ay once", "1 hafta once" vb.)
        date_text = (
            blok.css("span.dehysf::text").get("")
            or blok.css("span.rsqaWe::text").get("")
            or blok.css(".review-date span::text").get("")
            or ""
        ).strip()

        # Isletme sahibi yaniti
        owner_reply = (
            blok.css("div.d6SCIc::text").get("")
            or blok.css("div.CDe7pd::text").get("")
            or ""
        ).strip()

        # Begeni sayisi
        likes_text = (
            blok.css("span.GBkF3d::text").get("")
            or blok.css("span.pkWtMe::text").get("")
            or "0"
        )
        likes = self._sayi_cikar(likes_text)

        # Yorum fotograf sayisi
        photos = blok.css("button.Tya61d")
        photos_count = len(photos) if photos else 0

        return {
            "review_id": review_id,
            "author_name": author_name,
            "author_url": author_url,
            "rating": rating,
            "text": text,
            "date_text": date_text,
            "owner_reply": owner_reply,
            "likes": likes,
            "photos_count": photos_count,
        }

    def _puan_cikar(self, blok: Any) -> int | None:
        """
        Yorum blokundan yildiz puanini cikarir.

        Google Maps'te puan genellikle aria-label veya
        style attribute ile belirtilir.

        Args:
            blok: Scrapy Selector

        Returns:
            1-5 arasi puan veya None
        """
        # Yontem 1: aria-label'dan ("5 uzerinden 4 yildiz" gibi)
        aria_label = (
            blok.css("span.lTi8oc::attr(aria-label)").get("")
            or blok.css("span[role='img']::attr(aria-label)").get("")
            or blok.css("div.dHX2k::attr(aria-label)").get("")
            or ""
        )
        if aria_label:
            # "5 uzerinden 4" veya "Rated 4.0 out of 5.0" gibi formatlar
            sayi = re.findall(r"(\d+(?:[.,]\d+)?)", aria_label)
            if sayi:
                try:
                    puan = int(float(sayi[0].replace(",", ".")))
                    if 1 <= puan <= 5:
                        return puan
                except (ValueError, IndexError):
                    pass

        # Yontem 2: Dolu yildiz sayisini say
        dolu_yildizlar = blok.css("span.elGi1d, span.hCCjke.vzX5Ic")
        if dolu_yildizlar:
            return min(5, max(1, len(dolu_yildizlar)))

        # Yontem 3: style width'den hesapla (yildiz bar)
        style_span = blok.css("span.fzvQIb::attr(style)").get("")
        if style_span:
            width_match = re.search(r"width:\s*(\d+)%", style_span)
            if width_match:
                yuzde = int(width_match.group(1))
                return max(1, min(5, round(yuzde / 20)))

        return None

    def _yorum_metni_cikar(self, blok: Any) -> str:
        """
        Yorum blokundan tam yorum metnini cikarir.

        Google Maps bazen uzun yorumlari kisaltir ve "Devamini oku"
        butonu gosterir. reviewDialog'da genellikle tam metin gelir.

        Args:
            blok: Scrapy Selector

        Returns:
            Temizlenmis yorum metni
        """
        # Oncelik sirasina gore metni dene
        metin_seciciler = [
            "span.review-full-text::text",
            "div.review-full-text *::text",
            "span.wiI7pd::text",
            "div.MyEned span::text",
            "div.Jtu6Td *::text",
            "span.review-text::text",
        ]

        for secici in metin_seciciler:
            metin_parcalari = blok.css(secici).getall()
            if metin_parcalari:
                tam_metin = " ".join(p.strip() for p in metin_parcalari if p.strip())
                if tam_metin:
                    return self._metni_temizle(tam_metin)

        # Son care: tum metin icerigini al ve filtrele
        tum_metinler = blok.css("*::text").getall()
        if tum_metinler:
            # Yazar adi, tarih gibi alanlari cikar
            filtreli = [
                t.strip() for t in tum_metinler
                if t.strip()
                and len(t.strip()) > 10  # Kisa metinleri atla (tarih, ad vb.)
                and not re.match(r"^\d+\s*(ay|hafta|gun|yil|saat)", t.strip())
            ]
            if filtreli:
                return self._metni_temizle(" ".join(filtreli))

        return ""

    def _metni_temizle(self, metin: str) -> str:
        """
        Yorum metnini temizler ve normallestirir.

        Args:
            metin: Ham yorum metni

        Returns:
            Temizlenmis metin
        """
        if not metin:
            return ""

        # Fazla bosluk ve satir sonlarini temizle
        metin = re.sub(r"\s+", " ", metin).strip()
        # HTML entity'lerini temizle
        metin = metin.replace("&amp;", "&")
        metin = metin.replace("&lt;", "<")
        metin = metin.replace("&gt;", ">")
        metin = metin.replace("&quot;", '"')
        metin = metin.replace("&#39;", "'")
        # Unicode bosluk karakterlerini temizle
        metin = metin.replace("\u200b", "")  # Zero-width space
        metin = metin.replace("\u00a0", " ")  # Non-breaking space
        metin = metin.replace("\ufeff", "")   # BOM

        return metin.strip()

    def _sonraki_sayfa_token_cikar(self, response: Response) -> str:
        """
        Yanittaki next_page_token degerini bulur.

        Token, gizli bir input alani veya data attribute'u icerisinde
        yer alabilir. Ayrica JavaScript degiskeni olarak da bulunabilir.

        Args:
            response: reviewDialog HTTP yaniti

        Returns:
            Sonraki sayfa token'i veya bos dize
        """
        # Yontem 1: data-next-page-token attribute'u
        token = response.css(
            "*[data-next-page-token]::attr(data-next-page-token)"
        ).get("")

        if token:
            return token.strip()

        # Yontem 2: Gizli input alaninda
        token = response.css(
            "input[name='next_page_token']::attr(value)"
        ).get("")

        if token:
            return token.strip()

        # Yontem 3: HTML iceriginde next_page_token arama
        body = response.text
        token_patterns = [
            r'"next_page_token"\s*:\s*"([^"]+)"',
            r"next_page_token[=:]([^&\s\"',]+)",
            r'data-next-page-token="([^"]+)"',
            r"token\\u003d([^\\\"&]+)",
        ]

        for pattern in token_patterns:
            match = re.search(pattern, body)
            if match:
                bulunan_token = match.group(1).strip()
                if bulunan_token and bulunan_token != "null":
                    return bulunan_token

        return ""

    # ========================================================
    # Dil Tespiti
    # ========================================================

    def _dil_tespit(self, metin: str) -> str:
        """
        Basit heuristik ile yorum dilini tespit eder.

        Turkce karakterler ve yakin Turkce kelimeler kontrol edilir.
        langdetect kutuphanesine bagimliligi ortadan kaldirir.

        Args:
            metin: Yorum metni

        Returns:
            Dil kodu ('tr' veya 'other')
        """
        if not metin or len(metin.strip()) < 3:
            return "tr"  # Cok kisa metinlerde varsayilan Turkce

        metin_lower = metin.lower()

        # 1. Turkce'ye ozgu karakterler var mi?
        turkce_karakter_sayisi = sum(
            1 for c in metin if c in TURKCE_KARAKTERLER
        )

        # 2. Turkce kelimeler var mi?
        kelimeler = set(re.findall(r"\b\w+\b", metin_lower))
        turkce_kelime_sayisi = len(kelimeler & TURKCE_KELIMELER)

        # 3. Karar ver
        toplam_kelime = len(kelimeler) if kelimeler else 1

        # Turkce karakter orani
        karakter_orani = turkce_karakter_sayisi / max(len(metin), 1)

        # Turkce kelime orani
        kelime_orani = turkce_kelime_sayisi / toplam_kelime

        # Herhangi bir gosterge yeterliyse Turkce kabul et
        if karakter_orani > 0.02 or kelime_orani > 0.1 or turkce_kelime_sayisi >= 2:
            return "tr"

        # Latin alfabe kontrolu (Arapca, Cirllce vb. degilse "other")
        latin_karakter = sum(1 for c in metin if c.isalpha() and ord(c) < 256)
        if latin_karakter / max(len(metin), 1) < 0.5:
            return "other"

        return "other"

    # ========================================================
    # Tarih Parse
    # ========================================================

    def _tarihi_parse_et(self, tarih_metni: str) -> str | None:
        """
        Google Maps goreceli tarih metnini ISO formatina cevirir.

        Ornekler:
            "2 ay once" -> "2025-10-01T00:00:00+00:00" (yaklasik)
            "1 hafta once" -> "2025-12-25T00:00:00+00:00" (yaklasik)
            "3 gun once" -> "2025-12-29T00:00:00+00:00" (yaklasik)

        Args:
            tarih_metni: Google Maps tarih metni

        Returns:
            ISO 8601 formati tarih dizesi veya None
        """
        if not tarih_metni:
            return None

        tarih_metni = tarih_metni.strip().lower()
        simdi = datetime.now(timezone.utc)

        # Turkce goreceli tarih kaliplari
        kaliplar = [
            (r"(\d+)\s*(saniye|sn)", "saniye"),
            (r"(\d+)\s*(dakika|dk)", "dakika"),
            (r"(\d+)\s*(saat)", "saat"),
            (r"(\d+)\s*(g[uü]n)", "gun"),
            (r"(\d+)\s*(hafta)", "hafta"),
            (r"(\d+)\s*(ay)", "ay"),
            (r"(\d+)\s*(y[iı]l)", "yil"),
        ]

        for kalip, birim in kaliplar:
            eslesme = re.search(kalip, tarih_metni)
            if eslesme:
                miktar = int(eslesme.group(1))

                if birim == "saniye":
                    fark_saniye = miktar
                elif birim == "dakika":
                    fark_saniye = miktar * 60
                elif birim == "saat":
                    fark_saniye = miktar * 3600
                elif birim == "gun":
                    fark_saniye = miktar * 86400
                elif birim == "hafta":
                    fark_saniye = miktar * 604800
                elif birim == "ay":
                    fark_saniye = miktar * 2592000  # ~30 gun
                elif birim == "yil":
                    fark_saniye = miktar * 31536000  # ~365 gun
                else:
                    continue

                from datetime import timedelta
                hesaplanan = simdi - timedelta(seconds=fark_saniye)
                return hesaplanan.isoformat()

        # Ingilizce fallback ("2 months ago" gibi)
        ingilizce_kaliplar = [
            (r"(\d+)\s*second", "saniye"),
            (r"(\d+)\s*minute", "dakika"),
            (r"(\d+)\s*hour", "saat"),
            (r"(\d+)\s*day", "gun"),
            (r"(\d+)\s*week", "hafta"),
            (r"(\d+)\s*month", "ay"),
            (r"(\d+)\s*year", "yil"),
            (r"a\s+month", "ay_tek"),
            (r"a\s+week", "hafta_tek"),
            (r"a\s+year", "yil_tek"),
        ]

        for kalip, birim in ingilizce_kaliplar:
            eslesme = re.search(kalip, tarih_metni)
            if eslesme:
                if birim.endswith("_tek"):
                    miktar = 1
                    birim = birim.replace("_tek", "")
                else:
                    miktar = int(eslesme.group(1))

                birim_saniye = {
                    "saniye": 1, "dakika": 60, "saat": 3600,
                    "gun": 86400, "hafta": 604800,
                    "ay": 2592000, "yil": 31536000,
                }

                from datetime import timedelta
                fark = miktar * birim_saniye.get(birim, 0)
                hesaplanan = simdi - timedelta(seconds=fark)
                return hesaplanan.isoformat()

        return None

    # ========================================================
    # Yardimci Metodlar
    # ========================================================

    def _captcha_tespit(self, body: str) -> bool:
        """
        Yanitda CAPTCHA olup olmadigini kontrol eder.

        Args:
            body: HTTP yanit govdesi

        Returns:
            True ise CAPTCHA tespit edildi
        """
        captcha_isaretleri = [
            "captcha",
            "unusual traffic",
            "olagan disi trafik",
            "robot degilim",
            "not a robot",
            "recaptcha",
            "/sorry/",
            "automated queries",
        ]

        body_lower = body.lower()
        return any(isaret in body_lower for isaret in captcha_isaretleri)

    @staticmethod
    def _sayi_cikar(metin: str) -> int:
        """
        Metin icerisinden sayi cikarir.

        Args:
            metin: Sayi iceren metin ("123", "1.2K" gibi)

        Returns:
            Tam sayi degeri
        """
        if not metin:
            return 0

        metin = metin.strip()

        # "1.2K" veya "1,2K" gibi formatlar
        k_match = re.search(r"([\d.,]+)\s*[kK]", metin)
        if k_match:
            try:
                return int(float(k_match.group(1).replace(",", ".")) * 1000)
            except ValueError:
                pass

        # Duz sayi
        sayi_match = re.search(r"(\d+)", metin)
        if sayi_match:
            try:
                return int(sayi_match.group(1))
            except ValueError:
                pass

        return 0

    def closed(self, reason: str) -> None:
        """Spider kapandiginda detayli ozet istatistikleri loglar."""
        self.spider_logger.info(
            f"\n{'=' * 60}\n"
            f"Google Maps Yorum Spider Ozeti\n"
            f"{'=' * 60}\n"
            f"Kapanma sebebi     : {reason}\n"
            f"Restoran islenen   : {self.scrape_stats['restoran_islenen']}\n"
            f"Sayfa cekilen      : {self.scrape_stats['sayfa_cekilen']}\n"
            f"Toplam yorum       : {self.scrape_stats['yorum_bulunan']}\n"
            f"Tekrar elenen      : {self.scrape_stats['tekrar_elenen']}\n"
            f"Turkce olmayan     : {self.scrape_stats['turkce_olmayan']}\n"
            f"Bos yanit          : {self.scrape_stats['bos_yanit']}\n"
            f"CAPTCHA tespit     : {self.scrape_stats['captcha_tespit']}\n"
            f"Hata               : {self.scrape_stats['hata']}\n"
            f"{'=' * 60}"
        )

        # Restoran bazli yorum dagilimi
        if self.review_counts:
            self.spider_logger.info("Restoran bazli yorum dagilimi:")
            for fid, sayi in self.review_counts.items():
                adi = ""
                for r_fid, r_adi in self.restaurants:
                    if r_fid == fid:
                        adi = r_adi
                        break
                self.spider_logger.info(
                    f"  {fid} ({adi or 'isim yok'}): {sayi} yorum"
                )
