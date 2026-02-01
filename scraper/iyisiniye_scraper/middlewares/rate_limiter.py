"""
Adaptif Rate Limiting Middleware

Platform bazli adaptif hiz sinirlandirma middleware'i.
Her platform icin farkli istek limitleri, exponential backoff,
IP bazli istek takibi ve gunluk/saatlik limit yonetimi saglar.

Scrapy DOWNLOADER_MIDDLEWARES'a eklenmeli:
    "iyisiniye_scraper.middlewares.rate_limiter.AdaptiveRateLimiter": 420

Middleware sirasi onemlisi:
    - RotatingUserAgentMiddleware (400): UA rotasyonu
    - SkyStoneProxyDownloaderMiddleware (410): Proxy atamasi
    - AdaptiveRateLimiter (420): Rate limiting (proxy atandiktan SONRA calismali)
    - RetryMiddleware (500): Yeniden deneme
"""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from scrapy import Spider, signals
from scrapy.crawler import Crawler
from scrapy.exceptions import CloseSpider, IgnoreRequest, NotConfigured
from scrapy.http import Request, Response


# Varsayilan platform limitleri
# Spider'in custom_settings veya settings.py uzerinden override edilebilir
VARSAYILAN_PLATFORM_LIMITLERI: dict[str, dict[str, Any]] = {
    "google_maps": {
        "daily": 5000,       # Gunluk maksimum istek
        "hourly": 500,       # Saatlik maksimum istek
        "delay": 3,          # Istekler arasi minimum bekleme (saniye)
        "max_backoff": 120,  # Maksimum backoff suresi (saniye)
    },
    "yemeksepeti": {
        "daily": 10000,
        "hourly": 1000,
        "delay": 1,
        "max_backoff": 60,
    },
    "tripadvisor": {
        "daily": 8000,
        "hourly": 800,
        "delay": 2,
        "max_backoff": 90,
    },
    "foursquare": {
        "daily": 15000,
        "hourly": 1500,
        "delay": 0.5,
        "max_backoff": 60,
    },
    "default": {
        "daily": 10000,
        "hourly": 1000,
        "delay": 2,
        "max_backoff": 90,
    },
}


class AdaptiveRateLimiter:
    """
    Platform bazli adaptif rate limiting middleware.

    Ozellikler:
        - Her platform icin ayri istek limiti (gunluk/saatlik)
        - Exponential backoff: 429/ban yanitlarinda bekleme suresini 2x artirir
        - IP bazli istek sayisi takibi (proxy IP'leri dahil)
        - Gunluk limit asilinca spider'i graceful olarak durdurur
        - Detayli istatistik toplama

    Middleware Sirasi:
        Bu middleware, proxy middleware'den SONRA calismalidir (ornek: 420).
        Boylece proxy atandiktan sonra IP bazli rate limit uygulanabilir.
    """

    def __init__(
        self,
        varsayilan_gecikme: float = 3.0,
        platform_limitleri: dict[str, dict[str, Any]] | None = None,
        etkin: bool = True,
    ) -> None:
        """
        Args:
            varsayilan_gecikme: Hicbir platform eslesmediyse kullanilacak
                               varsayilan bekleme suresi (saniye)
            platform_limitleri: Platform bazli limit ayarlari sozlugu.
                               Ornek: {'google_maps': {'daily': 5000, ...}}
            etkin: Middleware etkin mi? False ise hicbir sey yapmaz.
        """
        self.etkin = etkin
        self.varsayilan_gecikme = varsayilan_gecikme

        # Platform limitlerini birlestir (kullanici ayarlari > varsayilan)
        self.platform_limitleri: dict[str, dict[str, Any]] = {
            **VARSAYILAN_PLATFORM_LIMITLERI
        }
        if platform_limitleri:
            for platform, ayarlar in platform_limitleri.items():
                if platform in self.platform_limitleri:
                    self.platform_limitleri[platform].update(ayarlar)
                else:
                    self.platform_limitleri[platform] = ayarlar

        # Platform bazli istek sayaclari: {platform: sayi}
        self._gunluk_sayac: defaultdict[str, int] = defaultdict(int)
        self._saatlik_sayac: defaultdict[str, int] = defaultdict(int)

        # Sayac sifirlama zamanlari
        self._gunluk_sifirlama: float = self._sonraki_gun_baslangici()
        self._saatlik_sifirlama: float = self._sonraki_saat_baslangici()

        # Exponential backoff takibi: {platform: mevcut_backoff_suresi}
        self._backoff_suresi: defaultdict[str, float] = defaultdict(float)

        # IP bazli istek sayaci: {ip_adresi: [timestamp_listesi]}
        self._ip_istek_kaydi: defaultdict[str, list[float]] = defaultdict(list)

        # Son istek zamani: {platform: timestamp}
        self._son_istek_zamani: defaultdict[str, float] = defaultdict(float)

        # Istatistikler
        self.istatistikler: dict[str, Any] = {
            "toplam_istek": 0,
            "platform_bazli": defaultdict(int),
            "toplam_bekleme_suresi": 0.0,
            "backoff_sayisi": 0,
            "maks_bekleme": 0.0,
            "gunluk_limit_asilma": 0,
            "saatlik_limit_asilma": 0,
            "ip_bazli_bekleme": 0,
        }

        self.mw_logger = logger.bind(middleware="AdaptiveRateLimiter")

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "AdaptiveRateLimiter":
        """
        Scrapy crawler'dan middleware ornegi olusturur.

        Settings'den okunan ayarlar:
            - RATE_LIMITER_ENABLED: Middleware etkin mi (bool, varsayilan: True)
            - RATE_LIMITER_DEFAULT_DELAY: Varsayilan gecikme (float, varsayilan: 3)
            - RATE_LIMITER_PLATFORM_LIMITS: Platform bazli limitler (dict)

        Spider'in custom_settings'i ile bu ayarlar override edilebilir.
        """
        etkin = crawler.settings.getbool("RATE_LIMITER_ENABLED", True)

        if not etkin:
            raise NotConfigured(
                "AdaptiveRateLimiter devre disi birakildi (RATE_LIMITER_ENABLED=False)"
            )

        varsayilan_gecikme = crawler.settings.getfloat(
            "RATE_LIMITER_DEFAULT_DELAY", 3.0
        )
        platform_limitleri = crawler.settings.getdict(
            "RATE_LIMITER_PLATFORM_LIMITS", None
        )

        middleware = cls(
            varsayilan_gecikme=varsayilan_gecikme,
            platform_limitleri=platform_limitleri,
            etkin=etkin,
        )

        # Crawler sinyallerine baglan
        crawler.signals.connect(
            middleware.spider_acildi, signal=signals.spider_opened
        )
        crawler.signals.connect(
            middleware.spider_kapandi, signal=signals.spider_closed
        )

        return middleware

    # ---- Scrapy Sinyal Metodlari ----

    def spider_acildi(self, spider: Spider) -> None:
        """Spider basladiginda rate limiter bilgilerini loglar."""
        platform = getattr(spider, "platform_name", "default")
        limitler = self._platform_limitlerini_al(platform)

        self.mw_logger.info(
            f"AdaptiveRateLimiter baslatildi | "
            f"Platform: {platform} | "
            f"Gunluk limit: {limitler['daily']} | "
            f"Saatlik limit: {limitler['hourly']} | "
            f"Gecikme: {limitler['delay']}s | "
            f"Maks backoff: {limitler['max_backoff']}s"
        )

    def spider_kapandi(self, spider: Spider) -> None:
        """Spider kapandiginda ozet istatistikleri loglar."""
        ort_bekleme = 0.0
        if self.istatistikler["toplam_istek"] > 0:
            ort_bekleme = (
                self.istatistikler["toplam_bekleme_suresi"]
                / self.istatistikler["toplam_istek"]
            )

        self.mw_logger.info("=== AdaptiveRateLimiter Istatistikleri ===")
        self.mw_logger.info(
            f"  Toplam istek: {self.istatistikler['toplam_istek']}"
        )
        self.mw_logger.info(
            f"  Platform bazli: {dict(self.istatistikler['platform_bazli'])}"
        )
        self.mw_logger.info(
            f"  Toplam bekleme: {self.istatistikler['toplam_bekleme_suresi']:.1f}s"
        )
        self.mw_logger.info(f"  Ortalama bekleme: {ort_bekleme:.2f}s")
        self.mw_logger.info(
            f"  Maks bekleme: {self.istatistikler['maks_bekleme']:.1f}s"
        )
        self.mw_logger.info(
            f"  Backoff sayisi: {self.istatistikler['backoff_sayisi']}"
        )
        self.mw_logger.info(
            f"  Gunluk limit asilma: {self.istatistikler['gunluk_limit_asilma']}"
        )
        self.mw_logger.info(
            f"  Saatlik limit asilma: {self.istatistikler['saatlik_limit_asilma']}"
        )
        self.mw_logger.info(
            f"  IP bazli bekleme: {self.istatistikler['ip_bazli_bekleme']}"
        )
        self.mw_logger.info("=" * 55)

    # ---- Scrapy Downloader Middleware Metodlari ----

    def process_request(self, request: Request, spider: Spider) -> None:
        """
        Her giden istek oncesinde rate limit kontrolu yapar.

        Kontrol sirasi:
            1. Sayac sifirlama kontrolleri (gunluk/saatlik)
            2. Gunluk limit kontrolu (asilirsa CloseSpider)
            3. Saatlik limit kontrolu (asilirsa saatin sonuna kadar bekle)
            4. IP bazli istek hizi kontrolu
            5. Platform bazli gecikme uygulama
            6. Aktif backoff varsa ek bekleme

        Args:
            request: Giden Scrapy istegi
            spider: Aktif spider ornegi
        """
        if not self.etkin:
            return None

        platform = getattr(spider, "platform_name", "default")
        limitler = self._platform_limitlerini_al(platform)

        # Sayaclari sifirla (zaman dolmussa)
        self._sayaclari_kontrol_et()

        # --- Gunluk limit kontrolu ---
        if self._gunluk_sayac[platform] >= limitler["daily"]:
            self.istatistikler["gunluk_limit_asilma"] += 1
            self.mw_logger.error(
                f"GUNLUK LIMIT ASILDI! Platform: {platform} | "
                f"Limit: {limitler['daily']} | "
                f"Mevcut: {self._gunluk_sayac[platform]} | "
                f"Spider durduruluyor..."
            )
            raise CloseSpider(
                f"Gunluk istek limiti asildi: {platform} "
                f"({self._gunluk_sayac[platform]}/{limitler['daily']})"
            )

        # --- Saatlik limit kontrolu ---
        if self._saatlik_sayac[platform] >= limitler["hourly"]:
            self.istatistikler["saatlik_limit_asilma"] += 1
            kalan_saniye = max(0, self._saatlik_sifirlama - time.time())

            if kalan_saniye > 0:
                self.mw_logger.warning(
                    f"Saatlik limit asildi: {platform} | "
                    f"Limit: {limitler['hourly']} | "
                    f"Saat sifirlanmasina {kalan_saniye:.0f}s kaldi | "
                    f"Bekleniyor..."
                )
                # Saatlik limitte en fazla 5 dakika bekle, gerisinde spider kapansin
                if kalan_saniye > 300:
                    self.mw_logger.error(
                        f"Saatlik sifirlama icin {kalan_saniye:.0f}s beklemek "
                        f"fazla uzun. Spider durduruluyor."
                    )
                    raise CloseSpider(
                        f"Saatlik istek limiti asildi ve sifirlama cok uzak: "
                        f"{platform} ({kalan_saniye:.0f}s)"
                    )
                self._bekle(kalan_saniye, platform, "saatlik_limit_bekleme")

        # --- IP bazli istek hizi kontrolu ---
        proxy_ip = self._proxy_ip_al(request)
        if proxy_ip:
            self._ip_hiz_kontrolu(proxy_ip, platform)

        # --- Platform bazli gecikme ---
        gecikme = limitler.get("delay", self.varsayilan_gecikme)
        son_istek = self._son_istek_zamani[platform]

        if son_istek > 0:
            gecen_sure = time.time() - son_istek
            kalan_gecikme = gecikme - gecen_sure

            if kalan_gecikme > 0:
                # Aktif backoff varsa gecikmeye ekle
                backoff = self._backoff_suresi[platform]
                toplam_bekleme = kalan_gecikme + backoff

                if backoff > 0:
                    self.mw_logger.debug(
                        f"Backoff aktif: {platform} | "
                        f"Temel gecikme: {kalan_gecikme:.1f}s + "
                        f"Backoff: {backoff:.1f}s = "
                        f"Toplam: {toplam_bekleme:.1f}s"
                    )

                self._bekle(toplam_bekleme, platform, "platform_gecikme")
        elif self._backoff_suresi[platform] > 0:
            # Son istek zamani yok ama backoff aktif (ilk istekten sonra ban yemis)
            self._bekle(
                self._backoff_suresi[platform], platform, "backoff_bekleme"
            )

        # Sayaclari guncelle
        self._gunluk_sayac[platform] += 1
        self._saatlik_sayac[platform] += 1
        self._son_istek_zamani[platform] = time.time()
        self.istatistikler["toplam_istek"] += 1
        self.istatistikler["platform_bazli"][platform] += 1

        # IP istek kaydini guncelle
        if proxy_ip:
            self._ip_istek_kaydi[proxy_ip].append(time.time())

        self.mw_logger.debug(
            f"Istek onaylandi: {platform} | "
            f"Gunluk: {self._gunluk_sayac[platform]}/{limitler['daily']} | "
            f"Saatlik: {self._saatlik_sayac[platform]}/{limitler['hourly']} | "
            f"URL: {request.url[:80]}"
        )

        return None

    def process_response(
        self, request: Request, response: Response, spider: Spider
    ) -> Response:
        """
        Gelen yaniti analiz ederek backoff durumunu gunceller.

        - 429 (Too Many Requests): Backoff suresini 2x artirir
        - 200-399 (Basarili): Backoff suresini sifirlar
        - Diger hata kodlari: Backoff'u hafifce artirir

        Args:
            request: Gonderilen istek
            response: Alinan yanit
            spider: Aktif spider ornegi

        Returns:
            Response nesnesi (degistirilmeden)
        """
        if not self.etkin:
            return response

        platform = getattr(spider, "platform_name", "default")
        limitler = self._platform_limitlerini_al(platform)
        maks_backoff = limitler.get("max_backoff", 120)

        # --- 429 Too Many Requests ---
        if response.status == 429:
            mevcut_backoff = self._backoff_suresi[platform]
            yeni_backoff = max(mevcut_backoff * 2, limitler.get("delay", 2))
            yeni_backoff = min(yeni_backoff, maks_backoff)
            self._backoff_suresi[platform] = yeni_backoff
            self.istatistikler["backoff_sayisi"] += 1

            # Retry-After header'ini kontrol et
            retry_after = response.headers.get(b"Retry-After")
            if retry_after:
                try:
                    retry_saniye = float(retry_after.decode("utf-8"))
                    yeni_backoff = min(retry_saniye, maks_backoff)
                    self._backoff_suresi[platform] = yeni_backoff
                    self.mw_logger.warning(
                        f"429 yaniti (Retry-After: {retry_saniye}s): {platform} | "
                        f"Backoff: {yeni_backoff:.1f}s | URL: {request.url[:80]}"
                    )
                except (ValueError, UnicodeDecodeError):
                    pass

            self.mw_logger.warning(
                f"429 yaniti alindi: {platform} | "
                f"Backoff arttirildi: {mevcut_backoff:.1f}s -> {yeni_backoff:.1f}s | "
                f"URL: {request.url[:80]}"
            )
            return response

        # --- Ban/engelleme algilama (403, 407) ---
        if response.status in (403, 407):
            mevcut_backoff = self._backoff_suresi[platform]
            yeni_backoff = max(mevcut_backoff * 2, limitler.get("delay", 2))
            yeni_backoff = min(yeni_backoff, maks_backoff)
            self._backoff_suresi[platform] = yeni_backoff
            self.istatistikler["backoff_sayisi"] += 1

            self.mw_logger.warning(
                f"Ban/engelleme tespit edildi (HTTP {response.status}): {platform} | "
                f"Backoff: {yeni_backoff:.1f}s | URL: {request.url[:80]}"
            )
            return response

        # --- Basarili yanit (200-399) ---
        if 200 <= response.status < 400:
            if self._backoff_suresi[platform] > 0:
                self.mw_logger.debug(
                    f"Basarili yanit, backoff sifirlandi: {platform} | "
                    f"Onceki backoff: {self._backoff_suresi[platform]:.1f}s"
                )
            self._backoff_suresi[platform] = 0.0
            return response

        # --- Diger hata kodlari (5xx vb.) ---
        if response.status >= 500:
            mevcut_backoff = self._backoff_suresi[platform]
            yeni_backoff = max(mevcut_backoff * 1.5, limitler.get("delay", 2))
            yeni_backoff = min(yeni_backoff, maks_backoff)
            self._backoff_suresi[platform] = yeni_backoff

            self.mw_logger.debug(
                f"Sunucu hatasi (HTTP {response.status}): {platform} | "
                f"Backoff hafifce arttirildi: {yeni_backoff:.1f}s"
            )

        return response

    def process_exception(
        self, request: Request, exception: Exception, spider: Spider
    ) -> None:
        """
        Baglanti hatalarinda backoff suresini artirir.

        Timeout, baglanti hatasi, DNS cozumleme hatasi gibi durumlarda
        exponential backoff uygulanir.

        Args:
            request: Hatali istek
            exception: Olusan istisna
            spider: Aktif spider ornegi
        """
        if not self.etkin:
            return None

        platform = getattr(spider, "platform_name", "default")
        limitler = self._platform_limitlerini_al(platform)
        maks_backoff = limitler.get("max_backoff", 120)

        mevcut_backoff = self._backoff_suresi[platform]
        yeni_backoff = max(mevcut_backoff * 2, limitler.get("delay", 2))
        yeni_backoff = min(yeni_backoff, maks_backoff)
        self._backoff_suresi[platform] = yeni_backoff
        self.istatistikler["backoff_sayisi"] += 1

        self.mw_logger.warning(
            f"Baglanti hatasi: {type(exception).__name__} | "
            f"Platform: {platform} | "
            f"Backoff: {mevcut_backoff:.1f}s -> {yeni_backoff:.1f}s | "
            f"URL: {request.url[:80]}"
        )

        return None

    # ---- Yardimci Metodlar ----

    def _platform_limitlerini_al(self, platform: str) -> dict[str, Any]:
        """
        Belirtilen platform icin limit ayarlarini dondurur.

        Platform tanimli degilse 'default' limitleri kullanilir.

        Args:
            platform: Platform adi (ornek: 'google_maps', 'yemeksepeti')

        Returns:
            Platform limit ayarlari sozlugu
        """
        if platform in self.platform_limitleri:
            return self.platform_limitleri[platform]
        return self.platform_limitleri.get("default", {
            "daily": 10000,
            "hourly": 1000,
            "delay": self.varsayilan_gecikme,
            "max_backoff": 90,
        })

    def _sayaclari_kontrol_et(self) -> None:
        """
        Gunluk ve saatlik sayaclarin sifirlama zamanini kontrol eder.
        Zaman dolmussa sayaclari sifirlar.
        """
        simdi = time.time()

        # Gunluk sayac sifirlama
        if simdi >= self._gunluk_sifirlama:
            toplam = sum(self._gunluk_sayac.values())
            if toplam > 0:
                self.mw_logger.info(
                    f"Gunluk sayaclar sifirlandi | "
                    f"Toplam istek: {toplam} | "
                    f"Detay: {dict(self._gunluk_sayac)}"
                )
            self._gunluk_sayac.clear()
            self._gunluk_sifirlama = self._sonraki_gun_baslangici()

        # Saatlik sayac sifirlama
        if simdi >= self._saatlik_sifirlama:
            toplam = sum(self._saatlik_sayac.values())
            if toplam > 0:
                self.mw_logger.debug(
                    f"Saatlik sayaclar sifirlandi | "
                    f"Toplam istek: {toplam}"
                )
            self._saatlik_sayac.clear()
            self._saatlik_sifirlama = self._sonraki_saat_baslangici()

    def _proxy_ip_al(self, request: Request) -> str | None:
        """
        Request meta verisinden proxy IP adresini cikarir.

        SkyStoneProxyMiddleware proxy'yi request.meta['proxy'] alanina
        'http://IP:PORT' formatinda yazar. Bu metod IP kismini ayiklar.

        Args:
            request: Scrapy Request nesnesi

        Returns:
            Proxy IP adresi veya None (proxy yoksa)
        """
        proxy_url = request.meta.get("proxy") or request.meta.get("_proxy_url")
        if not proxy_url:
            return None

        try:
            # 'http://1.2.3.4:8080' -> '1.2.3.4'
            # 'socks5://1.2.3.4:1080' -> '1.2.3.4'
            parcalar = proxy_url.split("://")
            if len(parcalar) >= 2:
                host_port = parcalar[1]
                ip = host_port.split(":")[0]
                return ip
        except (IndexError, ValueError):
            pass

        return None

    def _ip_hiz_kontrolu(self, ip: str, platform: str) -> None:
        """
        Belirtilen IP adresinin dakikadaki istek sayisini kontrol eder.

        Dakikada 30'dan fazla istek yapilmissa kisa bir bekleme uygular.
        Bu, tek bir proxy IP'sinin agendan engellenme riskini azaltir.

        Args:
            ip: Proxy IP adresi
            platform: Aktif platform adi
        """
        simdi = time.time()
        bir_dakika_once = simdi - 60.0

        # Son 1 dakikadaki istekleri filtrele (eski kayitlari temizle)
        self._ip_istek_kaydi[ip] = [
            zaman for zaman in self._ip_istek_kaydi[ip]
            if zaman > bir_dakika_once
        ]

        istek_sayisi = len(self._ip_istek_kaydi[ip])
        maks_ip_istek = 30  # Dakikada maksimum istek/IP

        if istek_sayisi >= maks_ip_istek:
            bekleme = 60.0 - (simdi - self._ip_istek_kaydi[ip][0])
            bekleme = max(bekleme, 1.0)  # En az 1 saniye bekle

            self.mw_logger.warning(
                f"IP hiz limiti: {ip} | "
                f"Dakikadaki istek: {istek_sayisi}/{maks_ip_istek} | "
                f"Bekleme: {bekleme:.1f}s"
            )
            self.istatistikler["ip_bazli_bekleme"] += 1
            self._bekle(bekleme, platform, "ip_hiz_limiti")

    def _bekle(self, sure: float, platform: str, sebep: str) -> None:
        """
        Belirtilen sure kadar bekler ve istatistikleri gunceller.

        Args:
            sure: Bekleme suresi (saniye)
            platform: Aktif platform adi
            sebep: Bekleme sebebi (log icin)
        """
        if sure <= 0:
            return

        # Maksimum tek seferde bekleme: 300 saniye (5 dakika)
        sure = min(sure, 300.0)

        self.mw_logger.debug(
            f"Bekleniyor: {sure:.1f}s | Platform: {platform} | Sebep: {sebep}"
        )

        self.istatistikler["toplam_bekleme_suresi"] += sure
        if sure > self.istatistikler["maks_bekleme"]:
            self.istatistikler["maks_bekleme"] = sure

        time.sleep(sure)

    @staticmethod
    def _sonraki_gun_baslangici() -> float:
        """
        Bir sonraki gunun baslangic zamanini (00:00:00 UTC) timestamp
        olarak dondurur.

        Returns:
            Unix timestamp (float)
        """
        simdi = datetime.now(timezone.utc)
        yarin = simdi.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        # Eger su an gece yarisisini gectiyse bir sonraki gune ayarla
        if yarin <= simdi:
            from datetime import timedelta
            yarin = yarin + timedelta(days=1)
        return yarin.timestamp()

    @staticmethod
    def _sonraki_saat_baslangici() -> float:
        """
        Bir sonraki saatin baslangic zamanini (XX:00:00 UTC) timestamp
        olarak dondurur.

        Returns:
            Unix timestamp (float)
        """
        simdi = datetime.now(timezone.utc)
        sonraki_saat = simdi.replace(
            minute=0, second=0, microsecond=0
        )
        if sonraki_saat <= simdi:
            from datetime import timedelta
            sonraki_saat = sonraki_saat + timedelta(hours=1)
        return sonraki_saat.timestamp()

    def istatistikleri_al(self) -> dict[str, Any]:
        """
        Middleware'in guncel istatistiklerini dondurur.

        Returns:
            Istatistik sozlugu (istek sayilari, bekleme sureleri, limitler)
        """
        ort_bekleme = 0.0
        if self.istatistikler["toplam_istek"] > 0:
            ort_bekleme = (
                self.istatistikler["toplam_bekleme_suresi"]
                / self.istatistikler["toplam_istek"]
            )

        return {
            "toplam_istek": self.istatistikler["toplam_istek"],
            "platform_bazli": dict(self.istatistikler["platform_bazli"]),
            "toplam_bekleme_suresi": round(
                self.istatistikler["toplam_bekleme_suresi"], 2
            ),
            "ortalama_bekleme": round(ort_bekleme, 3),
            "maks_bekleme": round(self.istatistikler["maks_bekleme"], 2),
            "backoff_sayisi": self.istatistikler["backoff_sayisi"],
            "gunluk_limitler": dict(self._gunluk_sayac),
            "saatlik_limitler": dict(self._saatlik_sayac),
            "aktif_backoff": {
                platform: round(sure, 1)
                for platform, sure in self._backoff_suresi.items()
                if sure > 0
            },
            "ip_bazli_bekleme": self.istatistikler["ip_bazli_bekleme"],
            "izlenen_ip_sayisi": len(self._ip_istek_kaydi),
        }


# ---- settings.py'ye eklenecek ayarlar ----
#
# DOWNLOADER_MIDDLEWARES'a eklenecek satir:
#     "iyisiniye_scraper.middlewares.rate_limiter.AdaptiveRateLimiter": 420,
#
# Konfigurasyon ayarlari:
# RATE_LIMITER_ENABLED = True
# RATE_LIMITER_DEFAULT_DELAY = 3  # saniye
# RATE_LIMITER_PLATFORM_LIMITS = {
#     'google_maps': {'daily': 5000, 'hourly': 500, 'delay': 3, 'max_backoff': 120},
#     'yemeksepeti': {'daily': 10000, 'hourly': 1000, 'delay': 1, 'max_backoff': 60},
#     'tripadvisor': {'daily': 8000, 'hourly': 800, 'delay': 2, 'max_backoff': 90},
#     'foursquare': {'daily': 15000, 'hourly': 1500, 'delay': 0.5, 'max_backoff': 60},
# }
#
# Spider bazli override ornegi (spider'in custom_settings'inde):
# custom_settings = {
#     'RATE_LIMITER_DEFAULT_DELAY': 5,
#     'RATE_LIMITER_PLATFORM_LIMITS': {
#         'google_maps': {'daily': 3000, 'hourly': 300, 'delay': 5, 'max_backoff': 180},
#     },
# }
