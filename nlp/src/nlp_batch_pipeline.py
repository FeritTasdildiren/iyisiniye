"""
nlp_batch_pipeline.py - NLP Batch Processing Pipeline

Tum NLP modullerini birlestiren toplu islem pipeline'i.
Islennemis yorumlari DB'den ceker, NLP analizi yapar ve sonuclari geri yazar.

Pipeline adimlari:
  1. DB'den islenmemis yorumlari cek (reviews.processed = false)
  2. WeakLabeler ile on etiketleme
  3. FoodExtractor ile yemek ismi cikarma
  4. ItemFilter ile icecek/yan urun filtreleme (FoodExtractor icinde)
  5. SentimentAnalyzer ile sentiment analizi (BERT + WeakLabeler ensemble)
  6. FoodScorer ile yemek bazli puanlama
  7. Sonuclari DB'ye yaz (food_mentions, food_scores)
  8. reviews.processed = true olarak guncelle

Kullanim:
  python nlp_batch_pipeline.py [--batch-size 100] [--dry-run] [--verbose]
"""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
import signal
import sys
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

# NLP modul importlari - ayni dizinden
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from food_extractor import FoodExtractor
from food_scorer import FoodScorer
from sentiment_analyzer import SentimentAnalyzer, AspectSentiment
from weak_labeler import WeakLabeler

# ── Loglama ──────────────────────────────────────────────────────────────

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

log_file = os.path.join(LOG_DIR, f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("nlp_pipeline")

# ── Sabitler ─────────────────────────────────────────────────────────────

LOCK_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".pipeline.lock")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
YEMEK_SOZLUK_PATH = os.path.join(DATA_DIR, "yemek_sozlugu.json")
FILTRE_SOZLUK_PATH = os.path.join(DATA_DIR, "filtre_sozlugu.json")

DEFAULT_BATCH_SIZE = 100

# DB konfigurasyon: Environment variable'lardan veya default degerler
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "5433")),
    "user": os.environ.get("DB_USER", "iyisiniye_app"),
    "password": os.environ.get("DB_PASSWORD", "IyS2026SecureDB"),
    "dbname": os.environ.get("DB_NAME", "iyisiniye"),
}


# ── File Lock ────────────────────────────────────────────────────────────


@contextmanager
def pipeline_lock():
    """Ayni anda iki pipeline calismasini engeller (file lock)."""
    lock_fd = None
    try:
        lock_fd = open(LOCK_FILE, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(f"PID: {os.getpid()}\nStarted: {datetime.now().isoformat()}\n")
        lock_fd.flush()
        logger.info("Pipeline lock alindi (PID: %d)", os.getpid())
        yield
    except BlockingIOError:
        logger.error("Baska bir pipeline zaten calisiyor! Lock dosyasi: %s", LOCK_FILE)
        if lock_fd:
            lock_fd.close()
        sys.exit(1)
    finally:
        if lock_fd:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
                os.remove(LOCK_FILE)
                logger.info("Pipeline lock serbest birakildi")
            except OSError:
                pass


# ── DB Yardimcilari ──────────────────────────────────────────────────────


def get_db_connection():
    """PostgreSQL baglantisi olusturur."""
    logger.info(
        "DB baglantisi: %s:%d/%s",
        DB_CONFIG["host"],
        DB_CONFIG["port"],
        DB_CONFIG["dbname"],
    )
    return psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        dbname=DB_CONFIG["dbname"],
    )


def ensure_tables_exist(conn) -> None:
    """Pipeline'in ihtiyac duydugu tablolari olusturur (yoksa)."""
    ddl = """
    CREATE TABLE IF NOT EXISTS food_mentions (
        id SERIAL PRIMARY KEY,
        review_id INTEGER NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
        food_name VARCHAR(255) NOT NULL,
        canonical_name VARCHAR(255),
        category VARCHAR(100),
        confidence DECIMAL(4,3),
        sentiment VARCHAR(10),
        sentiment_score DECIMAL(4,3),
        is_food BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_food_mentions_review_id ON food_mentions(review_id);
    CREATE INDEX IF NOT EXISTS idx_food_mentions_canonical_name ON food_mentions(canonical_name);
    CREATE INDEX IF NOT EXISTS idx_food_mentions_category ON food_mentions(category);

    CREATE TABLE IF NOT EXISTS food_scores (
        id SERIAL PRIMARY KEY,
        restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
        food_name VARCHAR(255) NOT NULL,
        score DECIMAL(4,2) NOT NULL,
        review_count INTEGER NOT NULL DEFAULT 0,
        confidence DECIMAL(4,3),
        sentiment_distribution JSONB,
        last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(restaurant_id, food_name)
    );
    CREATE INDEX IF NOT EXISTS idx_food_scores_restaurant_id ON food_scores(restaurant_id);
    CREATE INDEX IF NOT EXISTS idx_food_scores_score ON food_scores(score);

    CREATE TABLE IF NOT EXISTS nlp_jobs (
        id SERIAL PRIMARY KEY,
        started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        completed_at TIMESTAMPTZ,
        reviews_processed INTEGER NOT NULL DEFAULT 0,
        food_mentions_created INTEGER NOT NULL DEFAULT 0,
        food_scores_updated INTEGER NOT NULL DEFAULT 0,
        status VARCHAR(20) NOT NULL DEFAULT 'running',
        error_log TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_nlp_jobs_status ON nlp_jobs(status);
    """
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()
    logger.info("Tablo kontrolleri tamamlandi (CREATE IF NOT EXISTS)")


def fetch_unprocessed_reviews(conn, batch_size: int) -> list[dict]:
    """Islenmemis yorumlari DB'den ceker.

    reviews.processed = false olan yorumlari, restaurant bilgisiyle birlikte getirir.
    """
    query = """
        SELECT r.id AS review_id,
               r.text,
               r.rating AS star_rating,
               r.restaurant_platform_id,
               rp.restaurant_id
        FROM   reviews r
        JOIN   restaurant_platforms rp ON r.restaurant_platform_id = rp.id
        WHERE  r.processed = false
          AND  r.text IS NOT NULL
          AND  r.text != ''
        ORDER BY r.id
        LIMIT  %s
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, (batch_size,))
        rows = [dict(r) for r in cur.fetchall()]
    logger.info("DB'den %d islenmemis yorum cekildi", len(rows))
    return rows


def create_nlp_job(conn) -> int:
    """Yeni NLP job kaydı olusturur, ID'sini dondurur."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO nlp_jobs (started_at, status) VALUES (NOW(), 'running') RETURNING id"
        )
        job_id = cur.fetchone()[0]
    conn.commit()
    logger.info("NLP job olusturuldu: %d", job_id)
    return job_id


def update_nlp_job(
    conn,
    job_id: int,
    status: str,
    reviews_processed: int = 0,
    food_mentions_created: int = 0,
    food_scores_updated: int = 0,
    error_log: str | None = None,
) -> None:
    """NLP job kaydini gunceller."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE nlp_jobs
            SET completed_at = NOW(),
                reviews_processed = %s,
                food_mentions_created = %s,
                food_scores_updated = %s,
                status = %s,
                error_log = %s
            WHERE id = %s
            """,
            (reviews_processed, food_mentions_created, food_scores_updated, status, error_log, job_id),
        )
    conn.commit()


def insert_food_mentions(conn, mentions: list[dict]) -> int:
    """food_mentions tablosuna toplu ekleme yapar."""
    if not mentions:
        return 0
    query = """
        INSERT INTO food_mentions
            (review_id, food_name, canonical_name, category, confidence,
             sentiment, sentiment_score, is_food)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    rows = [
        (
            m["review_id"],
            m["food_name"],
            m.get("canonical_name"),
            m.get("category"),
            m.get("confidence"),
            m.get("sentiment"),
            m.get("sentiment_score"),
            m.get("is_food", True),
        )
        for m in mentions
    ]
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, query, rows, page_size=100)
    conn.commit()
    return len(rows)


def upsert_food_scores(conn, scores: list[dict]) -> int:
    """food_scores tablosuna UPSERT yapar (restaurant_id + food_name benzersiz)."""
    if not scores:
        return 0
    query = """
        INSERT INTO food_scores
            (restaurant_id, food_name, score, review_count, confidence,
             sentiment_distribution, last_updated)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (restaurant_id, food_name)
        DO UPDATE SET
            score = EXCLUDED.score,
            review_count = EXCLUDED.review_count,
            confidence = EXCLUDED.confidence,
            sentiment_distribution = EXCLUDED.sentiment_distribution,
            last_updated = NOW()
    """
    rows = [
        (
            s["restaurant_id"],
            s["food_name"],
            s["score"],
            s["review_count"],
            s.get("confidence"),
            json.dumps(s.get("sentiment_distribution", {})),
        )
        for s in scores
    ]
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, query, rows, page_size=100)
    conn.commit()
    return len(rows)


def mark_reviews_processed(conn, review_ids: list[int]) -> None:
    """Yorumlari islenmis olarak isaretler."""
    if not review_ids:
        return
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE reviews SET processed = true WHERE id = ANY(%s)",
            (review_ids,),
        )
    conn.commit()
    logger.info("%d yorum 'processed' olarak isaretlendi", len(review_ids))


# ── Pipeline Adimlari ────────────────────────────────────────────────────


class NLPBatchPipeline:
    """Tum NLP modullerini birlestiren batch pipeline."""

    def __init__(self, batch_size: int = DEFAULT_BATCH_SIZE, dry_run: bool = False):
        self.batch_size = batch_size
        self.dry_run = dry_run

        # Istatistikler
        self.stats = {
            "reviews_fetched": 0,
            "reviews_processed": 0,
            "reviews_failed": 0,
            "food_mentions_total": 0,
            "food_scores_updated": 0,
            "step_times": {},
        }

        logger.info("Pipeline baslatiliyor (batch_size=%d, dry_run=%s)", batch_size, dry_run)

    def _init_models(self) -> None:
        """NLP modellerini yukler."""
        t0 = time.time()

        logger.info("FoodExtractor yukleniyor...")
        self.food_extractor = FoodExtractor(YEMEK_SOZLUK_PATH, FILTRE_SOZLUK_PATH)

        logger.info("SentimentAnalyzer yukleniyor (BERT model)...")
        self.sentiment_analyzer = SentimentAnalyzer()
        self.aspect_sentiment = AspectSentiment(self.sentiment_analyzer)

        logger.info("FoodScorer yukleniyor...")
        self.food_scorer = FoodScorer(min_reviews=3, confidence_threshold=0.5)

        elapsed = time.time() - t0
        self.stats["step_times"]["model_loading"] = round(elapsed, 2)
        logger.info("Tum modeller yuklendi (%.1f sn)", elapsed)

    def _process_single_review(self, review: dict) -> dict[str, Any]:
        """Tek bir yorumu tum pipeline adimlarindan gecirir.

        Returns:
            {
                review_id, restaurant_id, food_mentions: [...],
                sentiment: {...}, food_scores_data: [...]
            }
        """
        review_id = review["review_id"]
        text = review.get("text", "")
        star_rating = review.get("star_rating") or 3
        restaurant_id = review.get("restaurant_id")

        # 1. FoodExtractor: Yemek isimlerini cikar
        extraction_result = self.food_extractor.extract_from_review({
            "review_id": review_id,
            "text": text,
            "star_rating": star_rating,
        })
        foods = extraction_result.get("foods", [])

        # 2. SentimentAnalyzer: Genel sentiment
        sentiment_result = self.sentiment_analyzer.analyze_review({
            "review_id": review_id,
            "text": text,
            "star_rating": star_rating,
        })

        # 3. AspectSentiment: Yemek bazli sentiment
        food_names = [f["canonical"] for f in foods if f.get("is_food")]
        aspect_map = self.aspect_sentiment.map_sentiments_to_foods(text, food_names)

        # 4. food_mentions kayitlari olustur
        mentions = []
        for food in foods:
            canonical = food.get("canonical", "")
            aspect = aspect_map.get(canonical, {})
            mentions.append({
                "review_id": review_id,
                "food_name": food.get("matched_text", canonical),
                "canonical_name": canonical,
                "category": food.get("category"),
                "confidence": food.get("score", 0.0) / 100.0,  # 0-100 → 0-1
                "sentiment": aspect.get("sentiment", sentiment_result.get("final_sentiment")),
                "sentiment_score": aspect.get("score", sentiment_result.get("confidence")),
                "is_food": food.get("is_food", True),
            })

        # 5. FoodScorer icin veri hazirla (food_sentiments formati)
        food_sentiments = []
        for food in foods:
            if not food.get("is_food"):
                continue
            canonical = food["canonical"]
            aspect = aspect_map.get(canonical, {})
            food_sentiments.append({
                "food": canonical,
                "sentiment": aspect.get("sentiment", sentiment_result.get("final_sentiment")),
                "score": aspect.get("score", sentiment_result.get("confidence", 0.5)),
                "confidence": sentiment_result.get("confidence", 0.5),
                "star_rating": star_rating,
            })

        return {
            "review_id": review_id,
            "restaurant_id": restaurant_id,
            "food_mentions": mentions,
            "sentiment": sentiment_result,
            "food_sentiments": food_sentiments,
            "star_rating": star_rating,
        }

    def run(self) -> dict[str, Any]:
        """Pipeline'i calistirir."""
        pipeline_start = time.time()
        conn = None
        job_id = None

        try:
            # DB baglantisi
            conn = get_db_connection()
            ensure_tables_exist(conn)

            # NLP job olustur
            if not self.dry_run:
                job_id = create_nlp_job(conn)

            # Modelleri yukle
            self._init_models()

            # Toplam islenmemis yorum sayisi
            total_processed = 0
            total_mentions = 0
            total_scores_updated = 0
            error_log_lines: list[str] = []

            while True:
                # Batch cek
                t_fetch = time.time()
                reviews = fetch_unprocessed_reviews(conn, self.batch_size)
                self.stats["step_times"].setdefault("fetch_reviews", []).append(
                    round(time.time() - t_fetch, 2)
                )

                if not reviews:
                    logger.info("Islenmemis yorum kalmadi, pipeline tamamlandi.")
                    break

                self.stats["reviews_fetched"] += len(reviews)
                logger.info("Batch isleniyor: %d yorum", len(reviews))

                # Her yorumu isle
                batch_mentions: list[dict] = []
                batch_food_sentiments_by_restaurant: dict[int, list[dict]] = {}
                processed_ids: list[int] = []

                for review in reviews:
                    try:
                        result = self._process_single_review(review)
                        batch_mentions.extend(result["food_mentions"])
                        processed_ids.append(result["review_id"])

                        # Restoran bazli food_sentiments topla
                        rid = result["restaurant_id"]
                        if rid:
                            batch_food_sentiments_by_restaurant.setdefault(rid, []).append({
                                "star_rating": result["star_rating"],
                                "food_sentiments": result["food_sentiments"],
                            })

                        self.stats["reviews_processed"] += 1

                    except Exception as e:
                        self.stats["reviews_failed"] += 1
                        err_msg = f"Review {review.get('review_id')}: {e}"
                        logger.warning("Yorum isleme hatasi: %s", err_msg)
                        error_log_lines.append(err_msg)
                        # Tek yorum hatasi batch'i durdurmasin
                        processed_ids.append(review["review_id"])
                        continue

                if self.dry_run:
                    logger.info(
                        "[DRY RUN] %d mention, %d processed (DB'ye yazilmadi)",
                        len(batch_mentions),
                        len(processed_ids),
                    )
                    total_processed += len(processed_ids)
                    total_mentions += len(batch_mentions)
                    continue

                # DB'ye yaz: food_mentions
                t_write = time.time()
                if batch_mentions:
                    inserted = insert_food_mentions(conn, batch_mentions)
                    total_mentions += inserted
                    logger.info("%d food_mention eklendi", inserted)

                # DB'ye yaz: food_scores (restoran bazli)
                for restaurant_id, review_data in batch_food_sentiments_by_restaurant.items():
                    scores_data = self._calculate_restaurant_scores(restaurant_id, review_data)
                    if scores_data:
                        updated = upsert_food_scores(conn, scores_data)
                        total_scores_updated += updated

                # Yorumlari islenmis olarak isaretle
                mark_reviews_processed(conn, processed_ids)
                total_processed += len(processed_ids)

                self.stats["step_times"].setdefault("db_write", []).append(
                    round(time.time() - t_write, 2)
                )

                logger.info(
                    "Batch tamamlandi: %d/%d yorum islendi, %d mention",
                    len(processed_ids),
                    len(reviews),
                    len(batch_mentions),
                )

            # Pipeline tamamlandi
            self.stats["food_mentions_total"] = total_mentions
            self.stats["food_scores_updated"] = total_scores_updated

            if job_id and not self.dry_run:
                error_text = "\n".join(error_log_lines) if error_log_lines else None
                update_nlp_job(
                    conn,
                    job_id,
                    status="completed",
                    reviews_processed=total_processed,
                    food_mentions_created=total_mentions,
                    food_scores_updated=total_scores_updated,
                    error_log=error_text,
                )

            elapsed = time.time() - pipeline_start
            self.stats["step_times"]["total"] = round(elapsed, 2)
            self._log_summary(elapsed)

            return self.stats

        except Exception as e:
            logger.error("Pipeline kritik hata: %s\n%s", e, traceback.format_exc())
            if job_id and conn and not self.dry_run:
                try:
                    update_nlp_job(
                        conn,
                        job_id,
                        status="failed",
                        reviews_processed=total_processed if "total_processed" in dir() else 0,
                        error_log=str(e),
                    )
                except Exception:
                    pass
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def _calculate_restaurant_scores(
        self,
        restaurant_id: int,
        review_data: list[dict],
    ) -> list[dict]:
        """Bir restoranin yemek puanlarini hesaplar.

        Mevcut batch'teki verilerle birlikte daha once biriktirilmis
        verileri de iceren kapsamli bir puanlama yapar.
        """
        food_scores = self.food_scorer.calculate_restaurant_food_scores(review_data)

        scores_list = []
        for food_name, data in food_scores.items():
            scores_list.append({
                "restaurant_id": restaurant_id,
                "food_name": food_name,
                "score": data["score_1_10"],
                "review_count": data["review_count"],
                "confidence": data.get("confidence", 0.0),
                "sentiment_distribution": data.get("sentiment_distribution", {}),
            })

        return scores_list

    def _log_summary(self, elapsed: float) -> None:
        """Pipeline ozet logunu yazar."""
        logger.info("=" * 60)
        logger.info("    NLP PIPELINE OZETI")
        logger.info("=" * 60)
        logger.info("Toplam sure        : %.1f sn", elapsed)
        logger.info("Yorumlar cekildi   : %d", self.stats["reviews_fetched"])
        logger.info("Yorumlar islendi   : %d", self.stats["reviews_processed"])
        logger.info("Yorumlar basarisiz : %d", self.stats["reviews_failed"])
        logger.info("Food mentions      : %d", self.stats["food_mentions_total"])
        logger.info("Food scores gunc.  : %d", self.stats["food_scores_updated"])
        logger.info("Model yukleme      : %s sn", self.stats["step_times"].get("model_loading", "?"))
        logger.info("Dry run            : %s", self.dry_run)
        logger.info("=" * 60)


# ── CLI ──────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="iyisiniye NLP Batch Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Her seferde islenecek yorum sayisi (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB'ye yazmadan pipeline'i calistir (test icin)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Ayrintili log seviyesi (DEBUG)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    logger.info("=" * 60)
    logger.info("iyisiniye NLP Batch Pipeline baslatiliyor")
    logger.info("Tarih  : %s", datetime.now().isoformat())
    logger.info("PID    : %d", os.getpid())
    logger.info("Batch  : %d", args.batch_size)
    logger.info("Dry run: %s", args.dry_run)
    logger.info("Log    : %s", log_file)
    logger.info("=" * 60)

    with pipeline_lock():
        pipeline = NLPBatchPipeline(
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )
        stats = pipeline.run()

    # Basarili cikis
    if stats["reviews_failed"] > 0:
        logger.warning(
            "Pipeline tamamlandi, ancak %d yorum basarisiz",
            stats["reviews_failed"],
        )
        sys.exit(2)  # Kismen basarili
    else:
        logger.info("Pipeline basariyla tamamlandi.")
        sys.exit(0)


if __name__ == "__main__":
    main()
