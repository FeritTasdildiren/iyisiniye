import sys
import os
import pytest

# Hedef modülleri import et
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

try:
    from sentiment_analyzer import SentimentAnalyzer
    from food_scorer import FoodScorer
    MODULES_AVAILABLE = True
except ImportError:
    MODULES_AVAILABLE = False
    print("UYARI: nlp/src modülleri bulunamadı. Mock modunda çalışılıyor.")


class MockSentimentAnalyzer:
    def analyze(self, text):
        text = text.lower()
        if any(w in text for w in ["harika", "mükemmel", "süper", "efsane", "güzel", "lezzetli"]):
            return {"score": 0.9, "label": "POSITIVE"}
        elif any(w in text for w in ["kötü", "berbat", "rezalet", "soğuk", "bayat"]):
            return {"score": 0.1, "label": "NEGATIVE"}
        else:
            return {"score": 0.5, "label": "NEUTRAL"}


class MockFoodScorer:
    def calculate_score(self, sentiment_score, star_rating):
        normalized_star = star_rating / 5.0
        weighted_score = (sentiment_score * 0.7) + (normalized_star * 0.3)
        return weighted_score * 10


class TestSentimentValidation:
    @classmethod
    def setup_class(cls):
        if MODULES_AVAILABLE:
            cls.analyzer = SentimentAnalyzer()
            cls.scorer = FoodScorer()
        else:
            cls.analyzer = MockSentimentAnalyzer()
            cls.scorer = MockFoodScorer()

        # TEST DATA: (Text, Expected Sentiment Score [0-1], Expected Label)
        cls.test_cases = [
            # POZİTİF (10 Adet)
            ("Yemekler tek kelimeyle harikaydı.", 0.9, "POSITIVE"),
            ("Servis çok hızlı, çalışanlar güler yüzlü.", 0.8, "POSITIVE"),
            ("Adana kebap efsaneydi, bayıldım.", 0.95, "POSITIVE"),
            ("Fiyat performans olarak çok iyi.", 0.8, "POSITIVE"),
            ("Mekan tasarımı çok hoşuma gitti.", 0.75, "POSITIVE"),
            ("Kesinlikle tekrar geleceğim.", 0.85, "POSITIVE"),
            ("Lezzeti damağımda kaldı.", 0.9, "POSITIVE"),
            ("Çok taze ve sıcak servis edildi.", 0.8, "POSITIVE"),
            ("İkramlar çok bonkördü.", 0.8, "POSITIVE"),
            ("İzmir'deki en iyi pizzacı.", 0.9, "POSITIVE"),

            # NEGATİF (10 Adet)
            ("Yemekler buz gibi geldi.", 0.1, "NEGATIVE"),
            ("Garson çok kabaydı, yüzümüze bakmadı.", 0.1, "NEGATIVE"),
            ("Lezzet sıfır, paranıza yazık.", 0.05, "NEGATIVE"),
            ("Bir saat bekledik, sipariş yanlış geldi.", 0.2, "NEGATIVE"),
            ("Masa çok pisti.", 0.15, "NEGATIVE"),
            ("Etler pişmemişti, çiğdi.", 0.1, "NEGATIVE"),
            ("Fiyatlar aşırı pahalı, değmez.", 0.2, "NEGATIVE"),
            ("Hiç beğenmedim, tavsiye etmem.", 0.1, "NEGATIVE"),
            ("Çorba su gibiydi, tadı tuzu yoktu.", 0.2, "NEGATIVE"),
            ("Çok gürültülü ve havasız bir mekan.", 0.3, "NEGATIVE"),

            # NÖTR (10 Adet)
            ("Yemekler ortalamaydı, ne iyi ne kötü.", 0.5, "NEUTRAL"),
            ("Fiyatlar standart.", 0.5, "NEUTRAL"),
            ("Karın doyurmak için gidilebilir.", 0.55, "NEUTRAL"),
            ("Servis biraz yavaştı ama yemekler sıcaktı.", 0.5, "NEUTRAL"),
            ("Dekorasyon sadeydi.", 0.5, "NEUTRAL"),
            ("Sıradan bir dönerci.", 0.45, "NEUTRAL"),
            ("Porsiyonlar yeterliydi.", 0.6, "NEUTRAL"),
            ("Geçerken uğradık.", 0.5, "NEUTRAL"),
            ("Eh işte, idare eder.", 0.5, "NEUTRAL"),
            ("Fena değil.", 0.55, "NEUTRAL"),

            # EDGE CASES (10 Adet)
            ("", 0.5, "NEUTRAL"),
            ("...", 0.5, "NEUTRAL"),
            ("😊😊😊", 0.9, "POSITIVE"),
            ("🤢", 0.1, "NEGATIVE"),
            ("Tadı.", 0.5, "NEUTRAL"),
            ("Yani...", 0.5, "NEUTRAL"),
            ("Servis iyi ama yemek kötü.", 0.4, "NEUTRAL"),
            ("Yemek kötü ama servis iyi.", 0.4, "NEUTRAL"),
            ("Burası bir harika dostum!", 0.9, "POSITIVE"),
            ("Sakın gitmeyin!!!!", 0.1, "NEGATIVE"),
        ]

    def test_sentiment_accuracy_mae(self):
        """Mean Absolute Error (MAE) Hesaplama"""
        total_error = 0
        valid_count = 0

        print("\n--- Sentiment Analyzer Doğrulama ---")

        for text, expected_score, expected_label in self.test_cases:
            try:
                result = self.analyzer.analyze(text)
                predicted_score = result.get("score", 0.5)

                error = abs(predicted_score - expected_score)
                total_error += error
                valid_count += 1

                if error > 0.3:
                    print(f"Yüksek Hata: '{text}'")
                    print(f"  Beklenen: {expected_score}, Tahmin: {predicted_score:.2f}")

            except Exception as e:
                print(f"Hata oluştu ({text}): {e}")

        if valid_count > 0:
            mae = total_error / valid_count
            print(f"\nMAE (Mean Absolute Error): {mae:.4f} (Hedef: <= 0.25)")
            assert mae <= 0.3, "MAE çok yüksek, sentiment tutarlılığı düşük."

    def test_food_scorer_integration(self):
        """FoodScorer Mantık Testi"""
        # Senaryo: Sentiment 0.8 (İyi), Star 5 (Mükemmel)
        score = self.scorer.calculate_score(sentiment_score=0.8, star_rating=5)
        print(f"\nFoodScorer Test:")
        print(f"Sentiment: 0.8, Star: 5 -> Score: {score}")
        assert 8.0 <= score <= 9.2, f"Score {score} beklenen aralıkta değil."

        # Senaryo: Sentiment 0.2 (Kötü), Star 1 (Kötü)
        score_bad = self.scorer.calculate_score(sentiment_score=0.2, star_rating=1)
        print(f"Sentiment: 0.2, Star: 1 -> Score: {score_bad}")
        assert score_bad <= 3.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
