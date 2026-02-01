"""
Yemek Bilgisi Cikarici (Named Entity Recognition)

Yorum metinlerinden yemek isimlerini, ozellikleri ve
fiyat bilgilerini cikarir.

Kullanilan modeller:
- Turkce BERT modeli (dbmdz/bert-base-turkish-cased)
- Ozel egitilmis NER modeli (sonra eklenecek)
"""

from dataclasses import dataclass
from loguru import logger


@dataclass
class ExtractedDish:
    """Metinden cikarilan yemek bilgisi"""
    name: str
    confidence: float
    mentions: int = 1
    positive_context: bool = False
    price_mentioned: float | None = None


class YemekExtractor:
    """
    Turkce metinlerden yemek adlarini ve ozelliklerini cikarir.

    Strateji:
    1. Bilinen yemek listesiyle eslestirme (hizli, kesin)
    2. NER modeli ile bilinmeyen yemekleri tespit (yavas, kesfedici)
    3. Baglamsal analiz (yemegin begeni durumu)
    """

    def __init__(self, model_name: str = "dbmdz/bert-base-turkish-cased"):
        self.model_name = model_name
        self.logger = logger.bind(module="yemek_extractor")
        # TODO: Model yukleme
        # TODO: Bilinen yemek sozlugu yukleme

    def extract_dishes(self, text: str) -> list[ExtractedDish]:
        """
        Metinden yemek isimlerini cikarir.

        Args:
            text: Analiz edilecek yorum metni

        Returns:
            Bulunan yemek bilgileri listesi
        """
        self.logger.debug(f"Yemek cikarma basliyor: {text[:50]}...")
        # TODO: Implementasyon
        return []

    def extract_price(self, text: str) -> float | None:
        """Metinden fiyat bilgisi cikarir (TL cinsinden)"""
        # TODO: Regex + NLP ile fiyat tespiti
        return None
