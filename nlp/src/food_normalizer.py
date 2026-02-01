import json
import re
import os
import sys
from typing import List, Dict, Optional, Tuple, Any, Set

# Gerekli kütüphaneler
try:
    from rapidfuzz import process, fuzz
except ImportError:
    print("UYARI: rapidfuzz kütüphanesi bulunamadı. Lütfen 'pip install rapidfuzz' ile kurun.", file=sys.stderr)
    process = None
    fuzz = None

class TextPreprocessor:
    """Metin ön işleme ve tokenizasyon sınıfı."""

    TURKISH_STOPWORDS = {
        'bir', 'bu', 'şu', 've', 'ile', 'için', 'de', 'da', 'mi', 'mı', 'mu', 'mü',
        'çok', 'en', 'ama', 'fakat', 'olan', 'olarak', 'ise', 'ki', 'veya', 'ya'
    }

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Metni küçük harfe çevirir ve kelimelerine ayırır (noktalama hariç)."""
        if not text:
            return []
        text = text.replace('İ', 'i').replace('I', 'ı').lower()
        tokens = re.findall(r'\w+', text)
        return tokens

    @staticmethod
    def remove_stopwords(tokens: List[str]) -> List[str]:
        """Stopword'leri listeden temizler."""
        return [t for t in tokens if t not in TextPreprocessor.TURKISH_STOPWORDS]

    @staticmethod
    def ngrams(tokens: List[str], n: int) -> List[str]:
        """n-gram listesi oluşturur."""
        if n < 1 or len(tokens) < n:
            return []
        return [' '.join(tokens[i:i+n]) for i in range(len(tokens)-n+1)]

class FoodNormalizer:
    """Yemek isimlerini normalize eden ve arayan sınıf."""

    def __init__(self, sozluk_path: str):
        self.sozluk_path = sozluk_path
        self.food_data: List[Dict] = []
        self.canonical_map: Dict[str, str] = {}  # normalized_name -> canonical_name
        self.lookup_keys: List[str] = []  # Fuzzy search için anahtar listesi

        self._load_data()
        self.build_lookup_table()

    def _load_data(self):
        """JSON sözlüğünü yükler."""
        if not os.path.exists(self.sozluk_path):
            raise FileNotFoundError(f"Yemek sözlüğü bulunamadı: {self.sozluk_path}")

        try:
            with open(self.sozluk_path, 'r', encoding='utf-8') as f:
                self.food_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON format hatası ({self.sozluk_path}): {e}")

    def normalize_text(self, text: str) -> str:
        """
        Metni normalize eder: Lowercase, noktalama temizliği, fazla boşluk temizliği.
        Türkçe karakterleri KORUR.
        """
        if not text:
            return ""

        # 1. Lowercase (Türkçe uyumlu 'İ' -> 'i', 'I' -> 'ı')
        text = text.replace('İ', 'i').replace('I', 'ı').lower()

        # 2. Noktalama temizliği (harf ve rakam dışı her şeyi boşluk yap)
        text = re.sub(r'[^\w\s]', ' ', text)
        text = text.replace('_', ' ')

        # 3. Fazla boşlukları temizle
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def _to_ascii(self, text: str) -> str:
        """Yardımcı: Türkçe karakterleri ASCII karşılıklarına çevirir."""
        tr_map = str.maketrans("çğıöşü", "cgiosu")
        return text.translate(tr_map)

    def build_lookup_table(self):
        """
        Alias ve Canonical isimlerden lookup tablosu oluşturur.
        Hem orijinal (Türkçe karakterli) hem de ASCII versiyonlarını map'e ekler.
        """
        self.canonical_map = {}

        for item in self.food_data:
            canonical = item.get('canonical')
            if not canonical:
                continue

            # Canonical'ın kendisini ekle
            norm_canonical = self.normalize_text(canonical)
            self.canonical_map[norm_canonical] = canonical

            # ASCII versiyonunu da ekle
            ascii_canonical = self._to_ascii(norm_canonical)
            if ascii_canonical != norm_canonical:
                self.canonical_map[ascii_canonical] = canonical

            # Aliasları ekle
            aliases = item.get('aliases', [])
            for alias in aliases:
                norm_alias = self.normalize_text(alias)
                self.canonical_map[norm_alias] = canonical

                ascii_alias = self._to_ascii(norm_alias)
                if ascii_alias != norm_alias:
                    self.canonical_map[ascii_alias] = canonical

        self.lookup_keys = list(self.canonical_map.keys())

    def fuzzy_match(self, query: str, threshold: float = 75.0) -> List[Tuple[str, float]]:
        """
        Rapidfuzz ile benzer yemek isimlerini bulur.
        Return: [(canonical_name, score), ...]
        """
        if not process or not self.lookup_keys:
            return []

        norm_query = self.normalize_text(query)

        matches = process.extract(norm_query, self.lookup_keys, limit=5, scorer=fuzz.WRatio)

        results = []
        seen_canonicals = set()

        for match_str, score, _ in matches:
            if score >= threshold:
                canonical = self.canonical_map.get(match_str)
                if canonical and canonical not in seen_canonicals:
                    results.append((canonical, score))
                    seen_canonicals.add(canonical)

        return results

    def exact_match(self, query: str) -> Optional[str]:
        """Tam eşleşme arar."""
        norm_query = self.normalize_text(query)
        return self.canonical_map.get(norm_query)

    def find_food_names(self, text: str) -> List[Dict[str, Any]]:
        """
        Metin içindeki yemek isimlerini bulur (Exact + Fuzzy).
        """
        found_foods = []

        # 1. Tokenize
        tokens = TextPreprocessor.tokenize(text)

        # 2. Generate n-grams (1 to 4 words usually covers most food names)
        candidates = []
        for n in range(1, 5):
            ngrams = TextPreprocessor.ngrams(tokens, n)
            candidates.extend(ngrams)

        # 3. Check candidates
        raw_matches = []

        for candidate in candidates:
            # Exact Match Check
            canonical = self.exact_match(candidate)
            if canonical:
                raw_matches.append({
                    'canonical': canonical,
                    'matched_text': candidate,
                    'score': 100.0,
                    'method': 'exact'
                })
                continue

            # Fuzzy Match Check (Sadece 3 karakterden uzunsa ve stopwords değilse)
            if len(candidate) < 3:
                continue

            if candidate in TextPreprocessor.TURKISH_STOPWORDS:
                continue

            fuzzy_results = self.fuzzy_match(candidate, threshold=85.0)
            if fuzzy_results:
                best_canonical, score = fuzzy_results[0]
                raw_matches.append({
                    'canonical': best_canonical,
                    'matched_text': candidate,
                    'score': score,
                    'method': 'fuzzy'
                })

        # 4. Filter Overlaps and Select Best Matches
        raw_matches.sort(key=lambda x: (x['score'], len(x['matched_text'])), reverse=True)

        final_results = []
        seen_canonicals = set()

        for match in raw_matches:
            if match['canonical'] not in seen_canonicals:
                # Kategori ve Bölge bilgisini ekle
                item_data = next((i for i in self.food_data if i['canonical'] == match['canonical']), {})
                match['category'] = item_data.get('category')
                match['region'] = item_data.get('region')

                final_results.append(match)
                seen_canonicals.add(match['canonical'])

        return final_results


if __name__ == "__main__":
    sozluk_path = "/Users/ferit/Projeler/iyisiniye/nlp/data/yemek_sozlugu.json"

    if os.path.exists(sozluk_path):
        normalizer = FoodNormalizer(sozluk_path)
        print(f"Sözlük yüklendi: {len(normalizer.food_data)} yemek")
        print(f"Lookup tablosu: {len(normalizer.lookup_keys)} anahtar")

        test_sentences = [
            "Adana kebap çok lezzetliydi",
            "İskender ve ayran aldık",
            "Mercimek çorbası harika",
            "Bir porsiyon acılı lahmacun lütfen",
            "Beyti kebap muhteşemdi",
        ]

        print("-" * 60)
        for sent in test_sentences:
            print(f"Metin: '{sent}'")
            results = normalizer.find_food_names(sent)
            for res in results:
                print(f"  -> {res['canonical']:<20} | Kategori: {res.get('category', '-'):<12} | Skor: {res['score']:.1f} ({res['method']})")
            print("-" * 60)
    else:
        print(f"Sözlük dosyası bulunamadı: {sozluk_path}")
        print("Lütfen önce yemek sözlüğünü oluşturun.")
