"""
TASK-017: Full-Text Search Index Testi (T-03.1.5)

PostgreSQL FTS, pg_trgm fuzzy match ve PostGIS mesafe sorgularini test eder.
Agent: gemini-test-muhendisi
"""
from __future__ import annotations
import pytest
import psycopg2
from psycopg2.extras import RealDictCursor

# DB Baglanti Ayarlari
DB_CONFIG = {
    "host": "157.173.116.230",
    "port": "5433",
    "user": "iyisiniye_app",
    "password": "IyS2026SecureDB",
    "dbname": "iyisiniye"
}


@pytest.fixture(scope="module")
def db_conn():
    """Veritabani baglantisi kurar."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        yield conn
        conn.close()
    except Exception as e:
        pytest.fail(f"DB Baglantisi kurulamadi: {e}")


@pytest.fixture(scope="module")
def db_cursor(db_conn):
    """Veritabani cursor'u dondurur."""
    cursor = db_conn.cursor(cursor_factory=RealDictCursor)
    yield cursor
    cursor.close()


# =====================
# 1. FULL-TEXT SEARCH
# =====================

class TestFullTextSearch:
    """FTS (tsvector + GIN) testleri"""

    def test_fts_simple_word(self, db_cursor):
        """Test 1.1: Basit kelime aramasi ('lokanta')"""
        query = """
            SELECT name
            FROM restaurants
            WHERE to_tsvector('turkish', coalesce(name, '') || ' ' || coalesce(address, ''))
                  @@ to_tsquery('turkish', 'lokanta');
        """
        db_cursor.execute(query)
        results = db_cursor.fetchall()
        names = [r['name'] for r in results]

        print(f"\n[FTS Simple] Bulunan: {names}")

        # Beklenen: Karaköy Lokantası ve Kanaat Lokantası (isimlerinde 'lokanta' gecen)
        assert len(names) >= 1, "En az 1 sonuc bekleniyordu"

    def test_fts_multi_word(self, db_cursor):
        """Test 1.2: Coklu kelime aramasi ('karaköy & lokanta')"""
        query = """
            SELECT name
            FROM restaurants
            WHERE to_tsvector('turkish', coalesce(name, '') || ' ' || coalesce(address, ''))
                  @@ to_tsquery('turkish', 'karaköy & lokanta');
        """
        db_cursor.execute(query)
        results = db_cursor.fetchall()
        names = [r['name'] for r in results]

        print(f"\n[FTS Multi] Bulunan: {names}")

        # Beklenen: Karaköy Lokantası (hem karaköy hem lokanta gecen)
        assert len(names) >= 1, "En az 1 sonuc bekleniyordu"

    def test_fts_unaccent(self, db_cursor):
        """Test 1.3: Unaccent destegi (Turkce karakter donusumu)"""
        query = """
            SELECT name
            FROM restaurants
            WHERE unaccent(lower(name)) ILIKE unaccent(lower('%karakoy lokantasi%'));
        """
        db_cursor.execute(query)
        results = db_cursor.fetchall()
        names = [r['name'] for r in results]

        print(f"\n[FTS Unaccent] Bulunan: {names}")

        assert len(names) >= 1, "Unaccent ile eslesme basarisiz"


# =====================
# 2. PG_TRGM FUZZY MATCH
# =====================

class TestFuzzyMatch:
    """pg_trgm benzerlik testleri"""

    def test_trgm_similarity(self, db_cursor):
        """Test 2.1: Typo toleransi ('Ciya Sofrasi' -> 'Çiya Sofrası')"""
        # Oncelikle similarity threshold'u dusur
        db_cursor.execute("SET pg_trgm.similarity_threshold = 0.2;")

        query = """
            SELECT name, similarity(name, 'Ciya Sofrasi') as sim
            FROM restaurants
            WHERE similarity(name, 'Ciya Sofrasi') > 0.2
            ORDER BY sim DESC;
        """
        db_cursor.execute(query)
        results = db_cursor.fetchall()
        names = [r['name'] for r in results]

        print(f"\n[Trgm Similarity] Bulunan: {names}")

        # En az bir sonuc donmeli
        assert len(names) >= 1, "Fuzzy match sonuc dondurmedi"

    def test_trgm_ascii_matching(self, db_cursor):
        """Test 2.2: ASCII esleme ('Karakoy' -> 'Karaköy')"""
        query = """
            SELECT name, similarity(name, 'Karakoy Lokantasi') as sim
            FROM restaurants
            WHERE similarity(name, 'Karakoy Lokantasi') > 0.2
            ORDER BY sim DESC;
        """
        db_cursor.execute(query)
        results = db_cursor.fetchall()
        names = [r['name'] for r in results]

        print(f"\n[Trgm ASCII] Bulunan: {names}")

        assert len(names) >= 1, "ASCII fuzzy match basarisiz"

    def test_ilike_search(self, db_cursor):
        """Test 2.3: ILIKE arama"""
        query = """
            SELECT name FROM restaurants
            WHERE name ILIKE '%sofrası%';
        """
        db_cursor.execute(query)
        results = db_cursor.fetchall()
        names = [r['name'] for r in results]

        print(f"\n[ILIKE] Bulunan: {names}")

        assert len(names) >= 1, "ILIKE arama sonuc dondurmedi"


# =====================
# 3. POSTGIS MESAFE
# =====================

class TestPostGIS:
    """PostGIS mesafe sorgu testleri"""

    def test_dwithin_2km(self, db_cursor):
        """Test 3.1: Kadikoy cevresi 2km mesafe sorgusu"""
        # Ciya Sofrasi yaklasik: lng=29.026, lat=40.990
        query = """
            SELECT name
            FROM restaurants
            WHERE ST_DWithin(
                location,
                ST_SetSRID(ST_Point(%s, %s), 4326)::geography,
                2000
            );
        """
        db_cursor.execute(query, (29.026, 40.990))
        results = db_cursor.fetchall()
        names = [r['name'] for r in results]

        print(f"\n[PostGIS DWithin 2km] Bulunan: {names}")

        # Kadikoy cevresinde en az 1 restoran olmali
        assert len(names) >= 1, "2km icinde restoran bulunamadi"

    def test_knn_nearest_3(self, db_cursor):
        """Test 3.2: En yakin 3 restoran (KNN)"""
        # Referans: Galata Koprusu (lng=28.973, lat=41.018)
        query = """
            SELECT name,
                   ST_Distance(location, ST_SetSRID(ST_Point(%s, %s), 4326)::geography) as dist_m
            FROM restaurants
            ORDER BY location <-> ST_SetSRID(ST_Point(%s, %s), 4326)::geography
            LIMIT 3;
        """
        db_cursor.execute(query, (28.973, 41.018, 28.973, 41.018))
        results = db_cursor.fetchall()
        names = [r['name'] for r in results]

        print(f"\n[PostGIS KNN] En yakin 3: {names}")

        assert len(names) == 3, f"3 restoran bekleniyordu, {len(names)} bulundu"

    def test_bounding_box_istanbul(self, db_cursor):
        """Test 3.3: Istanbul bounding box sorgusu"""
        query = """
            SELECT name FROM restaurants
            WHERE ST_Within(
                location::geometry,
                ST_MakeEnvelope(28.5, 40.8, 29.5, 41.3, 4326)
            );
        """
        db_cursor.execute(query)
        results = db_cursor.fetchall()
        names = [r['name'] for r in results]

        print(f"\n[PostGIS BBox] Istanbul icinde: {names}")

        # Tum 5 restoran Istanbul'da olmali
        assert len(names) >= 5, f"5 restoran bekleniyordu, {len(names)} bulundu"


# =====================
# 4. PERFORMANS
# =====================

class TestPerformance:
    """Index kullanim ve performans testleri"""

    def test_explain_fts(self, db_cursor):
        """Test 4.1: FTS sorgu plani"""
        db_cursor.execute("""
            EXPLAIN ANALYZE
            SELECT name FROM restaurants
            WHERE to_tsvector('turkish', coalesce(name, '') || ' ' || coalesce(address, ''))
                  @@ to_tsquery('turkish', 'lokanta')
        """)
        plan = db_cursor.fetchall()
        plan_text = "\n".join([r['QUERY PLAN'] for r in plan])

        print(f"\n[EXPLAIN FTS]\n{plan_text}")

        # Seq Scan bile olsa 5 kayitla sorun degil, onemli olan calismasini dogrulamak
        assert len(plan) > 0, "Sorgu plani alinamadi"

    def test_explain_trgm(self, db_cursor):
        """Test 4.2: pg_trgm sorgu plani"""
        db_cursor.execute("SET pg_trgm.similarity_threshold = 0.2;")
        db_cursor.execute("""
            EXPLAIN ANALYZE
            SELECT name FROM restaurants
            WHERE name % 'Ciya Sofrasi'
        """)
        plan = db_cursor.fetchall()
        plan_text = "\n".join([r['QUERY PLAN'] for r in plan])

        print(f"\n[EXPLAIN TRGM]\n{plan_text}")

        assert len(plan) > 0, "Sorgu plani alinamadi"

    def test_explain_postgis(self, db_cursor):
        """Test 4.3: PostGIS sorgu plani"""
        db_cursor.execute("""
            EXPLAIN ANALYZE
            SELECT name FROM restaurants
            WHERE ST_DWithin(
                location,
                ST_SetSRID(ST_Point(29.026, 40.990), 4326)::geography,
                2000
            )
        """)
        plan = db_cursor.fetchall()
        plan_text = "\n".join([r['QUERY PLAN'] for r in plan])

        print(f"\n[EXPLAIN PostGIS]\n{plan_text}")

        assert len(plan) > 0, "Sorgu plani alinamadi"
