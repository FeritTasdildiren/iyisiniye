"""
Yemek İsmi Çıkarıcı Modülü
Yorum metinlerinden yemek isimlerini çıkarır, içecek/yan ürünleri filtreler.
"""
import logging
import json
import pandas as pd
from typing import List, Dict, Any
from collections import Counter

logger = logging.getLogger(__name__)

# Dependency imports
try:
    from food_normalizer import FoodNormalizer
    from item_filter import ItemFilter
except ImportError:
    try:
        from .food_normalizer import FoodNormalizer
        from .item_filter import ItemFilter
    except ImportError:
        logger.warning("food_normalizer veya item_filter modülleri bulunamadı.")
        FoodNormalizer = None
        ItemFilter = None


class FoodExtractor:
    """Yorum metinlerinden yemek isimlerini çıkaran ana sınıf."""

    def __init__(self, yemek_sozluk_path: str, filtre_sozluk_path: str):
        """
        FoodNormalizer ve ItemFilter'ı başlatır.

        Args:
            yemek_sozluk_path: Yemek sözlüğü JSON dosya yolu
            filtre_sozluk_path: Filtreleme sözlüğü JSON dosya yolu
        """
        if FoodNormalizer is None or ItemFilter is None:
            raise ImportError("food_normalizer ve item_filter modülleri gerekli.")

        self.normalizer = FoodNormalizer(yemek_sozluk_path)
        self.item_filter = ItemFilter(filtre_sozluk_path)
        logger.info(f"FoodExtractor başlatıldı. Sözlük: {len(self.normalizer.food_data)} yemek")

    def extract_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Metindeki yemek isimlerini bulur ve sınıflandırır.

        Args:
            text: Analiz edilecek metin

        Returns:
            [{canonical, matched_text, score, category, is_food}]
        """
        if not text or not text.strip():
            return []

        # FoodNormalizer ile yemek isimlerini bul
        found_items = self.normalizer.find_food_names(text)

        results = []
        for item in found_items:
            canonical = item.get('canonical', '')
            matched_text = item.get('matched_text', '')
            score = item.get('score', 0.0)
            food_category = item.get('category', '')

            # ItemFilter ile sınıflandır
            classification = self.item_filter.classify(canonical)
            item_type = classification.get('type', 'yemek')
            is_food = (item_type == 'yemek')

            results.append({
                'canonical': canonical,
                'matched_text': matched_text,
                'score': score,
                'category': food_category if is_food else item_type,
                'is_food': is_food
            })

        return results

    def extract_from_review(self, review: Dict[str, Any]) -> Dict[str, Any]:
        """
        Bir yorum nesnesinden yemekleri çıkarır.

        Args:
            review: {review_id, text, star_rating}

        Returns:
            {review_id, text, star_rating, foods, food_count}
        """
        text = review.get('text', '')
        extracted = self.extract_from_text(text)
        food_count = sum(1 for f in extracted if f.get('is_food'))

        return {
            'review_id': review.get('review_id'),
            'text': text,
            'star_rating': review.get('star_rating'),
            'foods': extracted,
            'food_count': food_count
        }

    def extract_batch(self, reviews: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Toplu çıkarma işlemi yapar ve DataFrame döndürür.

        Args:
            reviews: Yorum listesi

        Returns:
            DataFrame: review_id, text, star_rating, foods_json, food_count
        """
        rows = []
        for review in reviews:
            result = self.extract_from_review(review)
            rows.append({
                'review_id': result['review_id'],
                'text': result['text'],
                'star_rating': result['star_rating'],
                'foods_json': json.dumps(result['foods'], ensure_ascii=False),
                'food_count': result['food_count']
            })

        return pd.DataFrame(rows)

    def get_food_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Çıkarım sonuçlarından istatistikler üretir.

        Args:
            results: extract_from_review sonuçları listesi

        Returns:
            {top_20_foods, category_distribution, average_food_per_review}
        """
        all_foods = []
        category_counts: Dict[str, int] = {}
        total_food_count = 0
        total_reviews = len(results)

        for res in results:
            foods = res.get('foods', [])
            for food in foods:
                cat = food.get('category', 'bilinmeyen')
                category_counts[cat] = category_counts.get(cat, 0) + 1

                if food.get('is_food'):
                    all_foods.append(food['canonical'])
                    total_food_count += 1

        food_counter = Counter(all_foods)
        top_20 = dict(food_counter.most_common(20))
        avg_per_review = total_food_count / total_reviews if total_reviews > 0 else 0.0

        return {
            'top_20_foods': top_20,
            'category_distribution': category_counts,
            'average_food_per_review': round(avg_per_review, 2),
            'total_unique_foods': len(food_counter),
            'total_food_mentions': total_food_count,
            'total_reviews': total_reviews
        }


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)

    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    yemek_path = os.path.join(data_dir, 'yemek_sozlugu.json')
    filtre_path = os.path.join(data_dir, 'filtre_sozlugu.json')

    if os.path.exists(yemek_path) and os.path.exists(filtre_path):
        extractor = FoodExtractor(yemek_path, filtre_path)

        test_reviews = [
            {'review_id': 1, 'text': 'Adana kebap ve mercimek çorbası çok güzeldi, yanında ayran içtik', 'star_rating': 5},
            {'review_id': 2, 'text': 'İskender harika ama lahmacun biraz soğuktu', 'star_rating': 4},
            {'review_id': 3, 'text': 'Çay ve kahve güzeldi, peçete eksikti', 'star_rating': 3},
            {'review_id': 4, 'text': 'Beyti sarma muhteşem, künefe de fena değildi', 'star_rating': 5},
            {'review_id': 5, 'text': 'Pide ve çorba sipariş ettik, hepsi lezzetliydi', 'star_rating': 4},
        ]

        print("=== FoodExtractor Test ===\n")
        results = []
        for review in test_reviews:
            result = extractor.extract_from_review(review)
            results.append(result)
            foods_str = ", ".join(f['canonical'] for f in result['foods'])
            food_only = ", ".join(f['canonical'] for f in result['foods'] if f['is_food'])
            print(f"Review {result['review_id']}: {food_only} ({result['food_count']} yemek)")

        print("\n--- İstatistikler ---")
        stats = extractor.get_food_statistics(results)
        print(f"Toplam: {stats['total_food_mentions']} yemek bahsi, {stats['total_unique_foods']} benzersiz")
        print(f"Ortalama: {stats['average_food_per_review']} yemek/yorum")
        print(f"Top yemekler: {stats['top_20_foods']}")
    else:
        print(f"Sözlük dosyaları bulunamadı: {data_dir}")
