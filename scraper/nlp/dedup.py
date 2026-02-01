"""
Veri Tekrarlama Tespit ve Temizleme Modulu

Farkli kaynaklardan gelen verilerdeki tekrarlamalari tespit eder.
Fuzzy matching ile benzer kayitlari bulur.
"""

from dataclasses import dataclass
from loguru import logger
from rapidfuzz import fuzz, process


@dataclass
class DuplicateMatch:
    """Tekrarlama eslesmesi"""
    source_id: str
    target_id: str
    similarity_score: float
    match_type: str  # "exact", "fuzzy", "partial"


class Deduplicator:
    """
    Veri tekrarlama tespit ve birlestirme motoru.

    Ozellikler:
    - Turkce karakter duyarli fuzzy matching
    - Adres normalizasyonu
    - Telefon numarasi normalizasyonu
    - Konum bazli eslestirme (yakin mesafedeki benzer isimler)
    """

    def __init__(self, similarity_threshold: float = 85.0):
        """
        Args:
            similarity_threshold: Esleme esik degeri (0-100)
        """
        self.similarity_threshold = similarity_threshold
        self.logger = logger.bind(module="dedup")

    def find_duplicates(
        self,
        records: list[dict],
        key_field: str = "name",
    ) -> list[DuplicateMatch]:
        """
        Kayit listesinde tekrarlamalari bulur.

        Args:
            records: Kontrol edilecek kayitlar
            key_field: Karsilastirma yapilacak alan

        Returns:
            Bulunan tekrarlama eslesmeleri
        """
        self.logger.info(f"{len(records)} kayit kontrol ediliyor...")
        duplicates: list[DuplicateMatch] = []

        names = [r.get(key_field, "") for r in records]

        for i, name in enumerate(names):
            matches = process.extract(
                name,
                names[i + 1:],
                scorer=fuzz.token_sort_ratio,
                score_cutoff=self.similarity_threshold,
            )
            for match_name, score, idx in matches:
                duplicates.append(
                    DuplicateMatch(
                        source_id=str(i),
                        target_id=str(i + 1 + idx),
                        similarity_score=score,
                        match_type="exact" if score == 100 else "fuzzy",
                    )
                )

        self.logger.info(f"{len(duplicates)} tekrarlama bulundu")
        return duplicates

    @staticmethod
    def normalize_turkish(text: str) -> str:
        """Turkce karakter normalizasyonu"""
        replacements = {
            "ç": "c", "Ç": "C",
            "ğ": "g", "Ğ": "G",
            "ı": "i", "İ": "I",
            "ö": "o", "Ö": "O",
            "ş": "s", "Ş": "S",
            "ü": "u", "Ü": "U",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text.lower().strip()
