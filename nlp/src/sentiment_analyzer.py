"""
sentiment_analyzer.py - Turkce BERT tabanli sentiment analiz pipeline.

Google Maps restoran yorumlarini analiz eder. dbmdz/bert-base-turkish-cased
modelinin CLS token embedding'ini kullanarak 3-sinifli (pozitif/notr/negatif)
sentiment tahmini yapar. WeakLabeler ile birlestirerek nihai skor uretir.

Etiket degerleri:
    POSITIVE = 1
    NEUTRAL  = 0
    NEGATIVE = -1
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch import Tensor
from tqdm import tqdm
from transformers import AutoModel, AutoTokenizer

from weak_labeler import WeakLabeler

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

# ── Sabitler ─────────────────────────────────────────────────────────────

LABEL_MAP: dict[int, str] = {1: "POSITIVE", 0: "NEUTRAL", -1: "NEGATIVE"}
LABEL_MAP_INV: dict[str, int] = {v: k for k, v in LABEL_MAP.items()}

# Basit kural: CLS embedding'in 3 sinifa projeksiyonu icin
# unsupervised "pseudo" agirliklar. Gercek fine-tune olmadan
# metin embedding benzerligine dayali siniflama yapar.
SEED_SENTENCES: dict[int, list[str]] = {
    1: [
        "Bu restoran harika, yemekler cok lezzetli ve servis mukemmel.",
        "Muhtesem bir deneyim, kesinlikle tavsiye ederim.",
        "Her sey cok guzeldi, bayildim.",
    ],
    0: [
        "Normal bir mekan, fena degil ama ozel bir sey de yok.",
        "Ortalama bir deneyim, ne iyi ne kotu.",
        "Idare eder, vasat bir restoran.",
    ],
    -1: [
        "Berbat bir deneyim, yemekler cok kotuydu.",
        "Rezalet servis, bir daha gelmem buraya.",
        "Igrenc, yemek soguk ve tatsizdi.",
    ],
}

MAX_SEQ_LEN = 128


# ── Yardimci: Cumle bolucu ──────────────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    """Metni cumlelere boler (basit regex tabanli)."""
    parts = re.split(r"[.!?;]+", text)
    return [p.strip() for p in parts if p.strip()]


# ── SentimentAnalyzer ────────────────────────────────────────────────────


class SentimentAnalyzer:
    """Turkce BERT (dbmdz/bert-base-turkish-cased) tabanli sentiment analizcisi.

    Base model sentiment fine-tune'lu olmadigi icin, CLS token embedding'ini
    kullanarak seed cumle benzerligine dayali zero-shot siniflama yapar.
    WeakLabeler ile birlestirerek daha guvenilir sonuc uretir.

    Args:
        model_name: HuggingFace model adi.
        device:     ``None`` ise otomatik CPU/CUDA secimi yapilir.
    """

    def __init__(
        self,
        model_name: str = "dbmdz/bert-base-turkish-cased",
        device: str | None = None,
    ) -> None:
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        logger.info("Model yukleniyor: %s (device=%s)", model_name, self.device)

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(self.device)
        self.model.eval()

        self.weak_labeler = WeakLabeler()

        # Seed cumlelerden prototip vektorleri olustur
        self._class_prototypes: dict[int, Tensor] = self._build_prototypes()
        logger.info("Sentiment analyzer hazir. Prototip boyutu: %d", self.model.config.hidden_size)

    # ── Prototip olusturma ───────────────────────────────────────────

    def _encode_texts(self, texts: list[str]) -> Tensor:
        """Metin listesini CLS embedding'lerine donusturur.

        Args:
            texts: Encode edilecek metinler.

        Returns:
            (N, hidden_size) boyutunda Tensor.
        """
        encodings = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=MAX_SEQ_LEN,
            return_tensors="pt",
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**encodings)

        # CLS token embedding: [batch, hidden_size]
        cls_emb = outputs.last_hidden_state[:, 0, :]
        # L2 normalize
        cls_emb = nn.functional.normalize(cls_emb, p=2, dim=1)
        return cls_emb

    def _build_prototypes(self) -> dict[int, Tensor]:
        """Her sentiment sinifi icin ortalama prototip vektoru hesaplar."""
        prototypes: dict[int, Tensor] = {}
        for label, sentences in SEED_SENTENCES.items():
            embs = self._encode_texts(sentences)
            proto = embs.mean(dim=0)
            proto = nn.functional.normalize(proto, p=2, dim=0)
            prototypes[label] = proto
        logger.info("Sinif prototipleri olusturuldu: %s", list(prototypes.keys()))
        return prototypes

    # ── Tekil analiz ─────────────────────────────────────────────────

    def analyze_text(self, text: str) -> dict[str, Any]:
        """Tek bir metni sentiment olarak analiz eder.

        CLS embedding ile prototip vektorleri arasindaki cosine
        benzerligini hesaplayarak sinif tahmini yapar.

        Args:
            text: Analiz edilecek metin.

        Returns:
            ``label`` (POSITIVE|NEUTRAL|NEGATIVE), ``score`` (float),
            ``raw_scores`` (dict) iceren sonuc.
        """
        if not text or not text.strip():
            return {
                "label": "NEUTRAL",
                "score": 0.5,
                "raw_scores": {"POSITIVE": 0.33, "NEUTRAL": 0.34, "NEGATIVE": 0.33},
            }

        emb = self._encode_texts([text])[0]  # (hidden_size,)

        # Cosine similarity (vektorler zaten L2 normalized)
        similarities: dict[int, float] = {}
        for label, proto in self._class_prototypes.items():
            sim = torch.dot(emb, proto).item()
            similarities[label] = sim

        # Softmax ile olasiliga donustur
        sim_tensor = torch.tensor(
            [similarities[1], similarities[0], similarities[-1]],
            dtype=torch.float32,
        )
        probs = torch.softmax(sim_tensor * 5.0, dim=0)  # temperature=0.2 (1/5)

        raw_scores = {
            "POSITIVE": round(probs[0].item(), 4),
            "NEUTRAL": round(probs[1].item(), 4),
            "NEGATIVE": round(probs[2].item(), 4),
        }

        # En yuksek olasilikli sinif
        pred_idx = torch.argmax(probs).item()
        label_order = [1, 0, -1]
        pred_label_int = label_order[pred_idx]

        return {
            "label": LABEL_MAP[pred_label_int],
            "score": round(probs[pred_idx].item(), 4),
            "raw_scores": raw_scores,
        }

    def analyze_review(self, review: dict[str, Any]) -> dict[str, Any]:
        """Bir restoran yorumunu BERT + WeakLabeler ile analiz eder.

        BERT sentiment tahmini ve WeakLabeler kural tabanlii etiketi
        birlestirilir. Uyusma durumunda guven artar, celiskide azalir.

        Args:
            review: ``review_id``, ``text``, ``star_rating`` anahtarli sozluk.

        Returns:
            ``review_id``, ``bert_sentiment``, ``bert_score``,
            ``weak_label``, ``final_sentiment``, ``confidence`` iceren sonuc.
        """
        review_id = review["review_id"]
        text = review.get("text") or ""
        star_rating = float(review["star_rating"])

        # BERT analizi
        bert_result = self.analyze_text(text)
        bert_label_int = LABEL_MAP_INV[bert_result["label"]]

        # WeakLabeler analizi
        rating_label = WeakLabeler.label_from_rating(star_rating)
        text_label = self.weak_labeler.label_from_text(text)
        weak_conf = WeakLabeler.confidence_score(rating_label, text_label)

        # Nihai karar: BERT + WeakLabeler ensemble
        # WeakLabeler'in etiketi rating-oncelikli
        weak_label = rating_label

        # Uyusma kontrolu
        if bert_label_int == weak_label:
            # Tam uyusma: yuksek guven
            final_sentiment = LABEL_MAP[bert_label_int]
            confidence = min(0.95, (bert_result["score"] + weak_conf) / 2 + 0.15)
        elif bert_result["score"] > 0.75 and weak_conf < 0.5:
            # BERT cok emin ama weak labeler dusuk guvenli: BERT'e guven
            final_sentiment = bert_result["label"]
            confidence = round(bert_result["score"] * 0.7, 4)
        else:
            # Celiskili: WeakLabeler (rating bazli) oncelikli
            final_sentiment = LABEL_MAP[weak_label]
            confidence = round(weak_conf * 0.6 + bert_result["score"] * 0.2, 4)

        return {
            "review_id": review_id,
            "bert_sentiment": bert_result["label"],
            "bert_score": bert_result["score"],
            "weak_label": LABEL_MAP[weak_label],
            "final_sentiment": final_sentiment,
            "confidence": round(confidence, 4),
        }

    def analyze_batch(
        self,
        reviews: list[dict[str, Any]],
        batch_size: int = 16,
    ) -> pd.DataFrame:
        """Yorum listesini toplu olarak analiz eder.

        Bellek tasarrufu icin ``torch.no_grad()`` kullanir ve
        ``batch_size`` kadar yorumu ayni anda isler.

        Args:
            reviews:    ``review_id``, ``text``, ``star_rating`` iceren sozluk listesi.
            batch_size: Ayni anda islenecek yorum sayisi.

        Returns:
            Analiz sonuclarini iceren DataFrame.
        """
        results: list[dict[str, Any]] = []

        for i in tqdm(range(0, len(reviews), batch_size), desc="Sentiment analizi"):
            batch = reviews[i : i + batch_size]
            texts = [r.get("text") or "" for r in batch]

            # Toplu BERT encoding
            if any(t.strip() for t in texts):
                non_empty_texts = [t if t.strip() else "." for t in texts]
                encodings = self.tokenizer(
                    non_empty_texts,
                    padding=True,
                    truncation=True,
                    max_length=MAX_SEQ_LEN,
                    return_tensors="pt",
                ).to(self.device)

                with torch.no_grad():
                    outputs = self.model(**encodings)

                cls_embs = outputs.last_hidden_state[:, 0, :]
                cls_embs = nn.functional.normalize(cls_embs, p=2, dim=1)

                # Prototip matrisi
                proto_matrix = torch.stack(
                    [self._class_prototypes[1], self._class_prototypes[0], self._class_prototypes[-1]]
                )  # (3, hidden_size)

                # Cosine similarity: (batch, 3)
                sims = torch.mm(cls_embs, proto_matrix.T)
                probs = torch.softmax(sims * 5.0, dim=1)

                label_order = [1, 0, -1]

                for j, rev in enumerate(batch):
                    raw_scores = {
                        "POSITIVE": round(probs[j, 0].item(), 4),
                        "NEUTRAL": round(probs[j, 1].item(), 4),
                        "NEGATIVE": round(probs[j, 2].item(), 4),
                    }
                    pred_idx = torch.argmax(probs[j]).item()
                    bert_label_int = label_order[pred_idx]
                    bert_score = round(probs[j, pred_idx].item(), 4)

                    # WeakLabeler
                    star_rating = float(rev["star_rating"])
                    rating_label = WeakLabeler.label_from_rating(star_rating)
                    text_label = self.weak_labeler.label_from_text(rev.get("text") or "")
                    weak_conf = WeakLabeler.confidence_score(rating_label, text_label)
                    weak_label = rating_label

                    # Ensemble
                    if bert_label_int == weak_label:
                        final_sentiment = LABEL_MAP[bert_label_int]
                        confidence = min(0.95, (bert_score + weak_conf) / 2 + 0.15)
                    elif bert_score > 0.75 and weak_conf < 0.5:
                        final_sentiment = LABEL_MAP[bert_label_int]
                        confidence = round(bert_score * 0.7, 4)
                    else:
                        final_sentiment = LABEL_MAP[weak_label]
                        confidence = round(weak_conf * 0.6 + bert_score * 0.2, 4)

                    results.append(
                        {
                            "review_id": rev["review_id"],
                            "text": rev.get("text") or "",
                            "star_rating": star_rating,
                            "bert_sentiment": LABEL_MAP[bert_label_int],
                            "bert_score": bert_score,
                            "weak_label": LABEL_MAP[weak_label],
                            "final_sentiment": final_sentiment,
                            "confidence": round(confidence, 4),
                        }
                    )
            else:
                # Tum batch bos metin
                for rev in batch:
                    star_rating = float(rev["star_rating"])
                    rating_label = WeakLabeler.label_from_rating(star_rating)
                    results.append(
                        {
                            "review_id": rev["review_id"],
                            "text": "",
                            "star_rating": star_rating,
                            "bert_sentiment": "NEUTRAL",
                            "bert_score": 0.5,
                            "weak_label": LABEL_MAP[rating_label],
                            "final_sentiment": LABEL_MAP[rating_label],
                            "confidence": 0.5,
                        }
                    )

        df = pd.DataFrame(results)
        logger.info(
            "Batch analiz tamamlandi: %d yorum. Dagilim: %s",
            len(df),
            df["final_sentiment"].value_counts().to_dict() if not df.empty else {},
        )
        return df


# ── AspectSentiment ──────────────────────────────────────────────────────


class AspectSentiment:
    """Yemek adi bazli aspect-level sentiment analizi.

    Bir yorum metninde gecen yemek isimlerini bulur ve her birinin
    gectigiicumlenin sentiment'ini ayri ayri analiz eder.

    Args:
        analyzer: Kullanilacak ``SentimentAnalyzer`` instansi.
    """

    def __init__(self, analyzer: SentimentAnalyzer) -> None:
        self.analyzer = analyzer

    def extract_aspects(
        self,
        text: str,
        food_names: list[str],
    ) -> list[dict[str, Any]]:
        """Metindeki yemek adlarini bulur ve sentiment'lerini cikarir.

        Her yemek adi icin o adiin gectigi cumleyi bulur ve
        SentimentAnalyzer ile analiz eder.

        Args:
            text:       Yorum metni.
            food_names: Aranacak yemek isimleri listesi.

        Returns:
            Her biri ``food``, ``sentence``, ``sentiment``, ``score``
            iceren sonuc listesi.
        """
        if not text or not food_names:
            return []

        text_lower = text.lower()
        sentences = _split_sentences(text)
        aspects: list[dict[str, Any]] = []

        for food in food_names:
            food_lower = food.lower()
            if food_lower not in text_lower:
                continue

            # Yemek adinin gectigi cumleyi bul
            matched_sentence = text  # fallback: tum metin
            for sent in sentences:
                if food_lower in sent.lower():
                    matched_sentence = sent
                    break

            result = self.analyzer.analyze_text(matched_sentence)
            aspects.append(
                {
                    "food": food,
                    "sentence": matched_sentence,
                    "sentiment": result["label"],
                    "score": result["score"],
                }
            )

        return aspects

    def map_sentiments_to_foods(
        self,
        review_text: str,
        food_names: list[str],
    ) -> dict[str, dict[str, Any]]:
        """Tum yemeklere sentiment eslestirmesi yapar.

        Args:
            review_text: Yorum metni.
            food_names:  Yemek isimleri listesi.

        Returns:
            ``{yemek_adi: {sentiment, score, sentence}}`` formunda sozluk.
        """
        aspects = self.extract_aspects(review_text, food_names)
        return {
            a["food"]: {
                "sentiment": a["sentiment"],
                "score": a["score"],
                "sentence": a["sentence"],
            }
            for a in aspects
        }


# ── CLI giris noktasi ───────────────────────────────────────────────────


def main() -> None:
    """Ornek kullanim: statik veriyle sentiment analizi gosterimi."""

    sample_reviews: list[dict[str, Any]] = [
        {
            "review_id": 1,
            "text": "Harika bir mekan, yemekler cok lezzetli! Adana kebap enfesti.",
            "star_rating": 5,
        },
        {
            "review_id": 2,
            "text": "Fiyatlar normal, servis yavasti biraz. Lahmacun idare ederdi.",
            "star_rating": 3,
        },
        {
            "review_id": 3,
            "text": "Berbat bir deneyim, iskender soguk geldi. Bir daha gelmem.",
            "star_rating": 1,
        },
        {
            "review_id": 4,
            "text": "Guzel mekan ama porsiyon kucuk. Pide cok guzeldi, corba kotu.",
            "star_rating": 4,
        },
        {
            "review_id": 5,
            "text": "Rezalet, mercimek corbasi bayatti. Pilav da les gibiydi.",
            "star_rating": 2,
        },
    ]

    print("\n=== Turkce BERT Sentiment Analyzer ===\n")

    # 1. Tekil analiz
    analyzer = SentimentAnalyzer()

    print("--- Tekil Metin Analizi ---")
    for rev in sample_reviews[:3]:
        result = analyzer.analyze_text(rev["text"])
        print(f"  [{rev['review_id']}] {result['label']:>8} ({result['score']:.2f}) | {rev['text'][:60]}")

    # 2. Review analizi (BERT + WeakLabeler)
    print("\n--- Review Analizi (BERT + WeakLabeler Ensemble) ---")
    for rev in sample_reviews:
        result = analyzer.analyze_review(rev)
        print(
            f"  [{result['review_id']}] BERT:{result['bert_sentiment']:>8} | "
            f"Weak:{result['weak_label']:>8} | "
            f"Final:{result['final_sentiment']:>8} (conf={result['confidence']:.2f})"
        )

    # 3. Batch analiz
    print("\n--- Batch Analiz ---")
    df = analyzer.analyze_batch(sample_reviews, batch_size=4)
    print(df[["review_id", "bert_sentiment", "weak_label", "final_sentiment", "confidence"]].to_string(index=False))

    # 4. Aspect sentiment
    print("\n--- Aspect (Yemek Bazli) Sentiment ---")
    aspect = AspectSentiment(analyzer)
    food_list = ["adana kebap", "lahmacun", "iskender", "pide", "corba", "pilav", "mercimek corbasi"]

    for rev in sample_reviews:
        aspects = aspect.extract_aspects(rev["text"], food_list)
        if aspects:
            print(f"  [{rev['review_id']}] {rev['text'][:50]}...")
            for a in aspects:
                print(f"       {a['food']:>18}: {a['sentiment']:>8} ({a['score']:.2f})")

    print(f"\nToplam: {len(sample_reviews)} yorum analiz edildi.")


if __name__ == "__main__":
    main()
