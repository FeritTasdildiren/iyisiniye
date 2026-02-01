"""
food_scorer.py - Yemek bazli puanlama ve sıralama modulu.

Google Maps restoran yorumlarindan elde edilen sentiment verilerini
kullanarak her yemege 1-10 arasi puan hesaplar. Agirlikli ortalama,
star rating normalizasyonu ve guven skoru tabanli skor uretir.

Puanlama formulu:
    sentiment_val = POSITIVE(+1) | NEUTRAL(0) | NEGATIVE(-1)
    weighted_sentiment = sum(val * confidence) / sum(confidence)
    star_component = (star_rating - 3) / 2  # 1-5 → -1..+1
    combined = weighted_sentiment * 0.70 + star_component * 0.30
    score_1_10 = (combined + 1) / 2 * 9 + 1
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)


# ── ScoreNormalizer ──────────────────────────────────────────────────────


class ScoreNormalizer:
    """Sentiment degerlerini sayisal skorlara donusturmek icin yardimci sinif."""

    SENTIMENT_MAP: dict[str, float] = {
        "POSITIVE": 1.0,
        "NEUTRAL": 0.0,
        "NEGATIVE": -1.0,
    }

    @staticmethod
    def sentiment_to_numeric(label: str) -> float:
        """Sentiment etiketini sayisal degere donusturur.

        Args:
            label: ``POSITIVE``, ``NEUTRAL`` veya ``NEGATIVE``.

        Returns:
            +1.0, 0.0 veya -1.0.

        Raises:
            ValueError: Gecersiz etiket verildiginde.
        """
        val = ScoreNormalizer.SENTIMENT_MAP.get(label.upper())
        if val is None:
            raise ValueError(f"Gecersiz sentiment etiketi: {label}")
        return val

    @staticmethod
    def normalize_star_rating(rating: float) -> float:
        """Yildiz puanini -1..+1 arasina normalize eder.

        1 → -1.0, 3 → 0.0, 5 → +1.0

        Args:
            rating: 1-5 arasi yildiz puani.

        Returns:
            -1.0 ile +1.0 arasi float.
        """
        clamped = max(1.0, min(5.0, float(rating)))
        return (clamped - 3.0) / 2.0

    @staticmethod
    def scale_to_10(value: float) -> float:
        """Degeri -1..+1 arasindan 1..10 arasina olcekler.

        -1.0 → 1.0, 0.0 → 5.5, +1.0 → 10.0

        Args:
            value: -1.0 ile +1.0 arasi deger.

        Returns:
            1.0 ile 10.0 arasi float.
        """
        clamped = max(-1.0, min(1.0, value))
        return (clamped + 1.0) / 2.0 * 9.0 + 1.0

    @staticmethod
    def weighted_average(values: list[float], weights: list[float]) -> float:
        """Agirlikli ortalama hesaplar.

        Args:
            values:  Deger listesi.
            weights: Agirlik listesi (values ile ayni uzunlukta).

        Returns:
            Agirlikli ortalama. Agirlik toplami 0 ise 0.0 doner.

        Raises:
            ValueError: Listeler farkli uzunlukta oldugunda.
        """
        if len(values) != len(weights):
            raise ValueError(
                f"values ({len(values)}) ve weights ({len(weights)}) uzunluklari esit olmali"
            )
        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0
        return sum(v * w for v, w in zip(values, weights)) / total_weight


# ── FoodScorer ───────────────────────────────────────────────────────────


class FoodScorer:
    """Yemek bazli puanlama ve siralama motoru.

    Her yemek icin yorumlardaki sentiment ve star_rating verilerini
    birlestirerek 1-10 arasi puan hesaplar.

    Args:
        min_reviews:       Yeterli veri icin minimum yorum sayisi esigi.
        confidence_threshold: Hesaba katilacak minimum guven skoru.
        star_weight:       Star rating'in toplam skordaki agirligi (0-1).
    """

    def __init__(
        self,
        min_reviews: int = 3,
        confidence_threshold: float = 0.5,
        star_weight: float = 0.30,
    ) -> None:
        self.min_reviews = min_reviews
        self.confidence_threshold = confidence_threshold
        self.star_weight = star_weight
        self.sentiment_weight = 1.0 - star_weight
        self.normalizer = ScoreNormalizer()

        logger.info(
            "FoodScorer baslatildi: min_reviews=%d, conf_threshold=%.2f, "
            "star_weight=%.2f, sentiment_weight=%.2f",
            min_reviews,
            confidence_threshold,
            star_weight,
            self.sentiment_weight,
        )

    # ── Tekil yemek puanlama ─────────────────────────────────────────

    def calculate_food_score(self, food_sentiments: list[dict[str, Any]]) -> dict[str, Any]:
        """Tek bir yemek icin sentiment verilerinden puan hesaplar.

        Agirlikli ortalama yontemiyle sentiment ve star_rating
        birlestirilir, 1-10 arasina olceklenir.

        Args:
            food_sentiments: Her biri ``sentiment`` (str), ``score`` (float),
                ``confidence`` (float), ``star_rating`` (float) iceren sozluk listesi.

        Returns:
            ``score_1_10``, ``confidence``, ``sentiment_distribution``,
            ``review_count``, ``enough_data`` iceren sozluk.
        """
        if not food_sentiments:
            logger.warning("Bos sentiment listesi, varsayilan skor dondurulecek")
            return {
                "score_1_10": 5.5,
                "confidence": 0.0,
                "sentiment_distribution": {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0},
                "review_count": 0,
                "enough_data": False,
            }

        sentiment_values: list[float] = []
        sentiment_weights: list[float] = []
        star_values: list[float] = []
        star_weights: list[float] = []
        distribution: dict[str, int] = {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0}
        valid_confidences: list[float] = []

        for entry in food_sentiments:
            sentiment_label = entry.get("sentiment")
            confidence = float(entry.get("confidence", 0.0) or 0.0)
            star_rating = entry.get("star_rating")

            if sentiment_label is None:
                logger.debug("sentiment=None olan kayit atlanacak")
                continue

            # Sentiment dagilimini say
            label_upper = sentiment_label.upper()
            if label_upper in distribution:
                distribution[label_upper] += 1

            # Dusuk guvenli kayitlari hesaba katma
            if confidence < self.confidence_threshold:
                logger.debug(
                    "Dusuk guven (%.2f < %.2f), kayit atlanacak",
                    confidence,
                    self.confidence_threshold,
                )
                continue

            try:
                num_val = ScoreNormalizer.sentiment_to_numeric(label_upper)
            except ValueError:
                logger.warning("Bilinmeyen sentiment etiketi: %s", sentiment_label)
                continue

            sentiment_values.append(num_val)
            sentiment_weights.append(confidence)
            valid_confidences.append(confidence)

            if star_rating is not None:
                norm_star = ScoreNormalizer.normalize_star_rating(float(star_rating))
                star_values.append(norm_star)
                star_weights.append(confidence)

        review_count = sum(distribution.values())
        enough_data = review_count >= self.min_reviews

        # Yeterli veri yoksa
        if not sentiment_values:
            avg_confidence = 0.0
            combined_score = 0.0
        else:
            weighted_sentiment = ScoreNormalizer.weighted_average(
                sentiment_values, sentiment_weights
            )

            if star_values:
                weighted_star = ScoreNormalizer.weighted_average(star_values, star_weights)
            else:
                weighted_star = 0.0

            combined_score = (
                weighted_sentiment * self.sentiment_weight
                + weighted_star * self.star_weight
            )
            avg_confidence = sum(valid_confidences) / len(valid_confidences)

        score_1_10 = ScoreNormalizer.scale_to_10(combined_score)

        # Yeterli veri yoksa guven skorunu dusur
        if not enough_data and avg_confidence > 0:
            data_penalty = review_count / self.min_reviews
            avg_confidence = avg_confidence * data_penalty

        return {
            "score_1_10": round(score_1_10, 2),
            "confidence": round(avg_confidence, 4),
            "sentiment_distribution": distribution,
            "review_count": review_count,
            "enough_data": enough_data,
        }

    # ── Restoran geneli yemek puanlama ───────────────────────────────

    def calculate_restaurant_food_scores(
        self,
        reviews_with_foods: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Birden fazla yorumdaki tum yemekler icin puan hesaplar.

        Her yorum ``food_sentiments`` listesi icerir.
        Yemek isimleri normalize edilerek (lowercase) gruplanir.

        Args:
            reviews_with_foods: Her biri ``food_sentiments`` anahtarli sozluk.
                ``food_sentiments`` icerisinde ``food`` (str), ``sentiment`` (str),
                ``score`` (float), ``confidence`` (float) ve ``star_rating`` (float) bulunur.

        Returns:
            ``{yemek_adi: {score_1_10, confidence, review_count, sentiment_distribution, enough_data}}``
        """
        food_data: dict[str, list[dict[str, Any]]] = {}

        for review in reviews_with_foods:
            food_sentiments = review.get("food_sentiments", [])
            star_rating = review.get("star_rating")

            for fs in food_sentiments:
                food_name = fs.get("food", "").strip().lower()
                if not food_name:
                    continue

                entry = {
                    "sentiment": fs.get("sentiment"),
                    "score": fs.get("score", 0.0),
                    "confidence": fs.get("confidence", 0.0),
                    "star_rating": fs.get("star_rating", star_rating),
                }
                food_data.setdefault(food_name, []).append(entry)

        logger.info(
            "Toplam %d farkli yemek bulundu, puan hesaplaniyor...",
            len(food_data),
        )

        results: dict[str, dict[str, Any]] = {}
        for food_name, sentiments in food_data.items():
            results[food_name] = self.calculate_food_score(sentiments)

        return results

    # ── Siralama ─────────────────────────────────────────────────────

    def rank_foods(
        self,
        food_scores: dict[str, dict[str, Any]],
        min_reviews: int | None = None,
    ) -> list[dict[str, Any]]:
        """Yemekleri puana gore siralar.

        Yeterli verisi olmayanlar listenin sonuna eklenir ve
        ``enough_data=False`` ile isaretlenir.

        Args:
            food_scores: ``calculate_restaurant_food_scores`` ciktisi.
            min_reviews: Yeterli veri icin minimum yorum esigi.
                         ``None`` ise ``self.min_reviews`` kullanilir.

        Returns:
            ``rank``, ``food``, ``score``, ``confidence``,
            ``review_count``, ``enough_data`` iceren siralanmis liste.
        """
        threshold = min_reviews if min_reviews is not None else self.min_reviews

        enough: list[dict[str, Any]] = []
        insufficient: list[dict[str, Any]] = []

        for food, data in food_scores.items():
            entry = {
                "food": food,
                "score": data["score_1_10"],
                "confidence": data["confidence"],
                "review_count": data["review_count"],
                "enough_data": data["review_count"] >= threshold,
            }
            if entry["enough_data"]:
                enough.append(entry)
            else:
                insufficient.append(entry)

        # Yeterli verisi olanlar: puana gore azalan
        enough.sort(key=lambda x: x["score"], reverse=True)
        # Yetersiz verisi olanlar: yorum sayisina gore azalan
        insufficient.sort(key=lambda x: x["review_count"], reverse=True)

        ranked: list[dict[str, Any]] = []
        for i, item in enumerate(enough + insufficient, start=1):
            item["rank"] = i
            ranked.append(item)

        logger.info(
            "Siralama tamamlandi: %d yemek (%d yeterli veri, %d yetersiz)",
            len(ranked),
            len(enough),
            len(insufficient),
        )
        return ranked

    # ── Rapor ────────────────────────────────────────────────────────

    def generate_report(self, food_scores: dict[str, dict[str, Any]]) -> str:
        """Yemek puanlarindan insan okunabilir rapor uretir.

        Icerdikleri:
            - En iyi 5 yemek
            - En kotu 5 yemek
            - Genel istatistikler
            - Veri yetersizligi uyarilari

        Args:
            food_scores: ``calculate_restaurant_food_scores`` ciktisi.

        Returns:
            Formatlanmis rapor metni.
        """
        if not food_scores:
            return "Rapor uretilemiyor: hicbir yemek verisi bulunamadi."

        ranked = self.rank_foods(food_scores)
        enough_data_items = [r for r in ranked if r["enough_data"]]
        insufficient_items = [r for r in ranked if not r["enough_data"]]

        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("    YEMEK PUANLAMA RAPORU")
        lines.append("=" * 60)

        # Genel istatistikler
        all_scores = [d["score_1_10"] for d in food_scores.values() if d["review_count"] > 0]
        total_reviews = sum(d["review_count"] for d in food_scores.values())

        lines.append("")
        lines.append(f"Toplam yemek cesidi : {len(food_scores)}")
        lines.append(f"Toplam yorum sayisi : {total_reviews}")
        lines.append(f"Yeterli verili yemek: {len(enough_data_items)}")
        lines.append(f"Yetersiz verili     : {len(insufficient_items)}")
        if all_scores:
            lines.append(f"Ortalama puan       : {sum(all_scores) / len(all_scores):.1f} / 10")

        # En iyi 5
        if enough_data_items:
            lines.append("")
            lines.append("-" * 60)
            lines.append("  EN IYI 5 YEMEK")
            lines.append("-" * 60)
            for item in enough_data_items[:5]:
                lines.append(
                    f"  {item['rank']:>3}. {item['food']:<25} "
                    f"{item['score']:>5.1f}/10  "
                    f"({item['review_count']} yorum, guven: {item['confidence']:.2f})"
                )

        # En kotu 5
        if len(enough_data_items) > 1:
            worst = list(reversed(enough_data_items))[:5]
            lines.append("")
            lines.append("-" * 60)
            lines.append("  EN KOTU 5 YEMEK")
            lines.append("-" * 60)
            for item in worst:
                lines.append(
                    f"  {item['rank']:>3}. {item['food']:<25} "
                    f"{item['score']:>5.1f}/10  "
                    f"({item['review_count']} yorum, guven: {item['confidence']:.2f})"
                )

        # Veri yetersizligi uyarilari
        if insufficient_items:
            lines.append("")
            lines.append("-" * 60)
            lines.append("  VERI YETERSIZLIGI UYARILARI")
            lines.append("-" * 60)
            lines.append(
                f"  Asagidaki {len(insufficient_items)} yemek icin yeterli yorum "
                f"bulunmamaktadir (min {self.min_reviews} yorum gerekli):"
            )
            for item in insufficient_items:
                lines.append(
                    f"    - {item['food']:<25} "
                    f"{item['score']:>5.1f}/10  "
                    f"(sadece {item['review_count']} yorum)"
                )

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)


# ── CLI giris noktasi ────────────────────────────────────────────────────


def main() -> None:
    """Ornek kullanim: statik veriyle yemek puanlama gosterimi."""

    # Ornek: restoran yorumlari ve yemek bazli sentiment verileri
    sample_reviews: list[dict[str, Any]] = [
        {
            "review_id": 1,
            "star_rating": 5,
            "food_sentiments": [
                {"food": "Adana Kebap", "sentiment": "POSITIVE", "score": 0.92, "confidence": 0.88},
                {"food": "Pide", "sentiment": "POSITIVE", "score": 0.85, "confidence": 0.80},
            ],
        },
        {
            "review_id": 2,
            "star_rating": 4,
            "food_sentiments": [
                {"food": "Adana Kebap", "sentiment": "POSITIVE", "score": 0.78, "confidence": 0.75},
                {"food": "Lahmacun", "sentiment": "NEUTRAL", "score": 0.60, "confidence": 0.65},
            ],
        },
        {
            "review_id": 3,
            "star_rating": 2,
            "food_sentiments": [
                {"food": "Iskender", "sentiment": "NEGATIVE", "score": 0.88, "confidence": 0.85},
                {"food": "Corba", "sentiment": "NEGATIVE", "score": 0.72, "confidence": 0.70},
            ],
        },
        {
            "review_id": 4,
            "star_rating": 5,
            "food_sentiments": [
                {"food": "Adana Kebap", "sentiment": "POSITIVE", "score": 0.95, "confidence": 0.92},
                {"food": "Corba", "sentiment": "POSITIVE", "score": 0.80, "confidence": 0.78},
            ],
        },
        {
            "review_id": 5,
            "star_rating": 1,
            "food_sentiments": [
                {"food": "Iskender", "sentiment": "NEGATIVE", "score": 0.90, "confidence": 0.88},
                {"food": "Pilav", "sentiment": "NEGATIVE", "score": 0.65, "confidence": 0.60},
            ],
        },
        {
            "review_id": 6,
            "star_rating": 3,
            "food_sentiments": [
                {"food": "Pide", "sentiment": "NEUTRAL", "score": 0.55, "confidence": 0.52},
                {"food": "Corba", "sentiment": "NEUTRAL", "score": 0.58, "confidence": 0.55},
            ],
        },
        {
            "review_id": 7,
            "star_rating": 4,
            "food_sentiments": [
                {"food": "Pide", "sentiment": "POSITIVE", "score": 0.82, "confidence": 0.78},
            ],
        },
        {
            "review_id": 8,
            "star_rating": 5,
            "food_sentiments": [
                {"food": "Adana Kebap", "sentiment": "POSITIVE", "score": 0.90, "confidence": 0.87},
                {"food": "Iskender", "sentiment": "POSITIVE", "score": 0.75, "confidence": 0.70},
            ],
        },
    ]

    print("\n=== Yemek Bazli Puanlama Sistemi ===\n")

    scorer = FoodScorer(min_reviews=3, confidence_threshold=0.5)

    # 1. Restoran geneli puanlama
    print("--- Restoran Yemek Puanlari ---")
    food_scores = scorer.calculate_restaurant_food_scores(sample_reviews)

    for food, data in sorted(food_scores.items(), key=lambda x: x[1]["score_1_10"], reverse=True):
        status = "OK" if data["enough_data"] else "AZ VERI"
        print(
            f"  {food:<20} {data['score_1_10']:>5.1f}/10  "
            f"({data['review_count']} yorum, guven: {data['confidence']:.2f}) [{status}]"
        )

    # 2. Siralama
    print("\n--- Siralama ---")
    ranked = scorer.rank_foods(food_scores)
    for item in ranked:
        marker = " *" if not item["enough_data"] else ""
        print(
            f"  #{item['rank']:<3} {item['food']:<20} "
            f"{item['score']:>5.1f}/10  ({item['review_count']} yorum){marker}"
        )

    # 3. Tekil yemek puanlama ornegi
    print("\n--- Tekil Yemek Puanlama (Adana Kebap) ---")
    adana_sentiments = [
        {"sentiment": "POSITIVE", "score": 0.92, "confidence": 0.88, "star_rating": 5},
        {"sentiment": "POSITIVE", "score": 0.78, "confidence": 0.75, "star_rating": 4},
        {"sentiment": "POSITIVE", "score": 0.95, "confidence": 0.92, "star_rating": 5},
        {"sentiment": "POSITIVE", "score": 0.90, "confidence": 0.87, "star_rating": 5},
    ]
    result = scorer.calculate_food_score(adana_sentiments)
    print(f"  Puan      : {result['score_1_10']}/10")
    print(f"  Guven     : {result['confidence']:.4f}")
    print(f"  Yorum     : {result['review_count']}")
    print(f"  Yeterli   : {result['enough_data']}")
    print(f"  Dagilim   : {result['sentiment_distribution']}")

    # 4. Edge case: tek yorum
    print("\n--- Edge Case: Tek Yorum ---")
    single = [{"sentiment": "NEGATIVE", "score": 0.85, "confidence": 0.80, "star_rating": 1}]
    result = scorer.calculate_food_score(single)
    print(f"  Puan      : {result['score_1_10']}/10")
    print(f"  Guven     : {result['confidence']:.4f} (dusuk: tek yorum)")
    print(f"  Yeterli   : {result['enough_data']}")

    # 5. Edge case: tumu pozitif
    print("\n--- Edge Case: Tumu Pozitif ---")
    all_pos = [
        {"sentiment": "POSITIVE", "score": 0.90, "confidence": 0.85, "star_rating": 5},
        {"sentiment": "POSITIVE", "score": 0.88, "confidence": 0.82, "star_rating": 5},
        {"sentiment": "POSITIVE", "score": 0.95, "confidence": 0.90, "star_rating": 5},
    ]
    result = scorer.calculate_food_score(all_pos)
    print(f"  Puan      : {result['score_1_10']}/10 (max beklenir)")

    # 6. Edge case: tumu negatif
    print("\n--- Edge Case: Tumu Negatif ---")
    all_neg = [
        {"sentiment": "NEGATIVE", "score": 0.90, "confidence": 0.85, "star_rating": 1},
        {"sentiment": "NEGATIVE", "score": 0.88, "confidence": 0.82, "star_rating": 1},
        {"sentiment": "NEGATIVE", "score": 0.95, "confidence": 0.90, "star_rating": 1},
    ]
    result = scorer.calculate_food_score(all_neg)
    print(f"  Puan      : {result['score_1_10']}/10 (min beklenir)")

    # 7. Rapor
    print("\n")
    report = scorer.generate_report(food_scores)
    print(report)

    print(f"\nToplam: {len(food_scores)} yemek puanlandi.")


if __name__ == "__main__":
    main()
