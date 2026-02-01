"""
Pytest Fixture'lari

Tum testlerde kullanilacak ortak fixture'lar burada tanimlanir.
"""

import pytest
from scrapy.http import Request, Response, TextResponse


def pytest_configure(config):
    """Pytest baslamadan once Scrapy reaktor kurar."""
    import scrapy
    from twisted.internet import default

    # Scrapy icin reaktor kur
    default.install()


@pytest.fixture
def mock_spider():
    """Mock Scrapy Spider fixture'i."""
    from scrapy import Spider

    spider = Spider(name="test_spider")
    return spider


@pytest.fixture
def mock_request():
    """Mock Scrapy Request fixture'i."""
    return Request(url="https://example.com/test")


@pytest.fixture
def mock_response_200(mock_request):
    """Basarili HTTP 200 yanit fixture'i."""
    return TextResponse(
        url="https://example.com/test",
        status=200,
        body=b"<html><body>Test Content</body></html>",
        request=mock_request,
        headers={b"Content-Type": b"text/html"},
    )


@pytest.fixture
def mock_response_403(mock_request):
    """Ban HTTP 403 yanit fixture'i."""
    return TextResponse(
        url="https://example.com/test",
        status=403,
        body=b"<html><body>Access Denied</body></html>",
        request=mock_request,
        headers={b"Content-Type": b"text/html"},
    )


@pytest.fixture
def mock_response_429(mock_request):
    """Rate limit HTTP 429 yanit fixture'i."""
    return TextResponse(
        url="https://example.com/test",
        status=429,
        body=b"<html><body>Too Many Requests</body></html>",
        request=mock_request,
        headers={b"Content-Type": b"text/html"},
    )


@pytest.fixture
def mock_response_captcha(mock_request):
    """CAPTCHA iceren HTTP 200 yanit fixture'i."""
    return TextResponse(
        url="https://example.com/test",
        status=200,
        body=b"<html><body><div class='g-recaptcha'>CAPTCHA Challenge</div></body></html>",
        request=mock_request,
        headers={b"Content-Type": b"text/html"},
    )


@pytest.fixture
def mock_crawler():
    """Mock Scrapy Crawler fixture'i."""
    from scrapy.utils.test import get_crawler

    settings = {
        "PROXY_API_URL": "http://test-api.example.com",
        "PROXY_API_KEY": "test-api-key-12345",
        "PROXY_MIN_POOL_SIZE": 5,
        "PROXY_REFRESH_INTERVAL": 300,
        "PROXY_BAN_THRESHOLD": 3,
    }
    return get_crawler(spidercls=None, settings_dict=settings)


@pytest.fixture
def sample_proxy_data():
    """Ornek proxy veri yapisi fixture'i."""
    return {
        "success": True,
        "proxies": [
            {
                "ip": "192.168.1.1",
                "port": 8080,
                "protocol": "http",
                "quality_score": 95.5,
                "success_rate": 98.2,
                "tier": "high",
            },
            {
                "ip": "192.168.1.2",
                "port": 3128,
                "protocol": "http",
                "quality_score": 92.0,
                "success_rate": 96.5,
                "tier": "high",
            },
            {
                "ip": "192.168.1.3",
                "port": 8888,
                "protocol": "http",
                "quality_score": 85.0,
                "success_rate": 90.1,
                "tier": "medium",
            },
            {
                "ip": "192.168.1.4",
                "port": 9999,
                "protocol": "socks5",
                "quality_score": 80.5,
                "success_rate": 88.0,
                "tier": "medium",
            },
            {
                "ip": "192.168.1.5",
                "port": 1080,
                "protocol": "http",
                "quality_score": 78.0,
                "success_rate": 85.5,
                "tier": "medium",
            },
        ],
    }
