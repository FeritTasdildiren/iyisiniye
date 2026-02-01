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
import random
import re
from typing import Any, Generator
from urllib.parse import unquote

import scrapy
from loguru import logger
from scrapy.http import Response

from ..items import RestaurantItem, ReviewItem
from .base_spider import BaseSpider


# --- Playwright sayfa baslatma callback'i ---

async def stealth_init_callback(page: Any) -> None:
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
    custom_settings: dict[str, Any] = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 5,
        "DOWNLOAD_TIMEOUT": 60,
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 45000,
        "PLAYWRIGHT_CONTEXTS": {
            "default": {
                "viewport": {"width": 1920, "height": 1080},
                "locale": "tr-TR",
                "timezone_id": "Europe/Istanbul",
                "java_script_enabled": True,
                "bypass_csp": False,
            },
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

    # --- Arama URL Sablonu ---
    SEARCH_URL_TEMPLATE = (
        "https://www.google.com/maps/search/restoran/@{lat},{lng},{zoom}z"
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

        # Grid noktalarini hesapla
        self.grid_noktalari: list[tuple[float, float]] = self._grid_noktalari_hesapla()

        self.spider_logger.info(
            f"GoogleMapsListSpider baslatildi: "
            f"grid={self.grid_size}x{self.grid_size} ({len(self.grid_noktalari)} nokta), "
            f"zoom={self.zoom}, maks_scroll={self.max_scroll}"
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

    def start_requests(self) -> Generator[scrapy.Request, None, None]:
        """
        Grid noktalarindan baslangic istekleri uretir.

        Her grid noktasi icin Google Maps arama URL'i olusturulur
        ve Playwright ile sayfa acma istegi yapilir.
        """
        for idx, (lat, lng) in enumerate(self.grid_noktalari):
            url = self.SEARCH_URL_TEMPLATE.format(
                lat=lat, lng=lng, zoom=self.zoom
            )

            self.spider_logger.info(
                f"Grid noktasi {idx + 1}/{len(self.grid_noktalari)}: "
                f"({lat}, {lng}) -> {url}"
            )

            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta={
                    "playwright": True,
                    "playwright_context": "default",
                    "playwright_include_page": True,
                    "playwright_page_init_callback": stealth_init_callback,
                    "grid_index": idx,
                    "grid_lat": lat,
                    "grid_lng": lng,
                },
                dont_filter=True,
                errback=self.hata_yakala,
            )

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
            items, restoran_sayisi = await self._restoran_verilerini_cikar(page, response)
            for item in items:
                yield item

            # Basarili tarama - ardisik hata sayacini sifirla
            self.scrape_stats["ardisik_hata"] = 0
            self.scrape_stats["taranan_grid_noktasi"] += 1

            self.spider_logger.info(
                f"Grid noktasi {grid_index + 1} tamamlandi: "
                f"{restoran_sayisi} restoran bulundu, "
                f"toplam benzersiz: {self.scrape_stats['benzersiz_restoran']}"
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
        """
        try:
            # Google'in cookie onay diyalogu icin farkli selectorlar dene
            cookie_selectorlar = [
                # "Tumu kabul et" butonu
                'button[aria-label="Tümünü kabul et"]',
                'button[aria-label="Accept all"]',
                # Form bazli selectorlar
                'form[action*="consent"] button',
                'div[role="dialog"] button',
                # Genel cookie banner selectorlari
                '[data-ved] button:has-text("Kabul")',
                '[data-ved] button:has-text("Accept")',
            ]

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
                        self.spider_logger.debug(
                            f"Cookie diyalogu kapatildi (selector: {selector})"
                        )
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                        return
                except Exception:
                    continue

            self.spider_logger.debug("Cookie diyalogu bulunamadi (muhtemelen zaten kabul edilmis)")

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
            # networkidle bekle
            await page.wait_for_load_state("networkidle", timeout=30000)

            # Ekstra bekleme (JS render tamamlanmasi icin)
            ekstra_bekleme = random.uniform(3.0, 5.0)
            await asyncio.sleep(ekstra_bekleme)

            # Sonuc paneli veya harita konteynerini ara
            sonuc_selektorlari = [
                'div[role="feed"]',
                'div[role="main"]',
                'div.m6QErb',
            ]

            for selector in sonuc_selektorlari:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        self.spider_logger.debug(
                            f"Sonuc paneli bulundu: {selector}"
                        )
                        return True
                except Exception:
                    continue

            # Son care: body icerigini kontrol et
            body = await page.content()
            if "restoran" in body.lower() or "restaurant" in body.lower():
                self.spider_logger.debug("Sayfa icerigi restoran verisi iceriyor")
                return True

            self.spider_logger.warning("Sonuc paneli bulunamadi")
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
    ) -> tuple[list, int]:
        """
        Sonuc panelindeki restoran kartlarindan veri cikarir.

        Her kart icin: ad, adres, puan, yorum sayisi, kategori,
        fiyat seviyesi, URL ve koordinat bilgilerini toplar.

        Args:
            page: Playwright sayfa nesnesi
            response: Scrapy Response nesnesi

        Returns:
            (items listesi, bulunan restoran sayisi) tuple'i
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
                return ([], 0)

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

                    # RestaurantItem olustur
                    item = self.build_restaurant_item(
                        name=restoran_verisi.get("name", ""),
                        source_id=source_id,
                        address=restoran_verisi.get("address", ""),
                        district="",
                        neighborhood="",
                        city="istanbul",
                        latitude=restoran_verisi.get("latitude"),
                        longitude=restoran_verisi.get("longitude"),
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

        return (items, bulunan_sayisi)

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

    async def hata_yakala(self, failure: Any) -> None:
        """
        Scrapy Request hata callback'i.

        Timeout, baglanti hatasi vb. durumlarda cagrilir.
        Hatayi loglar ve istatistikleri gunceller.

        Args:
            failure: Twisted Failure nesnesi
        """
        self.spider_logger.error(
            f"Istek hatasi: {failure.type.__name__}: {failure.value} "
            f"URL: {failure.request.url}"
        )
        self.scrape_stats["hata"] += 1
        self._ardisik_hata_kontrolu()

        # Playwright sayfasini temizle
        page = failure.request.meta.get("playwright_page")
        if page:
            try:
                await page.close()
            except Exception:
                pass

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
