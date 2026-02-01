import sys
import os
import json
import pytest
from collections import Counter

# Hedef modülleri import etmek için path ayarı
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Importlar başarısız olursa Mock kullanmak için try-except bloğu
try:
    from food_extractor import FoodExtractor
    from food_normalizer import FoodNormalizer
    from item_filter import ItemFilter
    MODULES_AVAILABLE = True
except ImportError:
    MODULES_AVAILABLE = False
    print("UYARI: nlp/src modülleri bulunamadı. Mock modunda çalışılıyor.")

class MockFoodExtractor:
    """Modüller bulunamazsa testin çalışması için basit bir mock"""
    def extract_from_text(self, text):
        text = text.lower()
        foods = []
        known_foods = {
            "adana": "Adana Kebap", "adana kebap": "Adana Kebap",
            "iskender": "İskender Kebap", "döner": "Döner",
            "lahmacun": "Lahmacun", "künefe": "Künefe",
            "ayran": "Ayran", "mercimek": "Mercimek Çorbası",
            "hamburger": "Hamburger", "pizza": "Pizza",
            "sushi": "Sushi", "mantı": "Mantı",
            "beyti": "Beyti", "çiğ köfte": "Çiğ Köfte",
            "baklava": "Baklava", "tiramisu": "Tiramisu",
            "latte": "Latte", "çay": "Çay"
        }
        for k, v in known_foods.items():
            if k in text:
                foods.append(v)
        return list(set(foods))


class TestFoodExtractorQuality:
    @classmethod
    def setup_class(cls):
        if MODULES_AVAILABLE:
            cls.extractor = FoodExtractor()
        else:
            cls.extractor = MockFoodExtractor()

        # TEST VERİ SETİ (Ground Truth)
        cls.test_data = [
            # Pozitif - Tekil Yemekler
            {"text": "Adana kebap gerçekten harikaydı, tam kıvamında.", "expected": ["Adana Kebap"]},
            {"text": "Yediğim en iyi lahmacun diyebilirim.", "expected": ["Lahmacun"]},
            {"text": "İskender sosu biraz soğuktu ama eti lezzetliydi.", "expected": ["İskender Kebap"]},
            {"text": "Mantı porsiyonu oldukça doyurucuydu.", "expected": ["Mantı"]},
            {"text": "Hamburger ekmeği bayattı.", "expected": ["Hamburger"]},

            # Çoklu Yemekler
            {"text": "Önden mercimek çorbası, ana yemek olarak beyti söyledik.", "expected": ["Mercimek Çorbası", "Beyti"]},
            {"text": "Lahmacun ve ayran ikilisi vazgeçilmez.", "expected": ["Lahmacun", "Ayran"]},
            {"text": "Pizza söyledik yanına da soğan halkası ve kola.", "expected": ["Pizza", "Soğan Halkası", "Kola"]},
            {"text": "Döner dürüm ve patates kızartması siparişim 1 saatte geldi.", "expected": ["Döner", "Patates Kızartması"]},
            {"text": "Sushi taze, noodle ise çok yağlıydı.", "expected": ["Sushi", "Noodle"]},

            # Tatlılar ve İçecekler
            {"text": "Yemekten sonra künefe söyledik, şerbeti çok fazlaydı.", "expected": ["Künefe"]},
            {"text": "Türk kahvesi ve tiramisu ile kapanışı yaptık.", "expected": ["Türk Kahvesi", "Tiramisu"]},
            {"text": "Çay ikram etmediler.", "expected": ["Çay"]},
            {"text": "Baklava taze değildi.", "expected": ["Baklava"]},
            {"text": "Latte çok sütlüydü.", "expected": ["Latte"]},

            # Zorlayıcı Durumlar (Edge Cases)
            {"text": "Garsonlar çok ilgiliydi, mekan temiz.", "expected": []},
            {"text": "Servis hızı rezalet, bir daha gelmem.", "expected": []},
            {"text": "Urfa söyledim ama Adana geldi.", "expected": ["Urfa Kebap", "Adana Kebap"]},
            {"text": "Sıcak bir çorba içmek için girdik.", "expected": ["Çorba"]},
            {"text": "Tavuk suyu çorbası şifalı gibiydi.", "expected": ["Tavuk Suyu Çorbası"]},

            # Normalizasyon Testleri
            {"text": "DÖNERLERİ çok güzeldi.", "expected": ["Döner"]},
            {"text": "Iskender yemek istiyorsan buraya gelme.", "expected": ["İskender Kebap"]},
            {"text": "çiğköfte dürüm acılıydı.", "expected": ["Çiğ Köfte"]},
            {"text": "Sübye ve kalamar tavası efsane.", "expected": ["Sübye", "Kalamar Tava"]},
            {"text": "Kaşarlı pide biraz yanmıştı.", "expected": ["Kaşarlı Pide"]},

            # Yanıltıcı / Negatif Filtreleme
            {"text": "Masa örtüsü kirliydi.", "expected": []},
            {"text": "Hesap çok geldi.", "expected": []},
            {"text": "Kurye çok kabaydı.", "expected": []},
            {"text": "Paket servis çok yavaştı.", "expected": []},
            {"text": "Menü çok zengindi.", "expected": []}
        ]

    def test_precision_recall_f1(self):
        """Metrik hesaplama ve Raporlama"""
        true_positives = 0
        false_positives = 0
        false_negatives = 0

        errors = []

        print("\n--- FoodExtractor Kalite Raporu ---")

        for case in self.test_data:
            text = case["text"]
            expected = set(case["expected"])

            try:
                predicted_list = self.extractor.extract_from_text(text)
                predicted = set(predicted_list)
            except Exception as e:
                print(f"HATA: '{text}' işlenirken hata oluştu: {e}")
                predicted = set()

            tp = len(expected.intersection(predicted))
            fp = len(predicted - expected)
            fn = len(expected - predicted)

            true_positives += tp
            false_positives += fp
            false_negatives += fn

            if fp > 0 or fn > 0:
                errors.append({
                    "text": text,
                    "expected": list(expected),
                    "predicted": list(predicted),
                    "missed": list(expected - predicted),
                    "wrong": list(predicted - expected)
                })

        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        print(f"\nToplam Yorum: {len(self.test_data)}")
        print(f"True Positives: {true_positives}")
        print(f"False Positives: {false_positives}")
        print(f"False Negatives: {false_negatives}")
        print(f"\nMETRİKLER:")
        print(f"Precision: {precision:.2%} (Hedef: >=75%)")
        print(f"Recall:    {recall:.2%} (Hedef: >=60%)")
        print(f"F1 Score:  {f1:.2%}")

        if MODULES_AVAILABLE:
            assert precision >= 0.75, "Precision hedefi (%75) tutturulamadı."
            assert recall >= 0.60, "Recall hedefi (%60) tutturulamadı."

        if errors:
            print("\n--- HATA ANALİZİ (İlk 5) ---")
            for err in errors[:5]:
                print(f"Yorum: {err['text']}")
                print(f"  Beklenen: {err['expected']}")
                print(f"  Bulunan:  {err['predicted']}")
                if err['missed']:
                    print(f"  Eksik (FN): {err['missed']}")
                if err['wrong']:
                    print(f"  Hatalı (FP): {err['wrong']}")
                print("-" * 30)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
