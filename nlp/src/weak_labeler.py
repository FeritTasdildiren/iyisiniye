"""
weak_labeler.py - Sentiment analizi icin zayif etiketleme modulu.

Google Maps restoran yorumlarini rating ve metin bazli kurallarla
etiketleyerek NLP modelinin egitim datasini olusturur.

Etiket degerleri:
     1 = POZITIF
     0 = NOTR
    -1 = NEGATIF
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import pandas as pd
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

# ── Sabit kelime listeleri ──────────────────────────────────────────────

POSITIVE_KEYWORDS: list[str] = [
    "harika",
    "mukemmel",
    "muhtesem",
    "cok iyi",
    "lezzetli",
    "enfes",
    "super",
    "guzel",
    "bayildim",
    "tavsiye ederim",
    # Turkce karakter variantlari
    "mükemmel",
    "muhteşem",
    "çok iyi",
    "süper",
    "güzel",
    "bayıldım",
]

NEGATIVE_KEYWORDS: list[str] = [
    "kotu",
    "berbat",
    "rezalet",
    "igrenc",
    "boktan",
    "les",
    "zehir",
    "pisman",
    "bir daha gelmem",
    "felaket",
    # Turkce karakter variantlari
    "kötü",
    "iğrenç",
    "leş",
    "pişman",
]

# ── Default DB config ───────────────────────────────────────────────────

DEFAULT_DB_CONFIG: dict[str, str | int] = {
    "host": "localhost",
    "port": 15433,
    "user": "iyisiniye_app",
    "password": "IyS2026SecureDB",
    "dbname": "iyisiniye",
}


# ── WeakLabeler ─────────────────────────────────────────────────────────


@dataclass
class WeakLabeler:
    """Kural tabanli zayif etiketleyici.

    Rating ve metin sinyallerini birlestirerek her yoruma
    bir sentiment etiketi ve guven skoru atar.
    """

    positive_keywords: list[str] = field(default_factory=lambda: list(POSITIVE_KEYWORDS))
    negative_keywords: list[str] = field(default_factory=lambda: list(NEGATIVE_KEYWORDS))

    # ── Etiketleme metodlari ────────────────────────────────────────

    @staticmethod
    def label_from_rating(rating: float) -> int:
        """Yildiz puanini sentiment etiketine donusturur.

        Args:
            rating: 1-5 arasi yildiz puani.

        Returns:
            1 (pozitif), 0 (notr) veya -1 (negatif).
        """
        if rating >= 4:
            return 1
        if rating <= 2:
            return -1
        return 0

    def label_from_text(self, text: str) -> int:
        """Metin icerigini basit kelime eslestirmesiyle etiketler.

        Args:
            text: Yorum metni.

        Returns:
            1 (pozitif), 0 (notr) veya -1 (negatif).
        """
        normalized = text.lower().strip()

        pos_count = sum(
            1 for kw in self.positive_keywords if kw in normalized
        )
        neg_count = sum(
            1 for kw in self.negative_keywords if kw in normalized
        )

        if pos_count > neg_count:
            return 1
        if neg_count > pos_count:
            return -1
        return 0

    @staticmethod
    def confidence_score(rating_label: int, text_label: int) -> float:
        """Iki sinyal arasindaki uyuma gore guven skoru hesaplar.

        Args:
            rating_label: Rating bazli etiket.
            text_label:   Metin bazli etiket.

        Returns:
            0.9 (uyusma), 0.6 (kismen), 0.3 (cakisma).
        """
        if rating_label == text_label:
            return 0.9
        if rating_label == 0 or text_label == 0:
            return 0.6
        # Zit isaretler
        return 0.3

    def create_labeled_dataset(self, reviews: list[dict]) -> pd.DataFrame:
        """Yorum listesinden etiketli DataFrame olusturur.

        Rating etiketi onceliklidir; text etiketi destekleyici sinyal
        olarak guven skorunu etkiler.

        Args:
            reviews: Her biri ``review_id``, ``text``, ``star_rating``
                     anahtarlarina sahip sozluk listesi.

        Returns:
            ``review_id``, ``text``, ``star_rating``, ``weak_label``,
            ``confidence`` sutunlarina sahip DataFrame.
        """
        rows: list[dict] = []

        for rev in reviews:
            review_id = rev["review_id"]
            text = rev.get("text") or ""
            star_rating = float(rev["star_rating"])

            rating_lbl = self.label_from_rating(star_rating)
            text_lbl = self.label_from_text(text)
            conf = self.confidence_score(rating_lbl, text_lbl)

            # Nihai etiket: rating oncelikli
            weak_label = rating_lbl

            rows.append(
                {
                    "review_id": review_id,
                    "text": text,
                    "star_rating": star_rating,
                    "weak_label": weak_label,
                    "confidence": conf,
                }
            )

        df = pd.DataFrame(rows)
        logger.info(
            "Etiketli dataset olusturuldu: %d yorum, dagilim: %s",
            len(df),
            df["weak_label"].value_counts().to_dict() if not df.empty else {},
        )
        return df


# ── DB erisim ───────────────────────────────────────────────────────────


def fetch_reviews(
    db_config: dict | None = None,
    limit: int = 1000,
) -> list[dict]:
    """PostgreSQL'den yorumlari ceker.

    SSH tuneli aktif oldugunda ``localhost:15433`` uzerinden baglanir.

    Args:
        db_config: Baglanti parametreleri. ``None`` ise default config kullanilir.
        limit:     Cekilecek maksimum yorum sayisi.

    Returns:
        Her biri ``review_id``, ``text``, ``star_rating`` icerir.
    """
    config = db_config or DEFAULT_DB_CONFIG

    query = """
        SELECT id   AS review_id,
               text,
               rating AS star_rating
        FROM   reviews
        WHERE  text IS NOT NULL
          AND  text != ''
        LIMIT  %s
    """

    try:
        logger.info(
            "DB baglantisi kuruluyor: %s:%s/%s",
            config["host"],
            config["port"],
            config["dbname"],
        )
        conn = psycopg2.connect(
            host=config["host"],
            port=int(config["port"]),
            user=config["user"],
            password=config["password"],
            dbname=config["dbname"],
        )
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, (limit,))
                rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        logger.info("DB'den %d yorum cekildi.", len(rows))
        return rows

    except psycopg2.Error as exc:
        logger.error("DB hatasi: %s", exc)
        raise


# ── CLI giris noktasi ───────────────────────────────────────────────────


def main() -> None:
    """Ornek kullanim: statik veriyle etiketleme gosterimi."""

    sample_reviews: list[dict] = [
        {
            "review_id": 1,
            "text": "Harika bir mekan, yemekler cok lezzetli!",
            "star_rating": 5,
        },
        {
            "review_id": 2,
            "text": "Fiyatlar normal, servis yavasti biraz.",
            "star_rating": 3,
        },
        {
            "review_id": 3,
            "text": "Berbat bir deneyim, bir daha gelmem.",
            "star_rating": 1,
        },
        {
            "review_id": 4,
            "text": "Guzel mekan ama porsiyon kucuk.",
            "star_rating": 4,
        },
        {
            "review_id": 5,
            "text": "Rezalet, yemek soguk geldi.",
            "star_rating": 2,
        },
    ]

    labeler = WeakLabeler()
    df = labeler.create_labeled_dataset(sample_reviews)

    print("\n=== Zayif Etiketleme Sonuclari ===\n")
    print(df.to_string(index=False))
    print(f"\nToplam: {len(df)} yorum")
    print(f"Dagilim:\n{df['weak_label'].value_counts().to_string()}")
    print(f"Ortalama guven: {df['confidence'].mean():.2f}")


if __name__ == "__main__":
    main()
