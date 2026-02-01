# CLAUDE.md - iyisiniye Proje Kayıt Dosyası

> Bu dosya projenin "hafızası"dır. Bağımsız Claude ile geliştirmeye devam ederken bu dosyayı referans al.

---

## Proje Bilgileri

| Alan | Değer |
|------|-------|
| **Proje Adı** | iyisiniye |
| **Açıklama** | Türkiye'nin yemek keşfetme platformu — "Restoranı değil, yediğini oyla" |
| **Oluşturma Tarihi** | 2026-02-01 |
| **Teknoloji Stack** | Turborepo + pnpm, Astro 5 + React Islands, Fastify + Zod v4, Drizzle ORM, PostgreSQL 17, Redis, Python NLP (BERT), Scrapy |
| **Proje Durumu** | MVP TAMAMLANDI |
| **Son Güncelleme** | 2026-02-01 |
| **GitHub** | https://github.com/FeritTasdildiren/iyisiniye |

---

## Teknoloji Kararları

| Teknoloji | Seçim | Gerekçe |
|-----------|-------|---------|
| Monorepo | Turborepo + pnpm workspaces | Çoklu paket yönetimi, paylaşımlı tipler, paralel build |
| Frontend | Astro 5 + React Islands + Tailwind CSS 4 | SSG ile hız, React ile interaktivite (Islands Architecture) |
| Backend | Fastify 5 + fastify-type-provider-zod + Zod v4 | Yüksek performans, tip güvenli validasyon |
| ORM | Drizzle ORM 0.38 | Type-safe SQL, hafif, PostgreSQL uyumlu |
| Veritabanı | PostgreSQL 17 + PostGIS + pg_trgm + unaccent | FTS, trigram fuzzy search, mekansal sorgular |
| Cache | Redis (ioredis) | API yanıt cache, graceful degradation |
| NLP | Python (BERT sentiment, food extraction, scoring) | Türkçe yemek yorumlarından anlam çıkarma |
| Scraping | Scrapy + Playwright stealth | Google Maps restoran ve yorum verisi toplama |
| Test (API) | Vitest | 41 birim/entegrasyon testi |
| Test (E2E) | Playwright | 41 uçtan uca test senaryosu |

---

## Geliştirme Kuralları

### Görev Yaşam Döngüsü Kaydı
Her yapılacak iş için aşağıdaki adımlar izlenmelidir:

1. **İŞ ÖNCESİ**: Görev "Aktif Görevler" tablosuna `PLANLANMIŞ` durumunda eklenir
2. **İŞ BAŞLANDIĞINDA**: Durum `DEVAM EDİYOR` olarak güncellenir, başlangıç tarihi yazılır
3. **İŞ TAMAMLANDIĞINDA**: Durum `TAMAMLANDI` olarak güncellenir, bitiş tarihi ve sonuç yazılır
4. **SORUN ÇIKTIĞINDA**: Durum `BLOKE` olarak güncellenir, sorun açıklaması eklenir

### Kod Standartları

- **Dil**: TypeScript (strict mode), Python 3.11+
- **Stil**: Prettier + ESLint (TS), Black + Ruff (Python)
- **Import**: ESM (`type: "module"` tüm paketlerde)
- **Zod**: Route dosyalarında `import { z } from "zod/v4"` kullan (v3 DEĞİL! fastify-type-provider-zod@6.1.0 Zod v4 gerektirir)
- **Cache**: Her API endpoint'te `X-Cache: HIT/MISS` header'ı döndür
- **Graceful Degradation**: Redis hatalarında sessizce devam et (try/catch, no throw)
- **Tailwind**: `font-poppins` başlıklarda, `text-orange-600` marka rengi, `text-slate-*` gövde metin
- **React Islands**: `client:load` (arama, filtre), `client:visible` (lazy bileşenler)
- **Accessibility**: `aria-label`, `aria-live="polite"`, `focus-visible:ring`, `role="progressbar"`

### Proje Yapısı

```
iyisiniye/
├── package.json                    # Monorepo root (pnpm + Turborepo)
├── turbo.json                      # Turborepo task config
├── pnpm-workspace.yaml             # Workspace tanımı
│
├── apps/
│   ├── api/                        # Fastify REST API (port 3001)
│   │   ├── package.json
│   │   ├── vitest.config.ts
│   │   └── src/
│   │       ├── index.ts            # buildApp() + start()
│   │       ├── lib/
│   │       │   ├── redis.ts        # ioredis singleton
│   │       │   └── cache.ts        # cacheGet/cacheSet/cacheDelete/cacheDeletePattern
│   │       ├── routes/
│   │       │   ├── search.ts       # GET /api/v1/search (FTS + trigram + PostGIS)
│   │       │   ├── restaurant.ts   # GET /api/v1/restaurant/:slug
│   │       │   ├── dish.ts         # GET /api/v1/dish/:slug
│   │       │   └── autocomplete.ts # GET /api/v1/autocomplete?q=
│   │       └── __tests__/
│   │           ├── setup.ts        # Mock altyapısı (Redis in-memory, Drizzle Proxy)
│   │           ├── search.test.ts
│   │           ├── restaurant.test.ts
│   │           ├── dish.test.ts
│   │           ├── autocomplete.test.ts
│   │           └── cache.test.ts
│   │
│   └── web/                        # Astro 5 Frontend (port 4321)
│       ├── package.json
│       ├── playwright.config.ts
│       ├── src/
│       │   ├── layouts/
│       │   │   └── BaseLayout.astro
│       │   ├── pages/
│       │   │   ├── index.astro          # Ana sayfa (Hero, Popüler Yemekler, Haftalık Yıldızlar)
│       │   │   ├── search.astro         # Arama sayfası (SearchIsland React Island)
│       │   │   └── restaurant/
│       │   │       └── [slug].astro     # Restoran detay sayfası
│       │   └── components/
│       │       ├── SearchIsland.tsx      # Arama + filtre + sonuçlar (client:load)
│       │       ├── RestaurantDetailIsland.tsx  # Restoran detay (client:load)
│       │       ├── VenueCard.tsx         # Restoran kartı
│       │       ├── DishRow.tsx           # Yemek satırı
│       │       ├── ScoreBadge.tsx        # Puan rozeti (yeşil/turuncu/kırmızı)
│       │       ├── FilterChip.tsx        # Filtre chip bileşeni
│       │       ├── Button.tsx            # Genel buton (primary/secondary/ghost)
│       │       └── EmptyState.tsx        # Boş durum gösterimi
│       └── e2e/
│           ├── search-flow.spec.ts       # 13 test
│           ├── filter-pagination.spec.ts # 16 test
│           └── error-states.spec.ts      # 12 test
│
├── packages/
│   ├── db/                         # Drizzle ORM Veritabanı Paketi
│   │   ├── package.json
│   │   └── src/
│   │       ├── index.ts            # DB bağlantısı (postgres.js driver)
│   │       ├── schema.ts           # 11 tablo + ilişkiler + indeksler
│   │       └── seed.ts             # Seed data scripti
│   │
│   └── shared/                     # Paylaşımlı tipler ve yardımcılar
│       └── src/
│           └── index.ts
│
├── nlp/                            # Python NLP Pipeline
│   ├── pyproject.toml
│   └── src/
│       ├── food_extractor.py       # Yemek adı çıkarma (regex + BERT)
│       ├── food_normalizer.py      # Yemek adı normalizasyonu (aliases, canonical)
│       ├── food_scorer.py          # Yemek puanlama (sentiment → 1-10 skor)
│       ├── item_filter.py          # Yemek/yemek-dışı sınıflandırma
│       ├── sentiment_analyzer.py   # BERT sentiment analizi (Türkçe)
│       ├── weak_labeler.py         # Zayıf etiketleme (bootstrap)
│       └── nlp_batch_pipeline.py   # Cron batch pipeline (tüm modüller birleşik)
│
├── scraper/                        # Scrapy Web Scraper
│   ├── requirements.txt
│   ├── scrapy.cfg
│   ├── config/                     # Scraper ayarları
│   ├── iyisiniye_scraper/          # Scrapy projesi
│   ├── scrapers/                   # Spider'lar (GM Liste + GM Yorum)
│   ├── middlewares/                 # Playwright stealth, proxy rotation
│   ├── matching/                   # Restoran eşleştirme
│   ├── nlp/                        # Scraper-specific NLP modülleri
│   └── tests/                      # Scraper testleri
│
└── docs/
    └── api-contracts-v1.ts         # API kontrat tanımları (TypeScript)
```

---

## Aktif Görevler

| Task ID | Açıklama | Durum | Başlangıç | Bitiş | Notlar |
|---------|----------|-------|-----------|-------|--------|
| - | Aktif görev yok | - | - | - | MVP tamamlandı |

---

## Tamamlanan Görevler

| Task ID | Açıklama | Sonuç | Tamamlanma | Notlar |
|---------|----------|-------|------------|--------|
| TASK-001~007 | Sprint 1: Altyapı & Scraping | OK | 2026-02-01 | Monorepo, DB, Scraper, NLP pipeline |
| TASK-008~019 | Sprint 1: Backend API & Veritabanı | OK | 2026-02-01 | 4 endpoint, FTS, cache, rate limiting |
| TASK-020~032 | Sprint 2: Frontend & Tasarım | OK | 2026-02-01 | Astro sayfaları, React bileşenleri, design system |
| TASK-033~040 | Sprint 3 Dalga 1-2: API & Microcopy | OK | 2026-02-01 | Dish endpoint, cache katmanı, microcopy |
| TASK-041~046 | Sprint 3 Dalga 3: Astro + UI | OK | 2026-02-01 | Astro sayfaları, UI bileşenleri, SearchIsland |
| TASK-047 | UI/UX Polish | OK | 2026-02-01 | 8 bileşen güncellendi, a11y iyileştirmeleri |
| TASK-048 | API Entegrasyon Testleri | OK | 2026-02-01 | 41 test, Zod v4 migration, mock altyapısı |
| TASK-049 | E2E Test Senaryoları | OK | 2026-02-01 | 41 Playwright senaryosu, 3 test dosyası |

---

## Stratejik Vizyon

**Konsept**: "Restoranı değil, yediğini oyla" — Geleneksel restoran puanlaması yerine yemek bazlı puanlama.

**Değer Önerisi**:
- Kullanıcılar spesifik yemekleri arayıp en iyi yapıldığı yerleri bulabilir
- NLP ile Google Maps yorumlarından otomatik yemek puanı çıkarılır
- Fuzzy arama (trigram), tam metin arama (FTS) ve konum bazlı arama (PostGIS)

**Gelir Modeli**: Sponsorlu restoran listeleme, premium API erişimi

---

## Veritabanı Şeması (11 Tablo)

| Tablo | Açıklama | Önemli Alanlar |
|-------|----------|----------------|
| `restaurants` | Restoran bilgileri | name, slug, location (PostGIS), cuisineType[], priceRange, overallScore |
| `restaurant_platforms` | Platform bağlantıları (GM) | platform, externalId, platformScore |
| `dishes` | Yemek tanımları | name, slug, canonicalName, category, aliases[], searchVector (tsvector) |
| `restaurant_dishes` | Restoran-yemek ilişkisi | avgSentiment, computedScore, totalMentions |
| `reviews` | Yorumlar | text, rating, processed (boolean) |
| `review_dish_mentions` | Yorum içi yemek bahisleri | sentiment, sentimentScore, extractionMethod |
| `food_mentions` | NLP yemek bahisleri | foodName, canonicalName, sentiment, confidence |
| `food_scores` | NLP yemek puanları | restaurantId + foodName (unique), score, reviewCount |
| `scrape_jobs` | Scrape görev kayıtları | platform, status, itemsScraped |
| `advertisements` | Reklam bilgileri | adType, isActive, impressions, clicks |
| `nlp_jobs` | NLP pipeline görevleri | reviewsProcessed, foodMentionsCreated, status |

**Aktif PostgreSQL Eklentileri**: PostGIS 3.5.2, pg_trgm 1.6, unaccent 1.1

**İndeksler**: GIN (FTS, trigram), GiST (PostGIS), B-tree (FK'lar), Partial (unprocessed reviews, active ads)

---

## API Endpoint'leri

| Method | Path | Açıklama | Cache TTL |
|--------|------|----------|-----------|
| GET | `/api/v1/search?q=&cuisine=&price_range=&min_score=&sort_by=&page=&limit=&lat=&lng=` | Restoran arama (FTS + trigram + PostGIS) | 300s |
| GET | `/api/v1/restaurant/:slug` | Restoran detay (bilgi + yemek puanları) | 600s |
| GET | `/api/v1/dish/:slug` | Yemek detay (hangi restoranlarda, sentiment) | 600s |
| GET | `/api/v1/autocomplete?q=` | Otomatik tamamlama (restoran + yemek) | 60s |
| GET | `/health` | Sağlık kontrolü | - |

**Cache Stratejisi**: MD5 hash key, `X-Cache: HIT/MISS` header, graceful degradation

---

## Mimari Kararlar

1. **Islands Architecture**: Astro SSG sayfalar + React interactive islands. Sadece interaktif bileşenler JavaScript yükler.
2. **Zod v4**: `fastify-type-provider-zod@6.1.0` Zod v4 core API kullanır. Route dosyalarında `import { z } from "zod/v4"` ZORUNLU.
3. **Cache Graceful Degradation**: Redis çökerse API çalışmaya devam eder, sadece cache atlanır.
4. **NLP Batch Pipeline**: Cron ile çalışır. İşlenmemiş yorumları bulur → yemek çıkarır → sentiment analizi → puan hesaplar.
5. **Scraper Stealth**: Playwright + stealth plugin + proxy rotation ile Google Maps scraping.
6. **FTS + Trigram Hibrit Arama**: `to_tsvector('turkish', ...)` ile FTS + `similarity() > 0.2` ile fuzzy birleşik sorgu.

---

## Bilinen Sorunlar ve Teknik Borç

| # | Açıklama | Öncelik | Durum |
|---|----------|---------|-------|
| 1 | Zod v3/v4 dual dependency — package.json'da `"zod": "^3.24.0"` ama route'lar `zod/v4` kullanıyor | ORTA | Workaround aktif |
| 2 | Ana sayfa arama kutusu henüz SearchIsland'a bağlı değil (statik HTML) | YÜKSEK | Bekliyor |
| 3 | PopularDishesCarousel henüz placeholder (React Island oluşturulmadı) | ORTA | Bekliyor |
| 4 | Sosyal medya ikonları placeholder | DÜŞÜK | Bekliyor |
| 5 | Kullanıcı auth sistemi yok (Giriş/Kayıt butonları non-functional) | YÜKSEK | Planlanmadı |
| 6 | SearchIsland API response formatı `data[]` ama bileşen `results[]` bekliyor | YÜKSEK | Düzeltilmeli |
| 7 | E2E testler henüz CI pipeline'ına entegre değil | ORTA | Bekliyor |
| 8 | NLP pipeline henüz cron job olarak ayarlanmadı (manuel çalıştırma) | ORTA | Bekliyor |

---

## Deployment Bilgileri

### Sunucu Erişimi

| Servis | URL / Host | Kullanıcı | Şifre |
|--------|------------|-----------|-------|
| CloudPanel | https://cloud.skystonetech.com | admin | SFj353!*?dd |
| SSH | 157.173.116.230 | root | E3Ry8H#bWkMGJc6y |
| Mailcow | https://mail.skystonetech.com | admin | SFj353!*?dd |

### Veritabanı Erişimi

| Ortam | Host | Port | Kullanıcı | Şifre | DB |
|-------|------|------|-----------|-------|----|
| Development | localhost (SSH tunnel) | 15433 | iyisiniye_app | IyS2026SecureDB | iyisiniye |
| Production | 157.173.116.230 | 5433 | iyisiniye_app | IyS2026SecureDB | iyisiniye |

### Ortam Değişkenleri (.env)

```env
# API
API_PORT=3001
API_HOST=0.0.0.0
NODE_ENV=development

# Veritabanı
DATABASE_URL=postgresql://iyisiniye_app:IyS2026SecureDB@localhost:15433/iyisiniye

# Redis
REDIS_URL=redis://localhost:6379

# CORS (production)
CORS_ORIGIN=https://iyisiniye.com
```

### Deploy Edilmedi
Proje henüz sunucuya deploy edilmemiştir. Tüm geliştirme lokalde yapılmıştır.
Deploy için gereken adımlar:
1. CloudPanel'de Node.js ve Python uygulaması oluştur
2. PostgreSQL veritabanını seed et (`pnpm db:migrate && pnpm db:push`)
3. Redis servisini başlat
4. API'yi PM2 ile ayağa kaldır
5. Web'i `astro build` ile derle, statik dosyaları serve et
6. Scraper'ı cron ile zamanla
7. NLP batch pipeline'ı cron ile zamanla

---

## İşlem Geçmişi

### 2026-02-01 Orkestrasyon ile MVP Geliştirme
- **İşlem**: 22 AI agent ile koordineli tam proje geliştirme
- **Yapılanlar**:
  - [x] Sprint 1: Monorepo + DB + Scraper + NLP (19 görev)
  - [x] Sprint 2: Frontend + Tasarım + API (13 görev)
  - [x] Sprint 3: Entegrasyon + Test + Polish (17 görev)
  - [x] Cross-agent prop uyumsuzlukları düzeltildi
  - [x] Zod v3→v4 migration tamamlandı
  - [x] 41 API testi + 41 E2E senaryosu yazıldı
- **Durum**: TAMAMLANDI (49/49 görev)

---

## Handoff Bilgileri

> Bu bölüm, projeye bağımsız Claude ile devam etmek için gerekli bilgileri içerir.

### Projeyi Çalıştırma

```bash
# 1. Bağımlılıkları yükle
cd /Users/ferit/Projeler/iyisiniye
pnpm install

# 2. Ortam değişkenlerini ayarla
cp .env.example .env  # (veya manuel oluştur, yukarıdaki değerleri kullan)

# 3. Veritabanı migration (PostgreSQL çalışıyor olmalı)
pnpm db:migrate

# 4. Redis başlat (brew veya docker)
redis-server

# 5. Geliştirme sunucuları (paralel)
pnpm dev
# → API: http://localhost:3001
# → Web: http://localhost:4321

# 6. Testleri çalıştır
pnpm test                          # Tüm testler (Vitest)
cd apps/web && npx playwright test # E2E testler

# 7. NLP Pipeline (Python)
cd nlp
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt  # veya: pip install -e .
python src/nlp_batch_pipeline.py

# 8. Scraper (Python)
cd scraper
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
scrapy crawl gm_list_spider       # Restoran listesi
scrapy crawl gm_review_spider     # Yorum toplama
```

### Geliştirmeye Devam Etme (Öncelik Sırasıyla)

1. **SearchIsland API response uyumu**: API `data[]` döndürüyor, bileşen `results[]` bekliyor — map'leme düzeltilmeli
2. **Ana sayfa arama kutusunu SearchIsland'a bağla**: Statik HTML'den React Island'a geçiş
3. **PopularDishesCarousel bileşeni**: Placeholder'ı gerçek carousel ile değiştir
4. **Kullanıcı auth sistemi**: Giriş/Kayıt akışı (JWT veya session tabanlı)
5. **CI/CD pipeline**: GitHub Actions ile test + deploy otomasyonu
6. **NLP cron entegrasyonu**: batch_pipeline.py'yi cron job olarak ayarla
7. **Production deploy**: CloudPanel + PM2 + Nginx reverse proxy

### Dikkat Edilmesi Gerekenler

1. **Zod Import**: Route dosyalarında `import { z } from "zod/v4"` kullan, `"zod"` DEĞİL. `fastify-type-provider-zod@6.1.0` Zod v4 core API (`schema._zod.run()`) gerektirir.
2. **Node.js Sürümü**: Minimum 20.0.0 gerekli
3. **pnpm Sürümü**: Minimum 9.0.0 gerekli
4. **PostgreSQL Eklentileri**: PostGIS, pg_trgm, unaccent aktif olmalı
5. **Test Mock'ları**: API testlerinde `setup.ts` Redis'i in-memory Map ile, Drizzle'ı Proxy mock ile simüle eder
6. **Scraper Etik Kullanım**: Google Maps ToS'a dikkat et, rate limiting ve proxy rotation aktif tut
7. **Cache Invalidation**: Yeni veri girişinde `cacheDeletePattern("search:*")` çağır
