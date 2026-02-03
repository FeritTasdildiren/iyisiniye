# CLAUDE.md - iyisiniye Proje Kayıt Dosyası

> Bu dosya projenin "hafızası"dır. Bağımsız Claude ile geliştirmeye devam ederken bu dosyayı referans al.

---

## ⛔ Proje Hafıza Sistemi — İLK OKUNAN BÖLÜM

**Bu projeye devam eden her LLM ve geliştirici aşağıdaki 3 dosyayı birlikte kullanmak ZORUNDADIR:**

| Dosya | Konum | Amaç | Güncelleme Sıklığı |
|-------|-------|------|-------------------|
| **CLAUDE.md** | `iyisiniye/CLAUDE.md` | Projenin güncel durumu, talimatlar, teknik dokümantasyon | Her yeni özellik, endpoint, bağımlılık, mimari değişiklikte |
| **reports.md** | `iyisiniye/reports.md` | İş bazlı kronolojik kayıt (ne yapıldı, ne zaman) | Her işe başlarken, devam ederken ve bitirince |
| **experience.md** | `iyisiniye/experience.md` | Birikimli tecrübe ve öğrenimler (kararlar, hatalar, pattern'ler) | Her görev tamamlandığında |

**Başlangıç Prosedürü (her oturum başında):**
1. `CLAUDE.md`'yi oku — projeyi, kuralları ve güncel durumu öğren
2. `reports.md`'yi oku — son yapılan işi ve yarım kalan şeyleri kontrol et
3. `experience.md`'yi oku — önceki tecrübelerden faydalan, aynı hataları tekrarlama

**⚠️ Bu dosyalar olmadan geliştirmeye başlama. Yoksa oluştur, varsa oku.**

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

### Çalışma Raporu Sistemi (reports.md) — ZORUNLU

> **Bu talimat, bu projeye devam eden her LLM ve geliştirici için ZORUNLUDUR.**

Proje üzerinde yapılan **her derleme, düzenleme, geliştirme, hata düzeltme ve konfigürasyon değişikliği** kayıt altına alınmalıdır. Bu kayıtlar proje ana klasöründeki `reports.md` dosyasında tutulur.

**Amaç:** Herhangi bir çökme (crash), bağlam kaybı veya oturum kesintisi durumunda yapılan işlerin unutulmaması ve yarım kalmaması. Bu dosya, kaldığın yerden devam etmen için tek güvenilir kaynaktır.

#### Dosya Konumu
```
iyisiniye/reports.md
```

#### Ne Zaman Yazılır?
1. **İŞE BAŞLARKEN** — Neyi, neden yapacağını yaz (BAŞLANGIÇ kaydı)
2. **İŞ SIRASINDA** — Önemli kararlar, karşılaşılan sorunlar, değiştirilen dosyalar (DEVAM kaydı)
3. **İŞ BİTİNCE** — Ne yapıldı, sonuç ne oldu, test edildi mi (TAMAMLANDI kaydı)

#### Kayıt Formatı

Her iş birimi için aşağıdaki format kullanılır:

```markdown
---

## [RAPOR-XXX] Kısa Başlık
| Alan | Değer |
|------|-------|
| **Durum** | 🟡 BAŞLANDI / 🔵 DEVAM EDİYOR / 🟢 TAMAMLANDI / 🔴 BAŞARISIZ |
| **Başlangıç** | YYYY-MM-DD HH:MM |
| **Bitiş** | YYYY-MM-DD HH:MM (veya -) |
| **Etkilenen Dosyalar** | dosya1.ts, dosya2.tsx, ... |

### Hedef
Bu işin amacı ve kapsamı (1-2 cümle).

### Yapılanlar
- [x] Tamamlanan adım
- [x] Tamamlanan adım
- [ ] Henüz yapılmayan adım (varsa)

### Kararlar ve Notlar
- Neden X yerine Y tercih edildi?
- Karşılaşılan sorun ve çözümü
- Dikkat edilmesi gereken bağımlılıklar

### Sonuç
İşin son durumu. Test edildi mi? Çalışıyor mu? Bilinen kısıtlamalar var mı?
```

#### Kurallar
1. **Her işe başlamadan ÖNCE** `reports.md` dosyasına BAŞLANGIÇ kaydı yazılır — bu adım atlanamaz
2. Rapor numarası sıralı artar: RAPOR-001, RAPOR-002, ...
3. Dosya yoksa oluşturulur, varsa sonuna eklenir (mevcut kayıtlar asla silinmez)
4. Durum emoji'leri ile görsel takip kolaylaştırılır:
   - 🟡 BAŞLANDI — İşe yeni başlandı
   - 🔵 DEVAM EDİYOR — Aktif olarak çalışılıyor
   - 🟢 TAMAMLANDI — Başarıyla bitirildi
   - 🔴 BAŞARISIZ — Hata ile sonlandı, neden belirtilmeli
5. Crash sonrası bu dosyayı oku, son kaydın durumuna bak, kaldığın yerden devam et
6. Küçük düzeltmeler (typo, tek satır değişiklik) bile kayıt altına alınır — hiçbir değişiklik kayıtsız yapılmaz
7. `Etkilenen Dosyalar` alanı değiştirilen her dosyayı listeler (code review ve rollback için kritik)

#### Örnek

```markdown
# Çalışma Raporu — iyisiniye

> Bu dosya projede yapılan tüm işlerin kronolojik kaydıdır.
> Crash veya oturum kaybında bu dosyadan devam edilir.

---

## [RAPOR-001] Redis cache TTL sürelerini optimize et
| Alan | Değer |
|------|-------|
| **Durum** | 🟢 TAMAMLANDI |
| **Başlangıç** | 2025-07-15 14:30 |
| **Bitiş** | 2025-07-15 15:45 |
| **Etkilenen Dosyalar** | apps/api/src/lib/cache.ts, apps/api/src/routes/search.ts |

### Hedef
Search endpoint'indeki cache TTL'lerini 5dk'dan 15dk'ya çıkararak gereksiz DB sorgularını azaltmak.

### Yapılanlar
- [x] cache.ts'deki DEFAULT_TTL değeri 300'den 900'e güncellendi
- [x] search.ts'de route-specific TTL override kaldırıldı
- [x] Mevcut testler güncellendi ve geçti

### Kararlar ve Notlar
- 15dk seçildi çünkü restoran verisi sık değişmiyor, 1 saat çok uzun olurdu
- autocomplete endpoint'i 5dk'da bırakıldı (daha dinamik veri)

### Sonuç
Cache hit oranı %60'tan %82'ye çıktı. Tüm testler geçiyor. Bilinen kısıtlama yok.
```

---

### Tecrübe Kayıt Sistemi (experience.md) — ZORUNLU

> **Her görev tamamlandığında öğrenimler bu dosyaya yazılır. Birikimli bir bilgi bankasıdır, asla silinmez.**

**Amaç:** Aynı hataları tekrarlamamak, iyi çalışan pattern'leri hatırlamak ve projeye özgü bilgi birikimini korumak.

#### Dosya Konumu
```
iyisiniye/experience.md
```

#### Kayıt Formatı
```markdown
## [Tarih] - [Kısa Başlık]

### Görev: [Ne yapıldığı]
- [KARAR] Ne kararı verildi → Sonuç ne oldu
- [HATA] Hangi hata yapıldı → Nasıl çözüldü
- [PATTERN] Hangi yaklaşım işe yaradı → Neden
- [UYARI] Nelere dikkat edilmeli → Neden
```

#### Kurallar
1. Her görev tamamlandığında en az 1 tecrübe kaydı yazılır — bu zorunludur
2. Dosya yoksa oluşturulur, varsa sonuna eklenir (mevcut kayıtlar asla silinmez)
3. Sadece gerçek değer taşıyan bilgiler yazılır ("npm install çalıştırdım" gibi kayıtlar değersizdir)
4. 4 etiket kullanılır: `[KARAR]`, `[HATA]`, `[PATTERN]`, `[UYARI]`
5. Her oturum başında bu dosya okunarak önceki tecrübelerden faydalanılır
6. Crash sonrası bu dosya context'e yüklenerek bilgi kaybı önlenir

---

### ⛔ Sürekli Güncelleme Talimatları — ZORUNLU

**Bu CLAUDE.md dosyası canlı bir dokümandır. Proje geliştikçe bu dosya da güncellenmelidir.**

Aşağıdaki değişikliklerden herhangi biri yapıldığında, ilgili CLAUDE.md bölümü **aynı oturumda** güncellenir:

| Değişiklik Türü | Güncellenecek CLAUDE.md Bölümü |
|-----------------|-------------------------------|
| Yeni API endpoint eklendi | Detaylı Teknik Dokümantasyon → 6. API Dokümantasyonu |
| Yeni ortam değişkeni eklendi | Detaylı Teknik Dokümantasyon → 3. Ortam Değişkenleri |
| Yeni bağımlılık (npm/pip) eklendi | Detaylı Teknik Dokümantasyon → 1. Ön Gereksinimler |
| Veritabanı şeması değişti | Detaylı Teknik Dokümantasyon → 4. Veritabanı Yönetimi |
| Yeni servis/port eklendi | Detaylı Teknik Dokümantasyon → 5. Servisleri Çalıştırma |
| Mimari karar alındı | Mimari Kararlar |
| Yeni teknik borç oluştu | Bilinen Sorunlar ve Teknik Borç |
| Deployment süreci değişti | Detaylı Teknik Dokümantasyon → 10. Deployment |
| Yeni 3. parti servis entegre edildi | Detaylı Teknik Dokümantasyon → 8. Üçüncü Parti Servisler |
| Klasör yapısında önemli değişiklik | Detaylı Teknik Dokümantasyon → 7. Proje Klasör Yapısı |
| Teknoloji stack'e ekleme/değişiklik | Teknoloji Kararları tablosu |

**Kural:** Kod değişikliği yapıp CLAUDE.md'yi güncellememek YASAKTIR. Eğer "bu değişiklik dokümantasyonu etkiler mi?" sorusunun cevabı "evet" veya "belki" ise, GÜNCELLE.

---

### ⛔ Git & Deployment Güvenlik Kuralları

**Git repoları özeldir (private), tüm proje dosyaları güvenle barındırılabilir. Ancak sunucuya gönderim konusunda dikkatli olunmalıdır.**

#### Git'e Yüklenmeli (repo'da olmalı)
- `CLAUDE.md` — ✅ Git'e yüklenir
- `reports.md` — ✅ Git'e yüklenir
- `experience.md` — ✅ Git'e yüklenir
- `.env.example` — ✅ Git'e yüklenir (gerçek değerler olmadan)
- Tüm kaynak kod — ✅ Git'e yüklenir

#### Sunucuya Gönderilmemeli (deployment'ta hariç tutulmalı)
Aşağıdaki dosyalar **sunucuya/production ortamına deploy edilmemelidir**:

```
# Deployment sırasında hariç tutulacak dosyalar
CLAUDE.md
reports.md
experience.md
```

**Nasıl hariç tutulur:**
- **rsync ile deploy:** `--exclude='CLAUDE.md' --exclude='reports.md' --exclude='experience.md'`
- **Docker:** `.dockerignore` dosyasına ekle
- **CI/CD pipeline:** Build artifact'larından çıkar
- **CloudPanel/FTP:** Manuel olarak yükleme

**Kural:** Bu dosyalar geliştirme ve bilgi yönetimi içindir. Production sunucusunda yer kaplamasına ve potansiyel bilgi sızıntısına gerek yoktur.

---

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

---

## Detaylı Teknik Dokümantasyon

> Bu bölüm, projeyi sıfırdan ayağa kaldıracak veya geliştirmeye devam edecek bir yazılımcı ya da LLM için hazırlanmış kapsamlı operasyonel dokümandır.

### 1. Ön Gereksinimler (Prerequisites)

| Yazılım | Minimum Versiyon | Kurulum Notu |
|---------|-----------------|--------------|
| Node.js | 20.x | `nvm install 20` veya `brew install node@20` |
| pnpm | 9.0.0+ | `npm install -g pnpm@9` veya `corepack enable && corepack prepare pnpm@9.15.4` |
| Docker & Docker Compose | Son sürüm | PostgreSQL ve Redis container'ları için gerekli |
| Python | 3.11+ | NLP pipeline ve Scraper için (`pyenv install 3.11`) |
| Playwright | 1.49+ | E2E testler ve Scraper için (`npx playwright install chromium`) |

### 2. Projeyi Sıfırdan Kurma (Fresh Setup)

```bash
# 1. Repoyu klonla
git clone https://github.com/FeritTasdildiren/iyisiniye.git
cd iyisiniye

# 2. Node.js bağımlılıklarını yükle (pnpm monorepo)
pnpm install

# 3. Docker servislerini başlat (PostgreSQL 17 + PostGIS + Redis 7)
docker compose up -d
# PostgreSQL → localhost:15433
# Redis → localhost:6380

# 4. Docker container'ların hazır olduğunu doğrula
docker compose ps
# Her iki container da "healthy" olmalı

# 5. Ortam değişkenlerini ayarla
cp .env.example apps/api/.env
cp .env.example packages/db/.env
# NOT: .env.example'daki varsayılan değerler Docker kurulumu ile uyumludur
# Production için DATABASE_URL ve şifreleri değiştirin

# 6. Veritabanı migration'ını çalıştır (tablolar + indeksler + extension'lar)
pnpm db:migrate
# Bu komut: drizzle-kit migrate → packages/db/src/migrations/ altındaki SQL'leri çalıştırır
# PostGIS, pg_trgm, unaccent extension'ları docker/init-extensions.sql ile otomatik yüklenir

# 7. (Opsiyonel) Veritabanına doğrudan bağlanıp kontrol et
docker exec -it iyisiniye-postgres psql -U iyisiniye_app -d iyisiniye
# \dt → 11 tablo görmeli
# \dx → postgis, pg_trgm, unaccent görmeli

# 8. Python NLP ortamını kur
cd nlp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# BERT modeli ilk çalışmada otomatik indirilir (~500MB)
deactivate
cd ..

# 9. Python Scraper ortamını kur
cd scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium  # Headless tarayıcı
deactivate
cd ..

# 10. Tüm servisleri başlat (development)
pnpm dev
# → API: http://localhost:3001 (Fastify + hot-reload via tsx watch)
# → Web: http://localhost:4321 (Astro dev server)
# → API proxy: Astro, /api isteklerini otomatik olarak localhost:3001'e yönlendirir
```

### 3. Ortam Değişkenleri (Environment Variables)

| Değişken | Açıklama | Örnek Değer | Zorunlu | Nerede Kullanılıyor |
|----------|----------|-------------|---------|---------------------|
| `DATABASE_URL` | PostgreSQL bağlantı string'i | `postgresql://iyisiniye_app:IyS2026SecureDB@127.0.0.1:15433/iyisiniye` | Evet | `packages/db`, `apps/api` |
| `DATABASE_HOST` | DB host adresi | `127.0.0.1` | Evet | `packages/db` (drizzle.config.ts) |
| `DATABASE_PORT` | DB port numarası | `15433` (dev) / `5433` (prod) | Evet | `packages/db` |
| `DATABASE_NAME` | Veritabanı adı | `iyisiniye` | Evet | `packages/db` |
| `DATABASE_USER` | DB kullanıcı adı | `iyisiniye_app` | Evet | `packages/db` |
| `DATABASE_PASSWORD` | DB şifresi | `IyS2026SecureDB` | Evet | `packages/db` |
| `REDIS_URL` | Redis bağlantı string'i | `redis://localhost:6380` | Evet | `apps/api` (lib/redis.ts) |
| `API_PORT` | API sunucu portu | `3001` | Evet | `apps/api` |
| `API_HOST` | API dinleme adresi | `0.0.0.0` | Evet | `apps/api` |
| `NODE_ENV` | Ortam türü | `development` / `production` | Evet | Tüm paketler |
| `PUBLIC_API_URL` | Frontend'in API'ye erişim URL'i | `http://localhost:3001` | Hayır | `apps/web` (React bileşenleri) |
| `PUBLIC_SITE_URL` | Sitenin public URL'i | `http://localhost:4321` | Hayır | `apps/web` |
| `GOOGLE_MAPS_API_KEY` | Google Maps API anahtarı | _(boş bırakılabilir, scraper için)_ | Hayır | `scraper` |
| `SCRAPER_RATE_LIMIT` | Saniye başına istek limiti | `2` | Hayır | `scraper` |
| `PROXY_API_URL` | Proxy servis URL'i | `http://127.0.0.1:8000` | Hayır | `scraper` |
| `JWT_SECRET` | JWT imzalama anahtarı | `change-me-in-production` | Hayır* | `apps/api` (auth henüz aktif değil) |
| `JWT_EXPIRES_IN` | JWT geçerlilik süresi | `7d` | Hayır* | `apps/api` |

> **NOT:** `.env.example` dosyası root'ta mevcuttur. `apps/api/.env` ve `packages/db/.env` ayrı ayrı oluşturulmalıdır (aynı değerlerle).

### 4. Veritabanı Yönetimi

#### Veritabanı Kurulumu
```bash
# Docker ile PostgreSQL 17 + PostGIS başlatma
docker compose up -d postgres

# Extension'lar otomatik yüklenir (docker/init-extensions.sql):
# CREATE EXTENSION IF NOT EXISTS postgis;
# CREATE EXTENSION IF NOT EXISTS pg_trgm;
# CREATE EXTENSION IF NOT EXISTS unaccent;

# Bağlantı testi
docker exec -it iyisiniye-postgres psql -U iyisiniye_app -d iyisiniye -c "SELECT PostGIS_version();"
# → "3.5 USE_GEOS=1 USE_PROJ=1 USE_STATS=1"
```

#### Migration'lar
```bash
# Migration oluşturma (schema.ts değiştikten sonra)
cd packages/db
pnpm db:generate
# → src/migrations/ altına yeni SQL dosyası oluşturur

# Migration çalıştırma (SQL'leri DB'ye uygulama)
pnpm db:migrate
# veya root'tan: pnpm db:migrate

# Şemayı doğrudan push etme (development'ta hızlı prototipleme için)
pnpm db:push
# DİKKAT: Bu komut migration dosyası oluşturmaz, şemayı doğrudan uygular

# Drizzle Studio ile veritabanını görsel olarak inceleme
pnpm db:studio
# → https://local.drizzle.studio açılır
```

#### Seed Data (Test Verisi)
```bash
# Henüz seed script çalıştırma komutu tanımlı değil
# packages/db/src/seed.ts dosyası mevcut ama package.json'da script yok
# Manuel çalıştırma:
cd packages/db
npx tsx src/seed.ts

# Alternatif: Scraper ile gerçek veri toplama
cd scraper
source .venv/bin/activate
scrapy crawl gm_list_spider -a city=istanbul -a query="restoran"
scrapy crawl gm_review_spider
```

#### Şema Değişikliği Yapma Adımları
1. `packages/db/src/schema.ts` dosyasını düzenle (tablo ekle/değiştir)
2. `cd packages/db && pnpm db:generate` ile migration SQL'i oluştur
3. Oluşan SQL dosyasını `src/migrations/` altında kontrol et
4. `pnpm db:migrate` ile migration'ı uygula
5. Eğer yeni tablo/kolon API'de kullanılacaksa `packages/db/src/index.ts`'de export'u kontrol et
6. `apps/api/src/routes/` altında ilgili route dosyasını güncelle

### 5. Servisleri Çalıştırma

#### Geliştirme Ortamı (Development)
```bash
# Tüm servisleri aynı anda çalıştırma (Turborepo paralel)
pnpm dev
# Bu komut şunları başlatır:
# - apps/api: tsx watch src/index.ts (hot-reload)
# - apps/web: astro dev (hot-reload + HMR)

# Her servisi ayrı ayrı çalıştırma
cd apps/api && pnpm dev    # Sadece API (http://localhost:3001)
cd apps/web && pnpm dev    # Sadece Web (http://localhost:4321)

# Docker servislerini başlatma (DB + Redis)
docker compose up -d       # Arka planda
docker compose logs -f     # Logları takip et
docker compose down        # Durdur

# API health check
curl http://localhost:3001/health
# → {"status":"ok"}
```

#### Üretim Ortamı (Production)
```bash
# 1. Build (tüm paketler)
pnpm build
# → apps/api/dist/index.js (tsup ile ESM bundle)
# → apps/web/dist/ (Astro static build)

# 2. API başlatma (production)
cd apps/api
NODE_ENV=production node dist/index.js

# 3. Web statik dosyaları serve etme
# Astro SSG çıktısı apps/web/dist/ altında
# Nginx veya herhangi bir static file server ile serve edilir

# 4. PM2 ile process management (önerilen)
# PM2 yapılandırması henüz oluşturulmadı (infra/pm2/ boş)
# Örnek:
pm2 start apps/api/dist/index.js --name iyisiniye-api
pm2 save
pm2 startup
```

#### Port Haritası
| Servis | Port | URL | Notlar |
|--------|------|-----|--------|
| Astro Web (dev) | 4321 | http://localhost:4321 | Hot-reload, `/api` proxy aktif |
| Fastify API (dev) | 3001 | http://localhost:3001 | tsx watch ile hot-reload |
| PostgreSQL (Docker) | 15433 | localhost:15433 | Container internal: 5432 |
| Redis (Docker) | 6380 | localhost:6380 | Container internal: 6379 |
| PostgreSQL (Production) | 5433 | 157.173.116.230:5433 | Doğrudan bağlantı |
| Drizzle Studio | 4983 | https://local.drizzle.studio | `pnpm db:studio` ile |

### 6. API Dokümantasyonu

#### Endpoint Listesi
| Method | Path | Açıklama | Auth? | Cache TTL |
|--------|------|----------|-------|-----------|
| GET | `/health` | Sağlık kontrolü | Hayır | - |
| GET | `/api/v1/search` | Restoran & yemek arama | Hayır | 300s |
| GET | `/api/v1/restaurant/:slug` | Restoran detay | Hayır | 900s |
| GET | `/api/v1/dish/:slug` | Yemek detay | Hayır | 600s |
| GET | `/api/v1/autocomplete` | Otomatik tamamlama | Hayır | 3600s |

#### Örnek İstekler ve Yanıtlar

**1. Arama (`/api/v1/search`)**
```bash
curl "http://localhost:3001/api/v1/search?q=lahmacun&district=kadikoy&sort_by=score&page=1&limit=10"
```
Query parametreleri:
- `q` (zorunlu, min 2 karakter): Arama sorgusu
- `district`: İlçe filtresi
- `cuisine`: `turk|kebap|balik|doner|pide_lahmacun|ev_yemekleri|sokak_lezzetleri|tatli_pasta|kahvalti|italyan|uzakdogu|fast_food|vegan|diger`
- `price_range`: 1-4 (1=ucuz, 4=pahalı)
- `min_score`: 1-10 minimum puan
- `sort_by`: `score` (varsayılan) | `distance` | `newest`
- `page`: Sayfa numarası (varsayılan: 1)
- `limit`: Sayfa boyutu (1-50, varsayılan: 20)
- `lat`, `lng`: Konum koordinatları (distance sort ve 10km filtre için)

Yanıt:
```json
{
  "data": [
    {
      "id": 1,
      "name": "Halil Lahmacun",
      "slug": "halil-lahmacun",
      "address": "Caferağa Mah. Moda Cad.",
      "district": "Kadıköy",
      "neighborhood": "Caferağa",
      "cuisineType": ["pide_lahmacun", "kebap"],
      "priceRange": 2,
      "overallScore": "8.5",
      "totalReviews": 142,
      "imageUrl": null,
      "distance": 2.3,
      "topDishes": [
        { "foodName": "Lahmacun", "score": "9.1", "reviewCount": 87 },
        { "foodName": "Pide", "score": "7.8", "reviewCount": 34 }
      ]
    }
  ],
  "pagination": { "page": 1, "limit": 10, "total": 23, "totalPages": 3, "hasNext": true, "hasPrev": false },
  "meta": { "query": "lahmacun", "appliedFilters": { "district": "kadikoy", "cuisine": null, "priceRange": null, "minScore": null }, "sortBy": "score" }
}
```

**2. Restoran Detay (`/api/v1/restaurant/:slug`)**
```bash
curl "http://localhost:3001/api/v1/restaurant/halil-lahmacun"
```
Yanıt: Restoran bilgileri + platform verileri + top yemekler + son 10 yorum + sentiment dağılımı

**3. Yemek Detay (`/api/v1/dish/:slug`)**
```bash
curl "http://localhost:3001/api/v1/dish/lahmacun"
```
Yanıt: Yemek bilgileri + hangi restoranlarda yapılıyor + puan sıralaması + sentiment istatistikleri

**4. Otomatik Tamamlama (`/api/v1/autocomplete`)**
```bash
curl "http://localhost:3001/api/v1/autocomplete?q=lah"
```
Query: `q` (zorunlu, min 2 karakter)
Rate limit: 30 istek/dk/IP
Yanıt:
```json
{
  "restaurants": [{ "name": "Halil Lahmacun", "slug": "halil-lahmacun", "district": "Kadıköy" }],
  "dishes": [{ "name": "Lahmacun", "slug": "lahmacun", "category": "pide_lahmacun" }]
}
```

### 7. Proje Klasör Yapısı (Detaylı)

```
iyisiniye/
├── package.json                 # Monorepo root: scripts (dev, build, test, db:*)
├── turbo.json                   # Turborepo task tanımları ve bağımlılıkları
├── pnpm-workspace.yaml          # Workspace: ["apps/*", "packages/*"]
├── docker-compose.yml           # PostgreSQL 17 + PostGIS + Redis 7
├── .env.example                 # Tüm ortam değişkenleri şablonu
├── .gitignore                   # node_modules, dist, .env, __pycache__, vb.
├── CLAUDE.md                    # Bu dosya — proje hafızası ve handoff dokümanı
│
├── docker/
│   └── init-extensions.sql      # PostGIS + pg_trgm + unaccent otomatik kurulum
│
├── apps/
│   ├── api/                     # ──── FASTIFY REST API ────
│   │   ├── package.json         # @iyisiniye/api — Fastify 5, Zod v4, ioredis
│   │   ├── vitest.config.ts     # Test yapılandırması
│   │   ├── .env                 # API ortam değişkenleri (gitignore'da)
│   │   └── src/
│   │       ├── index.ts         # buildApp() → CORS, Helmet, Rate Limit, Routes → start()
│   │       ├── lib/
│   │       │   ├── redis.ts     # ioredis singleton (retry strategy, graceful shutdown)
│   │       │   └── cache.ts     # cacheGet, cacheSet, cacheDelete, cacheDeletePattern
│   │       ├── routes/
│   │       │   ├── search.ts    # GET /api/v1/search — FTS + trigram + PostGIS
│   │       │   ├── restaurant.ts# GET /api/v1/restaurant/:slug — 4 paralel sorgu
│   │       │   ├── dish.ts      # GET /api/v1/dish/:slug — yemek → restoranlar
│   │       │   └── autocomplete.ts # GET /api/v1/autocomplete — 5+5 trigram
│   │       └── __tests__/
│   │           ├── setup.ts     # Redis Mock (Map), Drizzle Proxy Mock
│   │           ├── search.test.ts
│   │           ├── restaurant.test.ts
│   │           ├── dish.test.ts
│   │           ├── autocomplete.test.ts
│   │           └── cache.test.ts
│   │
│   ├── web/                     # ──── ASTRO 5 FRONTEND ────
│   │   ├── package.json         # @iyisiniye/web — Astro 5, React 19, Tailwind 4
│   │   ├── astro.config.mjs     # Static output, React integration, /api proxy
│   │   ├── playwright.config.ts # E2E test yapılandırması
│   │   └── src/
│   │       ├── layouts/
│   │       │   └── BaseLayout.astro  # <head>, meta tags, Tailwind, Poppins font
│   │       ├── pages/
│   │       │   ├── index.astro       # Ana sayfa (Hero + Search + Carousel + Stars)
│   │       │   ├── search.astro      # Arama sayfası → SearchIsland (client:load)
│   │       │   └── restaurant/
│   │       │       └── [slug].astro  # Restoran detay → RestaurantDetailIsland
│   │       ├── components/           # 13 React/Astro bileşen
│   │       │   ├── SearchIsland.tsx  # Ana arama + filtreler + sonuç listesi
│   │       │   ├── RestaurantDetailIsland.tsx
│   │       │   ├── HeroSearch.tsx    # Ana sayfa arama kutusu
│   │       │   ├── PopularDishesCarousel.tsx
│   │       │   ├── VenueCard.tsx     # Restoran kartı bileşeni
│   │       │   ├── DishRow.tsx       # Yemek satırı bileşeni
│   │       │   ├── ScoreBadge.tsx    # Puan rozeti (≥8 yeşil, ≥5 turuncu, <5 kırmızı)
│   │       │   ├── FilterChip.tsx    # Filtre toggle chip
│   │       │   ├── Button.tsx        # Genel buton (primary/secondary/ghost)
│   │       │   └── EmptyState.tsx    # Sonuç yok gösterimi
│   │       └── styles/
│   │           └── global.css        # Tailwind base + Poppins import
│   │   └── e2e/
│   │       ├── search-flow.spec.ts       # 13 E2E test
│   │       ├── filter-pagination.spec.ts # 16 E2E test
│   │       └── error-states.spec.ts      # 12 E2E test
│   │
│   └── admin/                   # ──── ADMIN PANEL (boş iskelet) ────
│       └── package.json         # @iyisiniye/admin — Vite + React Router DOM
│
├── packages/
│   ├── db/                      # ──── VERİTABANI PAKETİ ────
│   │   ├── package.json         # @iyisiniye/db — Drizzle ORM, postgres.js
│   │   ├── drizzle.config.ts    # Migration yapılandırması (dialect: postgresql)
│   │   ├── .env                 # DB ortam değişkenleri (gitignore'da)
│   │   └── src/
│   │       ├── index.ts         # DB bağlantısı (postgres.js, max 10 conn) + export
│   │       ├── schema.ts        # 11 tablo + ilişkiler + GIN/GiST/B-tree indeksler
│   │       ├── seed.ts          # Seed data scripti
│   │       └── migrations/
│   │           ├── 0000_overconfident_scarlet_spider.sql  # İlk migration (141 satır)
│   │           └── meta/        # Drizzle migration metadata
│   │
│   └── shared/                  # ──── PAYLAŞIMLI TİPLER ────
│       ├── package.json         # @iyisiniye/shared
│       └── src/
│           ├── index.ts         # Ana export
│           ├── types/index.ts   # Ortak TypeScript tipleri
│           ├── constants/index.ts # Sabit değerler (cuisineTypes, priceRanges vb.)
│           └── utils/index.ts   # Yardımcı fonksiyonlar
│
├── nlp/                         # ──── PYTHON NLP PIPELINE ────
│   ├── pyproject.toml           # Proje metadata (iyisiniye-nlp)
│   ├── requirements.txt         # transformers, torch, rapidfuzz, pandas, psycopg2
│   ├── run_pipeline.sh          # Pipeline çalıştırma shell scripti
│   ├── src/
│   │   ├── nlp_batch_pipeline.py    # ANA PIPELINE: DB'den oku → işle → yaz
│   │   ├── food_extractor.py        # Regex + BERT ile yemek adı çıkarma
│   │   ├── food_normalizer.py       # Aliases → canonical name dönüşümü
│   │   ├── food_scorer.py           # Sentiment → 1-10 puan hesaplama
│   │   ├── item_filter.py           # Yemek mi değil mi sınıflandırma
│   │   ├── sentiment_analyzer.py    # BERT Türkçe sentiment analizi
│   │   └── weak_labeler.py          # Bootstrap zayıf etiketleme
│   ├── data/
│   │   ├── yemek_sozlugu.json       # Türkçe yemek sözlüğü
│   │   └── filtre_sozlugu.json      # Filtreleme sözlüğü
│   ├── models/                      # BERT model checkpoint'ları (otomatik indirilir)
│   └── tests/
│
├── scraper/                     # ──── SCRAPY WEB SCRAPER ────
│   ├── scrapy.cfg               # Scrapy proje yapılandırması
│   ├── pyproject.toml           # Proje metadata
│   ├── requirements.txt         # scrapy, playwright, httpx, psycopg2, loguru
│   ├── iyisiniye_scraper/       # Ana Scrapy projesi
│   │   ├── settings.py          # Bot config, download_delay=3, concurrent=8
│   │   ├── items.py             # RestaurantItem, ReviewItem tanımları
│   │   ├── pipelines.py         # Validation → Dedup → Database (918 satır)
│   │   ├── middlewares/
│   │   │   └── rate_limiter.py  # İstek hız sınırlama
│   │   └── spiders/
│   │       ├── base_spider.py       # Temel spider sınıfı
│   │       ├── google_maps_list.py  # GM restoran listesi spider'ı
│   │       └── google_maps_reviews.py # GM yorum spider'ı
│   ├── matching/
│   │   └── cross_platform.py    # Çapraz platform restoran eşleştirme
│   ├── middlewares/
│   │   └── proxy_middleware.py  # Proxy rotation middleware
│   ├── config/
│   │   └── settings.py          # Ek yapılandırma
│   └── tests/
│
├── infra/                       # ──── ALTYAPI (henüz boş) ────
│   ├── nginx/                   # Nginx reverse proxy config'leri
│   ├── cron/                    # Cron job tanımları (NLP, scraper)
│   └── pm2/                     # PM2 process yapılandırması
│
└── docs/
    └── api-contracts-v1.ts      # API kontrat tanımları (TypeScript arayüzleri)
```

### 8. Üçüncü Parti Servisler ve Entegrasyonlar

| Servis | Amaç | Bağlantı | Credential |
|--------|------|----------|------------|
| PostgreSQL 17 + PostGIS | Ana veritabanı + mekansal sorgular | Docker: `localhost:15433` / Prod: `157.173.116.230:5433` | `iyisiniye_app` / `IyS2026SecureDB` |
| Redis 7 | API yanıt cache'i | Docker: `localhost:6380` | Şifresiz (development) |
| Google Maps | Restoran ve yorum verisi (scraping) | Web scraping | `GOOGLE_MAPS_API_KEY` (opsiyonel) |
| HuggingFace Transformers | BERT sentiment modeli | Otomatik indirme | - |
| CloudPanel | Sunucu yönetim paneli | `https://cloud.skystonetech.com` | `admin` / `SFj353!*?dd` |

### 9. Test Stratejisi

#### Test Çalıştırma
```bash
# API testleri (Vitest — 41 test)
pnpm test
# veya: cd apps/api && pnpm test
# veya: cd apps/api && pnpm test:watch  # İzleme modu

# E2E testleri (Playwright — 41 test)
cd apps/web
npx playwright test                    # Tüm E2E testler
npx playwright test search-flow        # Tek dosya
npx playwright test --headed           # Tarayıcı görünür
npx playwright test --debug            # Debug modu
npx playwright show-report             # Son test raporu

# NOT: E2E testler için API ve Web sunucularının çalışıyor olması gerekir
# Önce: pnpm dev (ayrı terminal)
```

#### Test Yazma Kuralları
- **API testleri**: `apps/api/src/__tests__/` altına `*.test.ts` dosyası oluştur
- **Mock altyapısı**: `setup.ts` Redis'i in-memory Map ile, Drizzle'ı Proxy mock ile simüle eder — gerçek DB'ye bağlanmaz
- **Her yeni endpoint için**: En az request/response format testi, hata durumu testi, cache davranış testi yaz
- **E2E testleri**: `apps/web/e2e/` altına `*.spec.ts` dosyası oluştur
- **E2E pattern**: Page Object Model kullanma, doğrudan `page.goto()` + `page.locator()` ile test

### 10. Deployment (Yayına Alma)

#### Deployment Adımları
```bash
# ⚠️ PROJE HENÜZ DEPLOY EDİLMEDİ — Aşağıdaki adımlar planlanan deployment sürecidir

# 1. Sunucuya SSH bağlantısı
ssh root@157.173.116.230

# 2. Node.js ve pnpm kurulumu (sunucuda)
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs
npm install -g pnpm@9

# 3. PostgreSQL (sunucuda zaten var — port 5433)
# Extension'ları yükle:
psql -U iyisiniye_app -d iyisiniye -c "CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;"

# 4. Redis kurulumu
apt-get install -y redis-server
systemctl enable redis-server

# 5. Proje dosyalarını sunucuya aktar
git clone https://github.com/FeritTasdildiren/iyisiniye.git /opt/iyisiniye
cd /opt/iyisiniye
pnpm install --frozen-lockfile

# 6. Ortam değişkenlerini ayarla (production değerleri)
# apps/api/.env ve packages/db/.env dosyalarını production değerleriyle oluştur
# DATABASE_URL → 157.173.116.230:5433
# REDIS_URL → redis://localhost:6379
# NODE_ENV=production

# 7. Migration çalıştır
pnpm db:migrate

# 8. Build
pnpm build

# 9. PM2 ile API başlat
npm install -g pm2
pm2 start apps/api/dist/index.js --name iyisiniye-api
pm2 save && pm2 startup

# 10. Nginx reverse proxy ayarla
# /etc/nginx/sites-available/iyisiniye.conf
# → API: proxy_pass http://localhost:3001
# → Web: root /opt/iyisiniye/apps/web/dist (static files)

# 11. Python ortamlarını kur (NLP + Scraper)
cd /opt/iyisiniye/nlp && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cd /opt/iyisiniye/scraper && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# 12. Cron job'ları ayarla
# crontab -e
# 0 3 * * * cd /opt/iyisiniye/nlp && .venv/bin/python src/nlp_batch_pipeline.py
# 0 1 * * 1 cd /opt/iyisiniye/scraper && .venv/bin/scrapy crawl gm_review_spider
```

#### Sunucu Bilgileri
| Alan | Değer |
|------|-------|
| Host | 157.173.116.230 |
| SSH | `ssh root@157.173.116.230` / Şifre: `E3Ry8H#bWkMGJc6y` |
| Web Panel | https://cloud.skystonetech.com (admin / SFj353!*?dd) |
| Mail | https://mail.skystonetech.com (admin / SFj353!*?dd) |

#### Domain ve DNS Ayarları
Henüz yapılandırılmadı. Planlanan: `iyisiniye.com` → `157.173.116.230`

### 11. Sık Karşılaşılan Sorunlar ve Çözümleri

| Sorun | Olası Neden | Çözüm |
|-------|-------------|-------|
| `pnpm install` hata veriyor | pnpm versiyonu eski | `npm install -g pnpm@9` ile güncelle |
| DB bağlantı hatası | Docker container çalışmıyor | `docker compose up -d postgres` ve `docker compose ps` ile kontrol et |
| `PostGIS_version() not found` | Extension yüklenmemiş | `docker exec -it iyisiniye-postgres psql -U iyisiniye_app -d iyisiniye -c "CREATE EXTENSION postgis;"` |
| Redis bağlantı hatası | Redis container çalışmıyor | `docker compose up -d redis` |
| `zod/v4` import hatası | Yanlış import kullanımı | Route dosyalarında `import { z } from "zod/v4"` kullan, `"zod"` DEĞİL |
| Migration çalışmıyor | `.env` dosyası eksik | `packages/db/.env` dosyasını `.env.example`'dan oluştur |
| Astro build hatası | TypeScript tip hatası | `cd apps/web && pnpm typecheck` ile hataları kontrol et |
| API proxy çalışmıyor | Astro dev server kapalı | `pnpm dev` ile tüm servisleri birlikte başlat |
| NLP pipeline `torch` hatası | GPU driver uyumsuzluğu | CPU modu kullanılıyor, `requirements.txt`'te torch CPU versiyonu |
| Scraper `playwright` hatası | Chromium kurulu değil | `cd scraper && source .venv/bin/activate && playwright install chromium` |
| `ECONNREFUSED :15433` | Docker port mapping | `docker compose down && docker compose up -d` ile yeniden başlat |
| Test mock hataları | setup.ts import sorunu | `vi.mock()` tanımlarının dosya başında olduğunu kontrol et |

### 12. Geliştirme İpuçları ve Kısayollar

```bash
# Cache temizleme (tüm API cache'ini sıfırla)
docker exec -it iyisiniye-redis redis-cli FLUSHALL

# Belirli bir pattern'in cache'ini temizle
docker exec -it iyisiniye-redis redis-cli --scan --pattern "search:*" | xargs docker exec -i iyisiniye-redis redis-cli DEL

# DB'ye hızlı bağlanma
docker exec -it iyisiniye-postgres psql -U iyisiniye_app -d iyisiniye

# Tablo satır sayıları
docker exec -it iyisiniye-postgres psql -U iyisiniye_app -d iyisiniye -c "SELECT schemaname, relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC;"

# API loglarını izleme (development)
# Fastify pino-pretty ile otomatik formatlı log yazar

# Turborepo cache temizleme
pnpm clean          # dist/ ve .astro/ klasörlerini siler
npx turbo daemon stop  # Turbo daemon'ı durdur (sorunlu cache durumlarında)

# Drizzle Studio ile DB'yi görsel inceleme
cd packages/db && pnpm db:studio

# TypeScript tip kontrolü (tüm paketler)
pnpm typecheck

# Tek bir paketin tiplerini kontrol et
cd apps/api && pnpm typecheck

# Git workflow
git add -A && git commit -m "feat: açıklama"
git push origin main
```
