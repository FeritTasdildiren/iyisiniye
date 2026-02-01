"""
Platformlar Arasi Restoran Eslestirme Modulu

Farkli platformlardan (Google Maps, Yemeksepeti, Trendyol Yemek)
gelen restoran kayitlarini birbirleriyle eslestirir.

Eslestirme kriterleri:
1. Isim benzerlik skoru (fuzzy matching)
2. Adres benzerlik skoru
3. Konum yakinligi (koordinat mesafesi)
4. Telefon numarasi eslesmesi
"""

from dataclasses import dataclass
from loguru import logger
from rapidfuzz import fuzz


@dataclass
class PlatformMatch:
    """Platformlar arasi eslestirme sonucu"""
    source_platform: str
    source_id: str
    target_platform: str
    target_id: str
    name_similarity: float
    address_similarity: float
    distance_km: float | None
    phone_match: bool
    overall_confidence: float


class CrossPlatformMatcher:
    """
    Farkli platformlardaki ayni restorani tespit eder.

    Algoritma:
    1. Isim bazli aday filtreleme (hizli - fuzzy threshold)
    2. Adaylar icin detayli karsilastirma (adres, konum, telefon)
    3. Agirlikli skor hesaplama
    4. Esik degeri uzerindeki eslesmeleri onaylama
    """

    # Agirliklar
    NAME_WEIGHT = 0.35
    ADDRESS_WEIGHT = 0.30
    LOCATION_WEIGHT = 0.25
    PHONE_WEIGHT = 0.10

    # Esik degerleri
    NAME_THRESHOLD = 75.0
    OVERALL_THRESHOLD = 70.0
    MAX_DISTANCE_KM = 0.5  # 500 metre

    def __init__(self):
        self.logger = logger.bind(module="cross_platform")

    def match_restaurants(
        self,
        source_restaurants: list[dict],
        target_restaurants: list[dict],
        source_platform: str,
        target_platform: str,
    ) -> list[PlatformMatch]:
        """
        Iki platform arasindaki restoranlari eslestirir.

        Args:
            source_restaurants: Kaynak platform restoranlari
            target_restaurants: Hedef platform restoranlari
            source_platform: Kaynak platform adi
            target_platform: Hedef platform adi

        Returns:
            Eslestirme sonuclari
        """
        self.logger.info(
            f"Eslestirme basliyor: {source_platform} ({len(source_restaurants)}) "
            f"<-> {target_platform} ({len(target_restaurants)})"
        )
        matches: list[PlatformMatch] = []

        for source in source_restaurants:
            best_match: PlatformMatch | None = None
            best_score = 0.0

            for target in target_restaurants:
                score = self._calculate_similarity(source, target)
                if score > best_score and score >= self.OVERALL_THRESHOLD:
                    best_score = score
                    best_match = PlatformMatch(
                        source_platform=source_platform,
                        source_id=source.get("source_id", ""),
                        target_platform=target_platform,
                        target_id=target.get("source_id", ""),
                        name_similarity=fuzz.token_sort_ratio(
                            source.get("name", ""), target.get("name", "")
                        ),
                        address_similarity=fuzz.token_sort_ratio(
                            source.get("address", ""), target.get("address", "")
                        ),
                        distance_km=None,  # TODO: Hesapla
                        phone_match=source.get("phone") == target.get("phone"),
                        overall_confidence=score,
                    )

            if best_match:
                matches.append(best_match)

        self.logger.info(f"{len(matches)} eslestirme bulundu")
        return matches

    def _calculate_similarity(self, source: dict, target: dict) -> float:
        """Iki restoran arasindaki benzerlik skorunu hesaplar"""
        name_score = fuzz.token_sort_ratio(
            source.get("name", ""), target.get("name", "")
        )

        if name_score < self.NAME_THRESHOLD:
            return 0.0

        address_score = fuzz.token_sort_ratio(
            source.get("address", ""), target.get("address", "")
        )

        # TODO: Konum mesafesi hesabi
        location_score = 50.0

        phone_score = 100.0 if (
            source.get("phone") and source.get("phone") == target.get("phone")
        ) else 0.0

        return (
            name_score * self.NAME_WEIGHT
            + address_score * self.ADDRESS_WEIGHT
            + location_score * self.LOCATION_WEIGHT
            + phone_score * self.PHONE_WEIGHT
        )
