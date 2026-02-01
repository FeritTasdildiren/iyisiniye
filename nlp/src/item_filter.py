import json
import re
from typing import Dict, List, Optional


class ItemFilter:
    """Menu items classifier for beverages, side items, and foods."""

    def __init__(self, sozluk_path: str) -> None:
        """Load filtering dictionary JSON from the given path."""
        with open(sozluk_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.beverage_keywords = [self.normalize(k) for k in data.get("icecek", [])]
        self.side_keywords = [self.normalize(k) for k in data.get("yan_urun", [])]

        # Longest-first matching prefers multi-word phrases.
        self.beverage_keywords.sort(key=len, reverse=True)
        self.side_keywords.sort(key=len, reverse=True)

        self.food_override_terms = {
            "sarma",
            "sarması",
            "sarmasi",
            "dolma",
            "kebap",
            "çorba",
            "corba",
            "pilav",
            "yaprak",
            "yaprağı",
            "yapragi",
        }

    def normalize(self, text: str) -> str:
        """Lowercase, trim, and normalize internal whitespace (Turkish chars preserved)."""
        return re.sub(r"\s+", " ", text.strip().lower())

    def _find_match(self, text: str, keywords: List[str]) -> Optional[str]:
        """Return the first keyword that appears as a substring in text."""
        for kw in keywords:
            if kw and kw in text:
                return kw
        return None

    def is_beverage(self, item_name: str) -> bool:
        """Return True if the item is classified as beverage (with partial match)."""
        normalized = self.normalize(item_name)
        match = self._find_match(normalized, self.beverage_keywords)
        if not match:
            return False

        tokens = normalized.split()
        is_multi_word_match = " " in match
        has_food_override = any(term in normalized for term in self.food_override_terms)
        if not is_multi_word_match and (len(tokens) >= 3 or has_food_override):
            return False

        return True

    def is_side_item(self, item_name: str) -> bool:
        """Return True if the item is classified as side item."""
        normalized = self.normalize(item_name)
        return self._find_match(normalized, self.side_keywords) is not None

    def classify(self, item_name: str) -> Dict[str, object]:
        """Classify the item into yemek/icecek/yan_urun with metadata."""
        normalized = self.normalize(item_name)

        side_match = self._find_match(normalized, self.side_keywords)
        if side_match:
            return {
                "name": item_name,
                "type": "yan_urun",
                "category": side_match,
                "confidence": 0.95,
            }

        beverage_match = self._find_match(normalized, self.beverage_keywords)
        if beverage_match:
            tokens = normalized.split()
            is_multi_word_match = " " in beverage_match
            has_food_override = any(term in normalized for term in self.food_override_terms)
            if not is_multi_word_match and (len(tokens) >= 3 or has_food_override):
                return {
                    "name": item_name,
                    "type": "yemek",
                    "category": None,
                    "confidence": 0.7,
                }
            return {
                "name": item_name,
                "type": "icecek",
                "category": beverage_match,
                "confidence": 0.9,
            }

        return {
            "name": item_name,
            "type": "yemek",
            "category": None,
            "confidence": 0.6,
        }

    def filter_menu_items(self, items: List[str]) -> Dict[str, List[str]]:
        """Group items into yemekler, icecekler, yan_urunler, belirsiz."""
        grouped = {
            "yemekler": [],
            "icecekler": [],
            "yan_urunler": [],
            "belirsiz": [],
        }

        for item in items:
            result = self.classify(item)
            if result["type"] == "yemek":
                grouped["yemekler"].append(item)
            elif result["type"] == "icecek":
                grouped["icecekler"].append(item)
            elif result["type"] == "yan_urun":
                grouped["yan_urunler"].append(item)
            else:
                grouped["belirsiz"].append(item)

        return grouped


if __name__ == "__main__":
    filterer = ItemFilter("/Users/ferit/Projeler/iyisiniye/nlp/data/filtre_sozlugu.json")

    examples = [
        "çay",
        "kahve",
        "ayran",
        "peçete",
        "plastik çatal",
        "Adana kebap",
        "mercimek çorbası",
        "çay yaprağı sarması",
        "soğuk kahve",
        "soğuk çay",
        "taze sıkılmış portakal suyu",
    ]

    for name in examples:
        print(filterer.classify(name))

    print(filterer.filter_menu_items(examples))
