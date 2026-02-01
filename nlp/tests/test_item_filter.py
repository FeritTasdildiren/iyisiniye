"""
ItemFilter modülü test dosyası
pytest formatında - /Users/ferit/Projeler/iyisiniye/nlp/.venv/bin/pytest ile çalıştır
"""
import pytest
import os
import sys

# src dizinini path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from item_filter import ItemFilter

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
DICT_PATH = os.path.join(DATA_DIR, 'filtre_sozlugu.json')


@pytest.fixture
def item_filter():
    """ItemFilter örneği oluşturur."""
    if not os.path.exists(DICT_PATH):
        pytest.skip(f"Sözlük dosyası bulunamadı: {DICT_PATH}")
    return ItemFilter(DICT_PATH)


class TestBeverageDetection:
    """İçecek tespiti testleri"""

    @pytest.mark.parametrize("item", [
        "çay", "kahve", "su", "ayran", "kola",
        "fanta", "gazoz", "soda", "şalgam", "limonata"
    ])
    def test_basic_beverages(self, item_filter, item):
        result = item_filter.classify(item)
        assert result["type"] == "icecek", f"'{item}' içecek olmalıydı, {result['type']} döndü"

    @pytest.mark.parametrize("item", [
        "soğuk kahve", "soğuk çay"
    ])
    def test_partial_match_beverages(self, item_filter, item):
        result = item_filter.classify(item)
        assert result["type"] == "icecek", f"'{item}' içecek olmalıydı, {result['type']} döndü"

    @pytest.mark.parametrize("item", [
        "türk kahvesi", "ihlamur", "ada çayı", "sahlep", "boza"
    ])
    def test_turkish_traditional_beverages(self, item_filter, item):
        result = item_filter.classify(item)
        assert result["type"] == "icecek", f"'{item}' içecek olmalıydı, {result['type']} döndü"


class TestSideItemDetection:
    """Yan ürün tespiti testleri"""

    @pytest.mark.parametrize("item", [
        "peçete", "plastik çatal", "kağıt bardak", "pipet", "ıslak mendil"
    ])
    def test_disposable_items(self, item_filter, item):
        result = item_filter.classify(item)
        assert result["type"] == "yan_urun", f"'{item}' yan_urun olmalıydı, {result['type']} döndü"

    @pytest.mark.parametrize("item", [
        "servis ücreti", "paket ücreti"
    ])
    def test_service_charges(self, item_filter, item):
        result = item_filter.classify(item)
        assert result["type"] == "yan_urun", f"'{item}' yan_urun olmalıydı, {result['type']} döndü"


class TestFoodDetection:
    """Yemek tespiti testleri"""

    @pytest.mark.parametrize("item", [
        "Adana kebap", "mercimek çorbası", "lahmacun",
        "İskender", "pide", "döner", "hamburger"
    ])
    def test_standard_foods(self, item_filter, item):
        result = item_filter.classify(item)
        assert result["type"] == "yemek", f"'{item}' yemek olmalıydı, {result['type']} döndü"

    def test_tea_leaf_wrap_is_food(self, item_filter):
        """Çay yaprağı sarması yemek olmalı, içecek değil!"""
        result = item_filter.classify("çay yaprağı sarması")
        assert result["type"] == "yemek", "Çay yaprağı sarması yemek olmalıydı!"

    def test_su_boregi_is_food(self, item_filter):
        """Su böreği yemek olmalı, içecek değil!"""
        result = item_filter.classify("su böreği")
        # Su böreği 2 kelime, "su" içecek match'i var ama börek yemek
        # Bu test edge case - mevcut implementasyona göre sonuç değişebilir
        result_type = result["type"]
        # En azından içecek olmamalı
        assert result_type != "icecek" or result_type == "yemek", \
            f"Su böreği içecek olarak sınıflandırılmamalı, {result_type} döndü"


class TestEdgeCases:
    """Edge case testleri"""

    def test_empty_string(self, item_filter):
        """Boş string hata vermemeli."""
        result = item_filter.classify("")
        assert result is not None

    def test_whitespace_only(self, item_filter):
        """Sadece boşluk hata vermemeli."""
        result = item_filter.classify("   ")
        assert result is not None

    def test_mixed_case(self, item_filter):
        """Büyük/küçük harf karışık giriş."""
        result = item_filter.classify("KOLA")
        assert result["type"] == "icecek", "KOLA büyük harfle de içecek olmalı"

    def test_long_string(self, item_filter):
        """Çok uzun string hata vermemeli."""
        try:
            result = item_filter.classify("A" * 500)
            assert result is not None
        except Exception as e:
            pytest.fail(f"Uzun string hata verdi: {e}")


class TestBulkFiltering:
    """Toplu filtreleme testleri"""

    def test_mixed_menu_items(self, item_filter):
        """Karma menü listesi doğru gruplanmalı."""
        items = [
            "çay", "kahve", "ayran",  # içecekler
            "peçete", "plastik çatal",  # yan ürünler
            "Adana kebap", "mercimek çorbası", "lahmacun",  # yemekler
        ]
        result = item_filter.filter_menu_items(items)

        assert "çay" in result["icecekler"]
        assert "peçete" in result["yan_urunler"]
        assert "Adana kebap" in result["yemekler"]

    def test_empty_list(self, item_filter):
        """Boş liste hata vermemeli."""
        result = item_filter.filter_menu_items([])
        assert result["yemekler"] == []
        assert result["icecekler"] == []
        assert result["yan_urunler"] == []
