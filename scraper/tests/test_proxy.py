"""
SkyStone Proxy Middleware Entegrasyon Testleri

Test Senaryolari:
1. Proxy havuzu basariyla dolduruluyor (API mock)
2. Her istekte farkli proxy ataniyor
3. Basarisiz proxy listeden kaldiriliyor
4. Ban algilama calisiyor (403/429)
5. Havuz < 5 oldugunda otomatik yenileniyor
6. API baglanti hatasi durumunda graceful handling
7. Istatistikler dogru toplaniyor
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
import requests
from scrapy.exceptions import NotConfigured
from scrapy.http import Request

from middlewares.proxy_middleware import SkyStoneProxyMiddleware


class TestProxyMiddlewareInit:
    """Middleware baslangic ve konfigurasyonu testleri."""

    def test_init_parametreleri_dogru_ataniyor(self):
        """Middleware init parametrelerinin dogru atandigini dogrular."""
        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com",
            api_key="test-key",
            min_pool_size=10,
            refresh_interval=600,
            ban_threshold=5,
        )

        assert middleware.api_url == "http://test.com"
        assert middleware.api_key == "test-key"
        assert middleware.min_pool_size == 10
        assert middleware.refresh_interval == 600
        assert middleware.ban_threshold == 5
        assert middleware.proxy_pool == {}
        assert len(middleware.blacklisted_proxies) == 0
        assert middleware.stats["toplam_istek"] == 0

    def test_from_crawler_basarili(self, mock_crawler):
        """from_crawler metodunun dogru calistigini dogrular."""
        with patch.object(
            SkyStoneProxyMiddleware, "_refresh_proxy_pool", return_value=None
        ):
            middleware = SkyStoneProxyMiddleware.from_crawler(mock_crawler)

        assert middleware.api_url == "http://test-api.example.com"
        assert middleware.api_key == "test-api-key-12345"
        assert middleware.min_pool_size == 5
        assert middleware.refresh_interval == 300
        assert middleware.ban_threshold == 3

    def test_from_crawler_api_url_eksik(self):
        """API URL eksikse NotConfigured hatasi firlatir."""
        from scrapy.utils.test import get_crawler

        crawler = get_crawler(spidercls=None, settings_dict={"PROXY_API_KEY": "key"})

        with pytest.raises(NotConfigured):
            SkyStoneProxyMiddleware.from_crawler(crawler)

    def test_from_crawler_api_key_eksik(self):
        """API key eksikse NotConfigured hatasi firlatir."""
        from scrapy.utils.test import get_crawler

        crawler = get_crawler(
            spidercls=None, settings_dict={"PROXY_API_URL": "http://test.com"}
        )

        with pytest.raises(NotConfigured):
            SkyStoneProxyMiddleware.from_crawler(crawler)


class TestProxyPool:
    """Proxy havuz yonetimi testleri."""

    @patch("middlewares.proxy_middleware.requests.get")
    def test_proxy_havuzu_basariyla_dolduruluyor(
        self, mock_requests_get, sample_proxy_data
    ):
        """Senaryo 1: API'den proxy'ler basariyla havuza ekleniyor."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = sample_proxy_data
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com",
            api_key="test-key",
        )

        # Havuzu doldur
        middleware._refresh_proxy_pool()

        # Dogrulama
        assert len(middleware.proxy_pool) == 5
        assert "http://192.168.1.1:8080" in middleware.proxy_pool
        assert "http://192.168.1.2:3128" in middleware.proxy_pool
        assert "socks5://192.168.1.4:9999" in middleware.proxy_pool
        assert middleware.stats["havuz_yenileme"] == 1

    @patch("middlewares.proxy_middleware.requests.get")
    def test_api_baglanti_hatasi_graceful_handling(self, mock_requests_get):
        """Senaryo 6: API baglanti hatasi durumunda sistem devam ediyor."""
        # Mock API connection error
        mock_requests_get.side_effect = requests.exceptions.ConnectionError(
            "Connection failed"
        )

        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com",
            api_key="test-key",
        )

        # Havuzu doldurmaya calis - hata firlatilamali
        middleware._refresh_proxy_pool()

        # Havuz bos kalmali ama sistem crash olmamali
        assert len(middleware.proxy_pool) == 0
        assert middleware.stats["havuz_yenileme"] == 1

    @patch("middlewares.proxy_middleware.requests.get")
    def test_api_timeout_hatasi_graceful_handling(self, mock_requests_get):
        """API timeout hatasi durumunda sistem devam ediyor."""
        # Mock API timeout error
        mock_requests_get.side_effect = requests.exceptions.Timeout("Request timeout")

        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com",
            api_key="test-key",
        )

        middleware._refresh_proxy_pool()

        # Havuz bos kalmali ama sistem crash olmamali
        assert len(middleware.proxy_pool) == 0
        assert middleware.stats["havuz_yenileme"] == 1

    @patch("middlewares.proxy_middleware.requests.get")
    def test_kara_listedeki_proxyler_havuza_eklenmiyor(
        self, mock_requests_get, sample_proxy_data
    ):
        """Kara listedeki proxy'ler yenileme sirasinda havuza eklenmiyor."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = sample_proxy_data
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com",
            api_key="test-key",
        )

        # Bir proxy'yi kara listeye al
        middleware.blacklisted_proxies.add("http://192.168.1.1:8080")

        # Havuzu doldur
        middleware._refresh_proxy_pool()

        # Kara listedeki proxy havuzda olmamali
        assert "http://192.168.1.1:8080" not in middleware.proxy_pool
        assert len(middleware.proxy_pool) == 4


class TestProxyAssignment:
    """Proxy atama testleri."""

    @patch("middlewares.proxy_middleware.requests.get")
    def test_her_istekte_proxy_ataniyor(
        self, mock_requests_get, sample_proxy_data, mock_request, mock_spider
    ):
        """Senaryo 2: Her istekte havuzdan proxy ataniyor."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = sample_proxy_data
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com",
            api_key="test-key",
        )
        middleware._refresh_proxy_pool()

        # Request'e proxy ata
        middleware.process_request(mock_request, mock_spider)

        # Proxy atanmis olmali
        assert "proxy" in mock_request.meta
        assert "_proxy_url" in mock_request.meta
        assert mock_request.meta["proxy"].startswith(("http://", "socks5://"))
        assert middleware.stats["toplam_istek"] == 1

    @patch("middlewares.proxy_middleware.requests.get")
    def test_havuz_bossa_proxy_atanmiyor(
        self, mock_requests_get, mock_request, mock_spider
    ):
        """Havuz bossa istek proxy'siz devam ediyor."""
        # Mock API bos response
        mock_response = Mock()
        mock_response.json.return_value = {"success": True, "proxies": []}
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com",
            api_key="test-key",
        )
        middleware._refresh_proxy_pool()

        # Request'e proxy ata
        middleware.process_request(mock_request, mock_spider)

        # Proxy atanmamis olmali
        assert "proxy" not in mock_request.meta
        assert middleware.stats["toplam_istek"] == 1


class TestBanDetection:
    """Ban algilama testleri."""

    def test_ban_algilama_403(
        self, mock_request, mock_response_403, mock_spider, sample_proxy_data
    ):
        """Senaryo 4: HTTP 403 yaniti ban olarak algilaniyor."""
        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com",
            api_key="test-key",
            ban_threshold=1,  # Ilk hatada kara listeye al
        )

        # Proxy havuzunu manuel doldur
        proxy_url = "http://192.168.1.1:8080"
        middleware.proxy_pool[proxy_url] = sample_proxy_data["proxies"][0]
        mock_request.meta["_proxy_url"] = proxy_url

        # 403 yaniti isle
        middleware.process_response(mock_request, mock_response_403, mock_spider)

        # Ban tespit edilmis olmali
        assert middleware.stats["ban_tespit"] == 1
        assert middleware.failure_counts[proxy_url] == 1
        assert proxy_url in middleware.blacklisted_proxies
        assert proxy_url not in middleware.proxy_pool

    def test_ban_algilama_429(
        self, mock_request, mock_response_429, mock_spider, sample_proxy_data
    ):
        """Senaryo 4: HTTP 429 yaniti ban olarak algilaniyor."""
        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com",
            api_key="test-key",
            ban_threshold=1,
        )

        proxy_url = "http://192.168.1.1:8080"
        middleware.proxy_pool[proxy_url] = sample_proxy_data["proxies"][0]
        mock_request.meta["_proxy_url"] = proxy_url

        # 429 yaniti isle
        middleware.process_response(mock_request, mock_response_429, mock_spider)

        # Ban tespit edilmis olmali
        assert middleware.stats["ban_tespit"] == 1
        assert proxy_url in middleware.blacklisted_proxies

    def test_ban_algilama_captcha_icerik(
        self, mock_request, mock_response_captcha, mock_spider, sample_proxy_data
    ):
        """Senaryo 4: CAPTCHA icerigi ban olarak algilaniyor."""
        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com",
            api_key="test-key",
            ban_threshold=1,
        )

        proxy_url = "http://192.168.1.1:8080"
        middleware.proxy_pool[proxy_url] = sample_proxy_data["proxies"][0]
        mock_request.meta["_proxy_url"] = proxy_url

        # CAPTCHA iceren yaniti isle
        middleware.process_response(mock_request, mock_response_captcha, mock_spider)

        # Ban tespit edilmis olmali (recaptcha kalip tespiti)
        assert middleware.stats["ban_tespit"] == 1
        assert proxy_url in middleware.blacklisted_proxies

    def test_basarili_yanit_hata_sayacini_sifirliyor(
        self, mock_request, mock_response_200, mock_spider, sample_proxy_data
    ):
        """Basarili yanit alindinda proxy hata sayaci sifirlaniyor."""
        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com",
            api_key="test-key",
        )

        proxy_url = "http://192.168.1.1:8080"
        middleware.proxy_pool[proxy_url] = sample_proxy_data["proxies"][0]
        middleware.failure_counts[proxy_url] = 2  # Onceki hatalar
        mock_request.meta["_proxy_url"] = proxy_url

        # Basarili yaniti isle
        middleware.process_response(mock_request, mock_response_200, mock_spider)

        # Hata sayaci sifirlanmis olmali
        assert middleware.failure_counts[proxy_url] == 0
        assert middleware.stats["basarili_istek"] == 1


class TestProxyFailureHandling:
    """Proxy hata yonetimi testleri."""

    @patch("middlewares.proxy_middleware.requests.get")
    def test_basarisiz_proxy_listeden_kaldiriliyor(
        self, mock_requests_get, sample_proxy_data
    ):
        """Senaryo 3: Ban threshold asildiktan sonra proxy havuzdan kaldiriliyor."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = sample_proxy_data
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com",
            api_key="test-key",
            ban_threshold=3,
        )

        proxy_url = "http://192.168.1.1:8080"
        middleware.proxy_pool[proxy_url] = sample_proxy_data["proxies"][0]

        # 3 kez hata ver
        for _ in range(3):
            middleware._handle_proxy_failure(proxy_url)

        # Proxy kara listede ve havuzdan kaldirilmis olmali
        assert proxy_url in middleware.blacklisted_proxies
        assert proxy_url not in middleware.proxy_pool
        assert middleware.stats["proxy_devre_disi"] == 1

    @patch("middlewares.proxy_middleware.requests.get")
    def test_havuz_kritik_seviyede_otomatik_yenileniyor(
        self, mock_requests_get, sample_proxy_data
    ):
        """Senaryo 5: Havuz < min_pool_size oldugunda otomatik yenileniyor."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = sample_proxy_data
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com",
            api_key="test-key",
            min_pool_size=5,
            ban_threshold=1,
        )

        # Baslangicta 5 proxy yukle
        middleware._refresh_proxy_pool()
        assert len(middleware.proxy_pool) == 5
        assert middleware.stats["havuz_yenileme"] == 1

        # Havuzdaki tum proxy'leri kara listeye al
        for proxy_url in list(middleware.proxy_pool.keys()):
            middleware._handle_proxy_failure(proxy_url)

        # Havuz yenilenmis olmali (auto-refresh tetiklendi)
        assert middleware.stats["havuz_yenileme"] > 1

    def test_process_exception_proxy_hatasi_olarak_isler(
        self, mock_request, mock_spider, sample_proxy_data
    ):
        """process_exception metodunda proxy hata sayaci artiyor."""
        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com",
            api_key="test-key",
        )

        proxy_url = "http://192.168.1.1:8080"
        middleware.proxy_pool[proxy_url] = sample_proxy_data["proxies"][0]
        mock_request.meta["_proxy_url"] = proxy_url

        # Exception isle
        exception = Exception("Connection timeout")
        middleware.process_exception(mock_request, exception, mock_spider)

        # Hata sayaci artmis olmali
        assert middleware.failure_counts[proxy_url] == 1
        assert middleware.stats["basarisiz_istek"] == 1


class TestStatistics:
    """Istatistik toplama testleri."""

    @patch("middlewares.proxy_middleware.requests.get")
    def test_istatistikler_dogru_toplaniyor(
        self,
        mock_requests_get,
        sample_proxy_data,
        mock_request,
        mock_response_200,
        mock_response_403,
        mock_spider,
    ):
        """Senaryo 7: Tum istatistikler dogru bir sekilde tutuluyor."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = sample_proxy_data
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com",
            api_key="test-key",
        )
        middleware._refresh_proxy_pool()

        # 3 basarili istek
        for _ in range(3):
            req = Request(url="https://example.com/test")
            proxy_url = middleware._get_random_proxy()
            req.meta["_proxy_url"] = proxy_url
            middleware.process_request(req, mock_spider)
            middleware.process_response(req, mock_response_200, mock_spider)

        # 2 basarisiz istek (ban)
        for _ in range(2):
            req = Request(url="https://example.com/test")
            proxy_url = middleware._get_random_proxy()
            req.meta["_proxy_url"] = proxy_url
            middleware.process_request(req, mock_spider)
            middleware.process_response(req, mock_response_403, mock_spider)

        # Istatistikleri dogrula
        assert middleware.stats["toplam_istek"] == 5
        assert middleware.stats["basarili_istek"] == 3
        assert middleware.stats["ban_tespit"] == 2
        assert middleware.stats["havuz_yenileme"] == 1

        # get_stats metodunu test et
        stats = middleware.get_stats()
        assert stats["toplam_istek"] == 5
        assert stats["basarili_istek"] == 3
        assert stats["aktif_proxy"] == len(middleware.proxy_pool)
        assert stats["kara_liste"] == len(middleware.blacklisted_proxies)


class TestHelperMethods:
    """Yardimci method testleri."""

    def test_format_proxy_url_http(self):
        """HTTP proxy URL formatlamasi dogru calisiyor."""
        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com", api_key="test-key"
        )

        proxy_data = {"ip": "1.2.3.4", "port": 8080, "protocol": "http"}
        url = middleware._format_proxy_url(proxy_data)

        assert url == "http://1.2.3.4:8080"

    def test_format_proxy_url_socks5(self):
        """SOCKS5 proxy URL formatlamasi dogru calisiyor."""
        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com", api_key="test-key"
        )

        proxy_data = {"ip": "5.6.7.8", "port": 1080, "protocol": "socks5"}
        url = middleware._format_proxy_url(proxy_data)

        assert url == "socks5://5.6.7.8:1080"

    def test_format_proxy_url_eksik_veri(self):
        """Eksik veri durumunda None donuyor."""
        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com", api_key="test-key"
        )

        proxy_data = {"ip": "1.2.3.4"}  # port eksik
        url = middleware._format_proxy_url(proxy_data)

        assert url is None

    def test_get_random_proxy_kara_liste_haric(self, sample_proxy_data):
        """_get_random_proxy kara listedeki proxy'leri secmiyor."""
        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com", api_key="test-key"
        )

        # Havuza 3 proxy ekle
        middleware.proxy_pool = {
            "http://192.168.1.1:8080": sample_proxy_data["proxies"][0],
            "http://192.168.1.2:3128": sample_proxy_data["proxies"][1],
            "http://192.168.1.3:8888": sample_proxy_data["proxies"][2],
        }

        # Birini kara listeye al
        middleware.blacklisted_proxies.add("http://192.168.1.2:3128")

        # 10 kez rastgele proxy sec - hicbiri kara listeli olmamali
        for _ in range(10):
            proxy_url = middleware._get_random_proxy()
            assert proxy_url != "http://192.168.1.2:3128"
            assert proxy_url in [
                "http://192.168.1.1:8080",
                "http://192.168.1.3:8888",
            ]

    def test_get_random_proxy_havuz_bos(self):
        """Havuz bossa None donuyor."""
        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com", api_key="test-key"
        )

        proxy_url = middleware._get_random_proxy()
        assert proxy_url is None

    @patch("middlewares.proxy_middleware.time.sleep")
    def test_rate_limit_wait(self, mock_sleep):
        """API rate limit beklemesi dogru calisiyor."""
        middleware = SkyStoneProxyMiddleware(
            api_url="http://test.com", api_key="test-key"
        )

        # Ilk cagrida bekleme yok
        middleware._rate_limit_wait()
        assert mock_sleep.call_count == 0

        # Ardindan hemen cagrida bekleme var
        middleware._last_api_call = middleware._last_api_call - 0.5  # 0.5s once
        middleware._rate_limit_wait()
        assert mock_sleep.call_count == 1
