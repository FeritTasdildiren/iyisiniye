/**
 * ============================================================================
 * iyisiniye.com - API v1 Endpoint Sozlesmeleri
 * ============================================================================
 *
 * Belge: TASK-035 (T-03.1.3)
 * Tarih: 2026-02-01
 * Versiyon: 1.0.0
 *
 * Bu dosya 4 public endpoint'in tam sozlesmesini icerir:
 *   1. GET /api/v1/search          - Restoran & yemek arama
 *   2. GET /api/v1/restaurants/:slug - Restoran detay
 *   3. GET /api/v1/dishes/:slug     - Yemek detay
 *   4. GET /api/v1/autocomplete     - Anlik oneri
 *
 * Kullanilan teknolojiler:
 *   - Fastify 5 + fastify-type-provider-zod
 *   - Drizzle ORM (PostgreSQL)
 *   - Zod validasyon
 *   - Redis cache (ioredis)
 *   - PostGIS, pg_trgm, unaccent eklentileri
 *
 * DB Semasi referansi: packages/db/src/schema.ts
 * ============================================================================
 */

import { z } from "zod";

// ============================================================================
// ORTAK TIPLER VE SEMA YARDIMCILARI
// ============================================================================

/**
 * Standart API hata yanit formati.
 * Tum endpointler ayni hata yapisini kullanir.
 */
export const ApiErrorSchema = z.object({
  statusCode: z.number(),
  error: z.string(),
  message: z.string(),
  details: z.unknown().optional(),
});

export type ApiErrorResponse = z.infer<typeof ApiErrorSchema>;

/**
 * Ornek hata yanitlari:
 *
 * 400 Bad Request:
 * {
 *   "statusCode": 400,
 *   "error": "Bad Request",
 *   "message": "Arama sorgusu en az 2 karakter olmalidir.",
 *   "details": { "field": "q", "constraint": "min_length" }
 * }
 *
 * 404 Not Found:
 * {
 *   "statusCode": 404,
 *   "error": "Not Found",
 *   "message": "Restoran bulunamadi: ciya-sofrasi-2"
 * }
 *
 * 429 Too Many Requests:
 * {
 *   "statusCode": 429,
 *   "error": "Too Many Requests",
 *   "message": "Rate limit asildi. Lutfen 60 saniye sonra tekrar deneyin."
 * }
 *
 * 500 Internal Server Error:
 * {
 *   "statusCode": 500,
 *   "error": "Internal Server Error",
 *   "message": "Beklenmeyen bir hata olustu."
 * }
 */

/** Sayfalama meta bilgisi */
export const PaginationSchema = z.object({
  page: z.number().int().positive(),
  limit: z.number().int().positive(),
  total: z.number().int().nonnegative(),
  totalPages: z.number().int().nonnegative(),
  hasNext: z.boolean(),
  hasPrev: z.boolean(),
});

/** Restoran ozet bilgisi (arama sonuclarinda kullanilir) */
export const RestaurantSummarySchema = z.object({
  id: z.number(),
  name: z.string(),
  slug: z.string(),
  address: z.string().nullable(),
  district: z.string().nullable(),
  neighborhood: z.string().nullable(),
  cuisineType: z.array(z.string()).nullable(),
  priceRange: z.number().min(1).max(4).nullable(),
  overallScore: z.string().nullable(), // decimal string: "7.85"
  totalReviews: z.number(),
  imageUrl: z.string().nullable(),
  distance: z.number().nullable(), // km, sadece konum aramasinda dolu
  topDishes: z.array(
    z.object({
      foodName: z.string(),
      score: z.string(), // decimal string: "8.50"
      reviewCount: z.number(),
    })
  ),
});

// ============================================================================
// 1. GET /api/v1/search - Restoran & Yemek Arama
// ============================================================================

/**
 * ENDPOINT: GET /api/v1/search
 * AMAC: Restoran ve yemek arama. FTS + fuzzy matching + konum destegi.
 *
 * ARAMA STRATEJISI:
 *   1. pg_trgm similarity ile fuzzy match (esik: 0.2, Turkce icin optimize)
 *   2. to_tsvector('turkish', ...) ile FTS
 *   3. PostGIS ST_DWithin() ile mesafe filtresi (lat/lng verildiginde)
 *   4. Sonuclar: once FTS rank, sonra trigram similarity skoru ile sirala
 *
 * PERFORMANS HEDEFI: < 300ms (cache miss), < 50ms (cache hit)
 */

// --- Request ---

export const SearchQuerySchema = z.object({
  /** Arama metni (min 2 karakter) */
  q: z.string().min(2, "Arama sorgusu en az 2 karakter olmalidir.").max(100),

  /** Ilce filtresi (ornek: "kadikoy", "besiktas") */
  district: z.string().max(100).optional(),

  /** Mutfak turu filtresi */
  cuisine: z
    .enum([
      "turk",
      "kebap",
      "balik",
      "doner",
      "pide_lahmacun",
      "ev_yemekleri",
      "sokak_lezzetleri",
      "tatli_pasta",
      "kahvalti",
      "italyan",
      "uzakdogu",
      "fast_food",
      "vegan",
      "diger",
    ])
    .optional(),

  /** Fiyat araligi filtresi (1-4) */
  price_range: z.coerce.number().int().min(1).max(4).optional(),

  /** Minimum genel puan filtresi (1-10 arasi) */
  min_score: z.coerce.number().min(1).max(10).optional(),

  /** Siralama kriteri */
  sort_by: z.enum(["score", "distance", "newest"]).default("score"),

  /** Sayfa numarasi */
  page: z.coerce.number().int().positive().default(1),

  /** Sayfa basina sonuc sayisi (maks 50) */
  limit: z.coerce.number().int().min(1).max(50).default(20),

  /** Kullanici enlemi (konum bazli arama icin) */
  lat: z.coerce.number().min(-90).max(90).optional(),

  /** Kullanici boylaml (konum bazli arama icin) */
  lng: z.coerce.number().min(-180).max(180).optional(),
});

export type SearchQuery = z.infer<typeof SearchQuerySchema>;

// --- Response ---

export const SearchResponseSchema = z.object({
  data: z.array(RestaurantSummarySchema),
  pagination: PaginationSchema,
  meta: z.object({
    query: z.string(),
    appliedFilters: z.object({
      district: z.string().nullable(),
      cuisine: z.string().nullable(),
      priceRange: z.number().nullable(),
      minScore: z.number().nullable(),
    }),
    sortBy: z.string(),
  }),
});

export type SearchResponse = z.infer<typeof SearchResponseSchema>;

/**
 * ORNEK RESPONSE:
 * {
 *   "data": [
 *     {
 *       "id": 1,
 *       "name": "Ciya Sofrasi",
 *       "slug": "ciya-sofrasi",
 *       "address": "Caferaga Mah. Guneslibahce Sok. No:43, Kadikoy",
 *       "district": "Kadikoy",
 *       "neighborhood": "Caferaga",
 *       "cuisineType": ["turk", "ev_yemekleri"],
 *       "priceRange": 2,
 *       "overallScore": "7.85",
 *       "totalReviews": 1240,
 *       "imageUrl": "/images/restaurants/ciya-sofrasi.jpg",
 *       "distance": null,
 *       "topDishes": [
 *         { "foodName": "Kuzu Tandir", "score": "9.20", "reviewCount": 85 },
 *         { "foodName": "Ali Nazik", "score": "8.90", "reviewCount": 62 },
 *         { "foodName": "Icli Kofte", "score": "8.75", "reviewCount": 54 }
 *       ]
 *     }
 *   ],
 *   "pagination": {
 *     "page": 1,
 *     "limit": 20,
 *     "total": 45,
 *     "totalPages": 3,
 *     "hasNext": true,
 *     "hasPrev": false
 *   },
 *   "meta": {
 *     "query": "kebap",
 *     "appliedFilters": {
 *       "district": null,
 *       "cuisine": null,
 *       "priceRange": null,
 *       "minScore": null
 *     },
 *     "sortBy": "score"
 *   }
 * }
 */

// --- Hata Durumlari ---
/**
 * 400: q parametresi eksik veya 2 karakterden kisa
 * 400: sort_by=distance ama lat/lng verilmemis
 * 400: gecersiz price_range, min_score degerleri
 * 500: Veritabani baglanti hatasi
 */

// --- Redis Cache Stratejisi ---
/**
 * Key format:  search:{hash(q+district+cuisine+price_range+min_score+sort_by+page+limit+lat+lng)}
 * Ornek key:   search:a3f8c2e1 (parametrelerin SHA-256 hash'inin ilk 8 karakteri)
 * TTL:         300 saniye (5 dakika)
 * Invalidation: Yeni restoran/yorum eklendiginde ilgili keyler silinir.
 *               Pratik yaklasim: "search:*" prefix'li keylere TTL-bazli expire yeterli.
 *               Manuel invalidation: food_scores veya restaurants tablosu guncellenmesinde
 *               Redis SCAN + DEL ile "search:*" temizlenir.
 */

// --- Drizzle ORM Sorgu Taslagi ---

/**
 * NOT: Asagidaki kod gercek Drizzle syntax'idir.
 * Uretim kodunda service katmanina tasinacaktir.
 *
 * ```typescript
 * import { db } from "@iyisiniye/db";
 * import { restaurants, foodScores } from "@iyisiniye/db/schema";
 * import { sql, eq, and, gte, desc, asc, ilike } from "drizzle-orm";
 *
 * async function searchRestaurants(params: SearchQuery) {
 *   const { q, district, cuisine, price_range, min_score, sort_by, page, limit, lat, lng } = params;
 *   const offset = (page - 1) * limit;
 *
 *   // Turkce normalizasyon: unaccent + lower
 *   const normalizedQuery = sql`unaccent(lower(${q}))`;
 *
 *   // Dinamik WHERE kosullari
 *   const conditions = [
 *     eq(restaurants.isActive, true),
 *     // FTS + Trigram birlestirmesi
 *     sql`(
 *       to_tsvector('turkish', coalesce(${restaurants.name}, '') || ' ' || coalesce(${restaurants.address}, ''))
 *       @@ plainto_tsquery('turkish', unaccent(${q}))
 *       OR similarity(${restaurants.name}, ${q}) > 0.2
 *     )`,
 *   ];
 *
 *   if (district) {
 *     conditions.push(sql`lower(${restaurants.district}) = lower(${district})`);
 *   }
 *
 *   if (cuisine) {
 *     conditions.push(sql`${q} = ANY(${restaurants.cuisineType})`);
 *     // Duzeltme: cuisine parametresi kullanilmali
 *     // conditions.push(sql`${cuisine} = ANY(${restaurants.cuisineType})`);
 *   }
 *
 *   if (price_range) {
 *     conditions.push(eq(restaurants.priceRange, price_range));
 *   }
 *
 *   if (min_score) {
 *     conditions.push(gte(restaurants.overallScore, min_score.toString()));
 *   }
 *
 *   // Mesafe filtresi (PostGIS)
 *   if (lat && lng) {
 *     // 10km yaricap varsayilan
 *     conditions.push(
 *       sql`ST_DWithin(
 *         ${restaurants.location}::geography,
 *         ST_SetSRID(ST_MakePoint(${lng}, ${lat}), 4326)::geography,
 *         10000
 *       )`
 *     );
 *   }
 *
 *   // Siralama
 *   let orderClause;
 *   switch (sort_by) {
 *     case "distance":
 *       orderClause = sql`ST_Distance(
 *         ${restaurants.location}::geography,
 *         ST_SetSRID(ST_MakePoint(${lng}, ${lat}), 4326)::geography
 *       ) ASC`;
 *       break;
 *     case "newest":
 *       orderClause = desc(restaurants.createdAt);
 *       break;
 *     case "score":
 *     default:
 *       orderClause = sql`${restaurants.overallScore} DESC NULLS LAST`;
 *       break;
 *   }
 *
 *   // Ana sorgu: Restoranlar
 *   const [results, countResult] = await Promise.all([
 *     db
 *       .select({
 *         id: restaurants.id,
 *         name: restaurants.name,
 *         slug: restaurants.slug,
 *         address: restaurants.address,
 *         district: restaurants.district,
 *         neighborhood: restaurants.neighborhood,
 *         cuisineType: restaurants.cuisineType,
 *         priceRange: restaurants.priceRange,
 *         overallScore: restaurants.overallScore,
 *         totalReviews: restaurants.totalReviews,
 *         imageUrl: restaurants.imageUrl,
 *         ...(lat && lng
 *           ? {
 *               distance: sql<number>`ST_Distance(
 *                 ${restaurants.location}::geography,
 *                 ST_SetSRID(ST_MakePoint(${lng}, ${lat}), 4326)::geography
 *               ) / 1000.0`.as("distance"),
 *             }
 *           : {}),
 *       })
 *       .from(restaurants)
 *       .where(and(...conditions))
 *       .orderBy(orderClause)
 *       .limit(limit)
 *       .offset(offset),
 *
 *     db
 *       .select({ count: sql<number>`count(*)::int` })
 *       .from(restaurants)
 *       .where(and(...conditions)),
 *   ]);
 *
 *   // Her restoran icin en iyi 3 yemek
 *   const restaurantIds = results.map((r) => r.id);
 *
 *   const topDishesResult = restaurantIds.length > 0
 *     ? await db
 *         .select({
 *           restaurantId: foodScores.restaurantId,
 *           foodName: foodScores.foodName,
 *           score: foodScores.score,
 *           reviewCount: foodScores.reviewCount,
 *         })
 *         .from(foodScores)
 *         .where(
 *           sql`${foodScores.restaurantId} IN (${sql.join(restaurantIds.map(id => sql`${id}`), sql`, `)})
 *               AND ${foodScores.score} IS NOT NULL`
 *         )
 *         .orderBy(desc(foodScores.score))
 *     : [];
 *
 *   // Restoran basina en iyi 3 yemek gruplama
 *   const dishMap = new Map<number, typeof topDishesResult>();
 *   for (const dish of topDishesResult) {
 *     const existing = dishMap.get(dish.restaurantId) ?? [];
 *     if (existing.length < 3) {
 *       existing.push(dish);
 *       dishMap.set(dish.restaurantId, existing);
 *     }
 *   }
 *
 *   const total = countResult[0]?.count ?? 0;
 *
 *   return {
 *     data: results.map((r) => ({
 *       ...r,
 *       distance: (r as any).distance ?? null,
 *       topDishes: (dishMap.get(r.id) ?? []).map((d) => ({
 *         foodName: d.foodName,
 *         score: d.score,
 *         reviewCount: d.reviewCount,
 *       })),
 *     })),
 *     pagination: {
 *       page,
 *       limit,
 *       total,
 *       totalPages: Math.ceil(total / limit),
 *       hasNext: page < Math.ceil(total / limit),
 *       hasPrev: page > 1,
 *     },
 *     meta: {
 *       query: q,
 *       appliedFilters: {
 *         district: district ?? null,
 *         cuisine: cuisine ?? null,
 *         priceRange: price_range ?? null,
 *         minScore: min_score ?? null,
 *       },
 *       sortBy: sort_by,
 *     },
 *   };
 * }
 * ```
 */

// ============================================================================
// 2. GET /api/v1/restaurants/:slug - Restoran Detay
// ============================================================================

/**
 * ENDPOINT: GET /api/v1/restaurants/:slug
 * AMAC: Tek restoran detay sayfasi. Yemek puanlari, yorumlar, sentiment ozeti.
 *
 * PERFORMANS HEDEFI: < 200ms (cache miss), < 30ms (cache hit)
 */

// --- Request ---

export const RestaurantDetailParamsSchema = z.object({
  /** Restoran slug'i (URL-safe) */
  slug: z
    .string()
    .min(1)
    .max(255)
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Gecersiz slug formati."),
});

export type RestaurantDetailParams = z.infer<
  typeof RestaurantDetailParamsSchema
>;

// --- Response ---

export const RestaurantDetailResponseSchema = z.object({
  restaurant: z.object({
    id: z.number(),
    name: z.string(),
    slug: z.string(),
    address: z.string().nullable(),
    district: z.string().nullable(),
    neighborhood: z.string().nullable(),
    location: z
      .object({
        lat: z.number(),
        lng: z.number(),
      })
      .nullable(),
    phone: z.string().nullable(),
    website: z.string().nullable(),
    cuisineType: z.array(z.string()).nullable(),
    priceRange: z.number().min(1).max(4).nullable(),
    overallScore: z.string().nullable(),
    totalReviews: z.number(),
    imageUrl: z.string().nullable(),
    platforms: z.array(
      z.object({
        platform: z.string(),
        externalUrl: z.string().nullable(),
        platformScore: z.string().nullable(),
        platformReviews: z.number(),
      })
    ),
  }),
  foodScores: z.array(
    z.object({
      foodName: z.string(),
      score: z.string(),
      reviewCount: z.number(),
      confidence: z.string().nullable(),
      sentimentDistribution: z
        .object({
          positive: z.number(),
          negative: z.number(),
          neutral: z.number(),
        })
        .nullable(),
    })
  ),
  recentReviews: z.array(
    z.object({
      id: z.number(),
      authorName: z.string().nullable(),
      rating: z.number().nullable(),
      text: z.string(),
      reviewDate: z.string().nullable(), // ISO 8601
      platform: z.string(),
      mentionedDishes: z.array(
        z.object({
          dishName: z.string(),
          sentiment: z.string().nullable(),
        })
      ),
    })
  ),
  sentimentSummary: z.object({
    totalAnalyzed: z.number(),
    overallSentiment: z.enum(["positive", "negative", "neutral", "mixed"]),
    distribution: z.object({
      positive: z.number(), // yuzde: 0-100
      negative: z.number(),
      neutral: z.number(),
    }),
  }),
});

export type RestaurantDetailResponse = z.infer<
  typeof RestaurantDetailResponseSchema
>;

/**
 * ORNEK RESPONSE:
 * {
 *   "restaurant": {
 *     "id": 1,
 *     "name": "Ciya Sofrasi",
 *     "slug": "ciya-sofrasi",
 *     "address": "Caferaga Mah. Guneslibahce Sok. No:43, Kadikoy",
 *     "district": "Kadikoy",
 *     "neighborhood": "Caferaga",
 *     "location": { "lat": 40.9825, "lng": 29.0288 },
 *     "phone": "+90 216 330 31 90",
 *     "website": "https://ciya.com.tr",
 *     "cuisineType": ["turk", "ev_yemekleri"],
 *     "priceRange": 2,
 *     "overallScore": "7.85",
 *     "totalReviews": 1240,
 *     "imageUrl": "/images/restaurants/ciya-sofrasi.jpg",
 *     "platforms": [
 *       {
 *         "platform": "google_maps",
 *         "externalUrl": "https://maps.google.com/...",
 *         "platformScore": "4.50",
 *         "platformReviews": 8500
 *       }
 *     ]
 *   },
 *   "foodScores": [
 *     {
 *       "foodName": "Kuzu Tandir",
 *       "score": "9.20",
 *       "reviewCount": 85,
 *       "confidence": "0.920",
 *       "sentimentDistribution": { "positive": 78, "negative": 3, "neutral": 4 }
 *     },
 *     {
 *       "foodName": "Ali Nazik",
 *       "score": "8.90",
 *       "reviewCount": 62,
 *       "confidence": "0.880",
 *       "sentimentDistribution": { "positive": 55, "negative": 2, "neutral": 5 }
 *     }
 *   ],
 *   "recentReviews": [
 *     {
 *       "id": 501,
 *       "authorName": "Ahmet Y.",
 *       "rating": 5,
 *       "text": "Kuzu tandir muhtesemdi, ali nazik de cok guzeldi.",
 *       "reviewDate": "2026-01-28T14:30:00.000Z",
 *       "platform": "google_maps",
 *       "mentionedDishes": [
 *         { "dishName": "Kuzu Tandir", "sentiment": "positive" },
 *         { "dishName": "Ali Nazik", "sentiment": "positive" }
 *       ]
 *     }
 *   ],
 *   "sentimentSummary": {
 *     "totalAnalyzed": 850,
 *     "overallSentiment": "positive",
 *     "distribution": { "positive": 72, "negative": 12, "neutral": 16 }
 *   }
 * }
 */

// --- Hata Durumlari ---
/**
 * 404: Slug ile eslesen aktif restoran bulunamadi
 * 400: Gecersiz slug formati (regex eslesmesi basarisiz)
 * 500: Veritabani baglanti hatasi
 */

// --- Redis Cache Stratejisi ---
/**
 * Key format:  restaurant:{slug}
 * Ornek key:   restaurant:ciya-sofrasi
 * TTL:         900 saniye (15 dakika)
 * Invalidation:
 *   - Restoran bilgisi guncellendiginde: DEL restaurant:{slug}
 *   - Yeni yorum islendiginde: DEL restaurant:{slug}
 *   - food_scores tablosu guncellendiginde: DEL restaurant:{slug}
 *   - NLP pipeline tamamlandiginda: ilgili restoran keyleri temizlenir
 */

// --- Drizzle ORM Sorgu Taslagi ---

/**
 * ```typescript
 * import { db } from "@iyisiniye/db";
 * import {
 *   restaurants,
 *   restaurantPlatforms,
 *   foodScores,
 *   reviews,
 *   foodMentions,
 * } from "@iyisiniye/db/schema";
 * import { eq, and, desc, sql } from "drizzle-orm";
 *
 * async function getRestaurantDetail(slug: string) {
 *   // 1. Restoran temel bilgileri
 *   const restaurant = await db
 *     .select()
 *     .from(restaurants)
 *     .where(and(eq(restaurants.slug, slug), eq(restaurants.isActive, true)))
 *     .limit(1);
 *
 *   if (restaurant.length === 0) {
 *     return null; // 404
 *   }
 *
 *   const rest = restaurant[0];
 *
 *   // 2-5 arasi sorgulari paralel calistir
 *   const [platforms, scores, recentReviewsRaw, sentimentAgg] =
 *     await Promise.all([
 *       // 2. Platform bilgileri
 *       db
 *         .select({
 *           platform: restaurantPlatforms.platform,
 *           externalUrl: restaurantPlatforms.externalUrl,
 *           platformScore: restaurantPlatforms.platformScore,
 *           platformReviews: restaurantPlatforms.platformReviews,
 *         })
 *         .from(restaurantPlatforms)
 *         .where(eq(restaurantPlatforms.restaurantId, rest.id)),
 *
 *       // 3. Yemek puanlari (score'a gore sirali)
 *       db
 *         .select({
 *           foodName: foodScores.foodName,
 *           score: foodScores.score,
 *           reviewCount: foodScores.reviewCount,
 *           confidence: foodScores.confidence,
 *           sentimentDistribution: foodScores.sentimentDistribution,
 *         })
 *         .from(foodScores)
 *         .where(eq(foodScores.restaurantId, rest.id))
 *         .orderBy(desc(foodScores.score)),
 *
 *       // 4. Son 10 yorum (platform bilgisiyle birlikte)
 *       db
 *         .select({
 *           id: reviews.id,
 *           authorName: reviews.authorName,
 *           rating: reviews.rating,
 *           text: reviews.text,
 *           reviewDate: reviews.reviewDate,
 *           platform: restaurantPlatforms.platform,
 *         })
 *         .from(reviews)
 *         .innerJoin(
 *           restaurantPlatforms,
 *           eq(reviews.restaurantPlatformId, restaurantPlatforms.id)
 *         )
 *         .where(eq(restaurantPlatforms.restaurantId, rest.id))
 *         .orderBy(desc(reviews.reviewDate))
 *         .limit(10),
 *
 *       // 5. Sentiment ozeti (food_mentions tablosundan aggregate)
 *       db
 *         .select({
 *           totalAnalyzed: sql<number>`count(*)::int`,
 *           positiveCount: sql<number>`count(*) FILTER (WHERE ${foodMentions.sentiment} = 'positive')::int`,
 *           negativeCount: sql<number>`count(*) FILTER (WHERE ${foodMentions.sentiment} = 'negative')::int`,
 *           neutralCount: sql<number>`count(*) FILTER (WHERE ${foodMentions.sentiment} = 'neutral')::int`,
 *         })
 *         .from(foodMentions)
 *         .innerJoin(reviews, eq(foodMentions.reviewId, reviews.id))
 *         .innerJoin(
 *           restaurantPlatforms,
 *           eq(reviews.restaurantPlatformId, restaurantPlatforms.id)
 *         )
 *         .where(eq(restaurantPlatforms.restaurantId, rest.id)),
 *     ]);
 *
 *   // 6. Her yorum icin bahsedilen yemekler (batch)
 *   const reviewIds = recentReviewsRaw.map((r) => r.id);
 *   const dishMentions =
 *     reviewIds.length > 0
 *       ? await db
 *           .select({
 *             reviewId: foodMentions.reviewId,
 *             foodName: foodMentions.canonicalName,
 *             sentiment: foodMentions.sentiment,
 *           })
 *           .from(foodMentions)
 *           .where(
 *             sql`${foodMentions.reviewId} IN (${sql.join(reviewIds.map((id) => sql`${id}`), sql`, `)})`
 *           )
 *       : [];
 *
 *   // Mention'lari review'a gore grupla
 *   const mentionsByReview = new Map<number, { dishName: string; sentiment: string | null }[]>();
 *   for (const m of dishMentions) {
 *     const arr = mentionsByReview.get(m.reviewId) ?? [];
 *     arr.push({ dishName: m.foodName ?? "Bilinmeyen", sentiment: m.sentiment });
 *     mentionsByReview.set(m.reviewId, arr);
 *   }
 *
 *   // Sentiment ozeti hesapla
 *   const sentimentData = sentimentAgg[0];
 *   const total = sentimentData?.totalAnalyzed ?? 0;
 *   const positivePerc = total > 0 ? Math.round((sentimentData.positiveCount / total) * 100) : 0;
 *   const negativePerc = total > 0 ? Math.round((sentimentData.negativeCount / total) * 100) : 0;
 *   const neutralPerc = total > 0 ? 100 - positivePerc - negativePerc : 0;
 *
 *   let overallSentiment: "positive" | "negative" | "neutral" | "mixed";
 *   if (positivePerc >= 60) overallSentiment = "positive";
 *   else if (negativePerc >= 40) overallSentiment = "negative";
 *   else if (total === 0) overallSentiment = "neutral";
 *   else overallSentiment = "mixed";
 *
 *   return {
 *     restaurant: {
 *       ...rest,
 *       platforms,
 *     },
 *     foodScores: scores,
 *     recentReviews: recentReviewsRaw.map((r) => ({
 *       ...r,
 *       reviewDate: r.reviewDate?.toISOString() ?? null,
 *       mentionedDishes: mentionsByReview.get(r.id) ?? [],
 *     })),
 *     sentimentSummary: {
 *       totalAnalyzed: total,
 *       overallSentiment,
 *       distribution: {
 *         positive: positivePerc,
 *         negative: negativePerc,
 *         neutral: neutralPerc,
 *       },
 *     },
 *   };
 * }
 * ```
 */

// ============================================================================
// 3. GET /api/v1/dishes/:slug - Yemek Detay
// ============================================================================

/**
 * ENDPOINT: GET /api/v1/dishes/:slug
 * AMAC: Yemek detay sayfasi. Bu yemegin en iyi yapildigi restoranlar listesi.
 *
 * PERFORMANS HEDEFI: < 250ms (cache miss), < 30ms (cache hit)
 */

// --- Request ---

export const DishDetailParamsSchema = z.object({
  /** Yemek slug'i (URL-safe) */
  slug: z
    .string()
    .min(1)
    .max(255)
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Gecersiz slug formati."),
});

export type DishDetailParams = z.infer<typeof DishDetailParamsSchema>;

// --- Response ---

export const DishDetailResponseSchema = z.object({
  dish: z.object({
    id: z.number(),
    name: z.string(),
    slug: z.string(),
    canonicalName: z.string().nullable(),
    category: z.string().nullable(),
    subcategory: z.string().nullable(),
    isMainDish: z.boolean(),
    aliases: z.array(z.string()).nullable(),
  }),
  stats: z.object({
    /** Bu yemegi yapan toplam restoran sayisi */
    totalRestaurants: z.number(),
    /** Tum restoranlardaki ortalama puan */
    avgScore: z.string().nullable(),
    /** Toplam degerlendirme sayisi */
    totalReviews: z.number(),
  }),
  bestRestaurants: z.array(
    z.object({
      restaurant: z.object({
        id: z.number(),
        name: z.string(),
        slug: z.string(),
        district: z.string().nullable(),
        neighborhood: z.string().nullable(),
        imageUrl: z.string().nullable(),
        overallScore: z.string().nullable(),
      }),
      dishScore: z.string(), // bu yemegin bu restorandaki puani
      reviewCount: z.number(),
      confidence: z.string().nullable(),
      sentimentDistribution: z
        .object({
          positive: z.number(),
          negative: z.number(),
          neutral: z.number(),
        })
        .nullable(),
    })
  ),
});

export type DishDetailResponse = z.infer<typeof DishDetailResponseSchema>;

/**
 * ORNEK RESPONSE:
 * {
 *   "dish": {
 *     "id": 42,
 *     "name": "Iskender Kebap",
 *     "slug": "iskender-kebap",
 *     "canonicalName": "Iskender Kebap",
 *     "category": "ana_yemek",
 *     "subcategory": "kebap",
 *     "isMainDish": true,
 *     "aliases": ["iskender", "bursa kebabi", "iskender kebabi"]
 *   },
 *   "stats": {
 *     "totalRestaurants": 34,
 *     "avgScore": "7.45",
 *     "totalReviews": 512
 *   },
 *   "bestRestaurants": [
 *     {
 *       "restaurant": {
 *         "id": 15,
 *         "name": "Kebapci Iskender",
 *         "slug": "kebapci-iskender",
 *         "district": "Besiktas",
 *         "neighborhood": "Levent",
 *         "imageUrl": "/images/restaurants/kebapci-iskender.jpg",
 *         "overallScore": "8.10"
 *       },
 *       "dishScore": "9.50",
 *       "reviewCount": 120,
 *       "confidence": "0.950",
 *       "sentimentDistribution": { "positive": 110, "negative": 5, "neutral": 5 }
 *     },
 *     {
 *       "restaurant": {
 *         "id": 22,
 *         "name": "Bursa Iskender",
 *         "slug": "bursa-iskender",
 *         "district": "Kadikoy",
 *         "neighborhood": "Moda",
 *         "imageUrl": null,
 *         "overallScore": "7.30"
 *       },
 *       "dishScore": "8.80",
 *       "reviewCount": 45,
 *       "confidence": "0.870",
 *       "sentimentDistribution": { "positive": 38, "negative": 3, "neutral": 4 }
 *     }
 *   ]
 * }
 */

// --- Hata Durumlari ---
/**
 * 404: Slug ile eslesen yemek bulunamadi
 * 400: Gecersiz slug formati
 * 500: Veritabani baglanti hatasi
 */

// --- Redis Cache Stratejisi ---
/**
 * Key format:  dish:{slug}
 * Ornek key:   dish:iskender-kebap
 * TTL:         1800 saniye (30 dakika)
 * Invalidation:
 *   - food_scores tablosu guncellendiginde: DEL dish:{slug}
 *   - restaurant_dishes tablosu guncellendiginde: DEL dish:{slug}
 *   - NLP pipeline tamamlandiginda: degisen yemek sluglari icin temizlik
 *   - Yeni restoran eklendiginde: ilgili yemek keyleri temizlenir
 */

// --- Drizzle ORM Sorgu Taslagi ---

/**
 * ```typescript
 * import { db } from "@iyisiniye/db";
 * import {
 *   dishes,
 *   foodScores,
 *   restaurants,
 * } from "@iyisiniye/db/schema";
 * import { eq, and, desc, sql } from "drizzle-orm";
 *
 * async function getDishDetail(slug: string) {
 *   // 1. Yemek temel bilgileri
 *   const dish = await db
 *     .select()
 *     .from(dishes)
 *     .where(eq(dishes.slug, slug))
 *     .limit(1);
 *
 *   if (dish.length === 0) {
 *     return null; // 404
 *   }
 *
 *   const d = dish[0];
 *
 *   // 2. Bu yemegin food_scores'daki karsiligi
 *   //    dishes.canonicalName ile food_scores.foodName eslestirilir.
 *   //    Buyuk-kucuk harf duyarsiz eslesme (unaccent + lower).
 *   const matchName = d.canonicalName ?? d.name;
 *
 *   // 3. Bu yemegi sunan en iyi restoranlar (puana gore sirali, max 20)
 *   const bestRestaurants = await db
 *     .select({
 *       restaurantId: foodScores.restaurantId,
 *       restaurantName: restaurants.name,
 *       restaurantSlug: restaurants.slug,
 *       district: restaurants.district,
 *       neighborhood: restaurants.neighborhood,
 *       imageUrl: restaurants.imageUrl,
 *       overallScore: restaurants.overallScore,
 *       dishScore: foodScores.score,
 *       reviewCount: foodScores.reviewCount,
 *       confidence: foodScores.confidence,
 *       sentimentDistribution: foodScores.sentimentDistribution,
 *     })
 *     .from(foodScores)
 *     .innerJoin(restaurants, eq(foodScores.restaurantId, restaurants.id))
 *     .where(
 *       and(
 *         sql`lower(unaccent(${foodScores.foodName})) = lower(unaccent(${matchName}))`,
 *         eq(restaurants.isActive, true)
 *       )
 *     )
 *     .orderBy(desc(foodScores.score))
 *     .limit(20);
 *
 *   // 4. Istatistikler
 *   const statsResult = await db
 *     .select({
 *       totalRestaurants: sql<number>`count(DISTINCT ${foodScores.restaurantId})::int`,
 *       avgScore: sql<string>`round(avg(${foodScores.score}::numeric), 2)::text`,
 *       totalReviews: sql<number>`coalesce(sum(${foodScores.reviewCount}), 0)::int`,
 *     })
 *     .from(foodScores)
 *     .innerJoin(restaurants, eq(foodScores.restaurantId, restaurants.id))
 *     .where(
 *       and(
 *         sql`lower(unaccent(${foodScores.foodName})) = lower(unaccent(${matchName}))`,
 *         eq(restaurants.isActive, true)
 *       )
 *     );
 *
 *   const stats = statsResult[0];
 *
 *   return {
 *     dish: {
 *       id: d.id,
 *       name: d.name,
 *       slug: d.slug,
 *       canonicalName: d.canonicalName,
 *       category: d.category,
 *       subcategory: d.subcategory,
 *       isMainDish: d.isMainDish,
 *       aliases: d.aliases,
 *     },
 *     stats: {
 *       totalRestaurants: stats?.totalRestaurants ?? 0,
 *       avgScore: stats?.avgScore ?? null,
 *       totalReviews: stats?.totalReviews ?? 0,
 *     },
 *     bestRestaurants: bestRestaurants.map((r) => ({
 *       restaurant: {
 *         id: r.restaurantId,
 *         name: r.restaurantName,
 *         slug: r.restaurantSlug,
 *         district: r.district,
 *         neighborhood: r.neighborhood,
 *         imageUrl: r.imageUrl,
 *         overallScore: r.overallScore,
 *       },
 *       dishScore: r.dishScore,
 *       reviewCount: r.reviewCount,
 *       confidence: r.confidence,
 *       sentimentDistribution: r.sentimentDistribution as {
 *         positive: number;
 *         negative: number;
 *         neutral: number;
 *       } | null,
 *     })),
 *   };
 * }
 * ```
 */

// ============================================================================
// 4. GET /api/v1/autocomplete - Anlik Oneri
// ============================================================================

/**
 * ENDPOINT: GET /api/v1/autocomplete
 * AMAC: Arama kutusunda anlik restoran ve yemek onerileri.
 *
 * PERFORMANS HEDEFI: < 150ms (cache miss), < 20ms (cache hit)
 *
 * ONEMLI: Bu endpoint agresif cache ve hafif sorgularla calisir.
 * pg_trgm similarity + LIMIT ile hizli donus saglanir.
 */

// --- Request ---

export const AutocompleteQuerySchema = z.object({
  /** Arama metni (min 2 karakter) */
  q: z.string().min(2, "Oneri icin en az 2 karakter gereklidir.").max(50),
});

export type AutocompleteQuery = z.infer<typeof AutocompleteQuerySchema>;

// --- Response ---

export const AutocompleteResponseSchema = z.object({
  restaurants: z.array(
    z.object({
      id: z.number(),
      name: z.string(),
      slug: z.string(),
      district: z.string().nullable(),
      cuisineType: z.array(z.string()).nullable(),
      overallScore: z.string().nullable(),
    })
  ),
  dishes: z.array(
    z.object({
      id: z.number(),
      name: z.string(),
      slug: z.string(),
      category: z.string().nullable(),
      /** Bu yemegi sunan restoran sayisi */
      restaurantCount: z.number(),
    })
  ),
});

export type AutocompleteResponse = z.infer<typeof AutocompleteResponseSchema>;

/**
 * ORNEK RESPONSE:
 * {
 *   "restaurants": [
 *     {
 *       "id": 1,
 *       "name": "Ciya Sofrasi",
 *       "slug": "ciya-sofrasi",
 *       "district": "Kadikoy",
 *       "cuisineType": ["turk", "ev_yemekleri"],
 *       "overallScore": "7.85"
 *     },
 *     {
 *       "id": 8,
 *       "name": "Cibalikapi Balikcisi",
 *       "slug": "cibalikapi-balikcisi",
 *       "district": "Fatih",
 *       "cuisineType": ["balik"],
 *       "overallScore": "8.20"
 *     }
 *   ],
 *   "dishes": [
 *     {
 *       "id": 42,
 *       "name": "Cizbiz Kofte",
 *       "slug": "cizbiz-kofte",
 *       "category": "ana_yemek",
 *       "restaurantCount": 18
 *     },
 *     {
 *       "id": 99,
 *       "name": "Ciger Tava",
 *       "slug": "ciger-tava",
 *       "category": "ana_yemek",
 *       "restaurantCount": 12
 *     }
 *   ]
 * }
 */

// --- Hata Durumlari ---
/**
 * 400: q parametresi eksik veya 2 karakterden kisa
 * 429: Rate limit asildi (autocomplete icin ek rate limit: 30 req/dk per IP)
 * 500: Veritabani baglanti hatasi
 */

// --- Redis Cache Stratejisi ---
/**
 * Key format:  autocomplete:{normalizedQuery}
 * Ornek key:   autocomplete:keb  (lower + trim uygulanmis)
 * TTL:         3600 saniye (1 saat)
 * Invalidation:
 *   - Yeni restoran eklendiginde: SCAN + DEL autocomplete:*
 *   - Yeni yemek eklendiginde: SCAN + DEL autocomplete:*
 *   - Pratik yaklasim: TTL-bazli expire cogu senaryo icin yeterli.
 *     Autocomplete cacheleri yuksek TTL ile calisir cunku yemek/restoran
 *     isimleri nadiren degisir.
 *
 * EK OPTiMiZASYON:
 *   - Populer 2-3 harfli prefixler (keb, don, piz vb.) warm-up ile onceden
 *     cache'e yuklenir.
 *   - Redis PIPELINE kullanilarak restoran + yemek sorgulari tek roundtrip'te
 *     kontrol edilir.
 */

// --- Drizzle ORM Sorgu Taslagi ---

/**
 * ```typescript
 * import { db } from "@iyisiniye/db";
 * import { restaurants, dishes, foodScores } from "@iyisiniye/db/schema";
 * import { eq, sql, desc } from "drizzle-orm";
 *
 * async function getAutocomplete(q: string) {
 *   const normalizedQ = q.trim().toLowerCase();
 *
 *   // Restoran ve yemek sorgularini paralel calistir
 *   const [restaurantResults, dishResults] = await Promise.all([
 *     // 1. Restoran onerileri (trigram similarity + FTS, max 5)
 *     db
 *       .select({
 *         id: restaurants.id,
 *         name: restaurants.name,
 *         slug: restaurants.slug,
 *         district: restaurants.district,
 *         cuisineType: restaurants.cuisineType,
 *         overallScore: restaurants.overallScore,
 *         similarity: sql<number>`similarity(${restaurants.name}, ${q})`.as(
 *           "similarity"
 *         ),
 *       })
 *       .from(restaurants)
 *       .where(
 *         sql`(
 *           similarity(${restaurants.name}, ${q}) > 0.2
 *           OR to_tsvector('turkish', ${restaurants.name})
 *              @@ plainto_tsquery('turkish', unaccent(${q}))
 *         )
 *         AND ${restaurants.isActive} = true`
 *       )
 *       .orderBy(
 *         sql`similarity(${restaurants.name}, ${q}) DESC`,
 *         desc(restaurants.overallScore)
 *       )
 *       .limit(5),
 *
 *     // 2. Yemek onerileri (trigram similarity + FTS, max 5)
 *     //    + Bu yemegi sunan restoran sayisi (subquery)
 *     db
 *       .select({
 *         id: dishes.id,
 *         name: dishes.name,
 *         slug: dishes.slug,
 *         category: dishes.category,
 *         similarity: sql<number>`similarity(coalesce(${dishes.canonicalName}, ${dishes.name}), ${q})`.as(
 *           "similarity"
 *         ),
 *         restaurantCount: sql<number>`(
 *           SELECT count(DISTINCT ${foodScores.restaurantId})::int
 *           FROM ${foodScores}
 *           WHERE lower(unaccent(${foodScores.foodName})) = lower(unaccent(coalesce(${dishes.canonicalName}, ${dishes.name})))
 *         )`.as("restaurant_count"),
 *       })
 *       .from(dishes)
 *       .where(
 *         sql`(
 *           similarity(coalesce(${dishes.canonicalName}, ${dishes.name}), ${q}) > 0.2
 *           OR ${dishes.searchVector} @@ plainto_tsquery('turkish', unaccent(${q}))
 *         )`
 *       )
 *       .orderBy(
 *         sql`similarity(coalesce(${dishes.canonicalName}, ${dishes.name}), ${q}) DESC`
 *       )
 *       .limit(5),
 *   ]);
 *
 *   return {
 *     restaurants: restaurantResults.map(({ similarity, ...rest }) => rest),
 *     dishes: dishResults.map(({ similarity, ...rest }) => rest),
 *   };
 * }
 * ```
 */

// ============================================================================
// FASTIFY ROUTE KAYIT ORNEGI
// ============================================================================

/**
 * Asagidaki kod, endpointlerin Fastify'a nasil kayit edilecegini gosterir.
 * fastify-type-provider-zod kullanilarak request/response tipleri otomatik cikarilir.
 *
 * ```typescript
 * import {
 *   type FastifyInstance,
 *   type FastifyRequest,
 *   type FastifyReply,
 * } from "fastify";
 * import {
 *   serializerCompiler,
 *   validatorCompiler,
 *   type ZodTypeProvider,
 * } from "fastify-type-provider-zod";
 * import {
 *   SearchQuerySchema,
 *   RestaurantDetailParamsSchema,
 *   DishDetailParamsSchema,
 *   AutocompleteQuerySchema,
 * } from "./contracts.js";
 *
 * export async function registerRoutes(app: FastifyInstance) {
 *   // Zod entegrasyonu
 *   app.setValidatorCompiler(validatorCompiler);
 *   app.setSerializerCompiler(serializerCompiler);
 *
 *   const server = app.withTypeProvider<ZodTypeProvider>();
 *
 *   // --- 1. Search ---
 *   server.get(
 *     "/api/v1/search",
 *     {
 *       schema: {
 *         querystring: SearchQuerySchema,
 *       },
 *     },
 *     async (request, reply) => {
 *       const cacheKey = buildSearchCacheKey(request.query);
 *       const cached = await redis.get(cacheKey);
 *       if (cached) return JSON.parse(cached);
 *
 *       // sort_by=distance ama lat/lng yoksa hata don
 *       if (
 *         request.query.sort_by === "distance" &&
 *         (!request.query.lat || !request.query.lng)
 *       ) {
 *         return reply.status(400).send({
 *           statusCode: 400,
 *           error: "Bad Request",
 *           message:
 *             "Mesafeye gore siralama icin lat ve lng parametreleri gereklidir.",
 *         });
 *       }
 *
 *       const result = await searchRestaurants(request.query);
 *       await redis.setex(cacheKey, 300, JSON.stringify(result));
 *       return result;
 *     }
 *   );
 *
 *   // --- 2. Restaurant Detail ---
 *   server.get(
 *     "/api/v1/restaurants/:slug",
 *     {
 *       schema: {
 *         params: RestaurantDetailParamsSchema,
 *       },
 *     },
 *     async (request, reply) => {
 *       const { slug } = request.params;
 *       const cacheKey = `restaurant:${slug}`;
 *       const cached = await redis.get(cacheKey);
 *       if (cached) return JSON.parse(cached);
 *
 *       const result = await getRestaurantDetail(slug);
 *       if (!result) {
 *         return reply.status(404).send({
 *           statusCode: 404,
 *           error: "Not Found",
 *           message: `Restoran bulunamadi: ${slug}`,
 *         });
 *       }
 *
 *       await redis.setex(cacheKey, 900, JSON.stringify(result));
 *       return result;
 *     }
 *   );
 *
 *   // --- 3. Dish Detail ---
 *   server.get(
 *     "/api/v1/dishes/:slug",
 *     {
 *       schema: {
 *         params: DishDetailParamsSchema,
 *       },
 *     },
 *     async (request, reply) => {
 *       const { slug } = request.params;
 *       const cacheKey = `dish:${slug}`;
 *       const cached = await redis.get(cacheKey);
 *       if (cached) return JSON.parse(cached);
 *
 *       const result = await getDishDetail(slug);
 *       if (!result) {
 *         return reply.status(404).send({
 *           statusCode: 404,
 *           error: "Not Found",
 *           message: `Yemek bulunamadi: ${slug}`,
 *         });
 *       }
 *
 *       await redis.setex(cacheKey, 1800, JSON.stringify(result));
 *       return result;
 *     }
 *   );
 *
 *   // --- 4. Autocomplete ---
 *   server.get(
 *     "/api/v1/autocomplete",
 *     {
 *       schema: {
 *         querystring: AutocompleteQuerySchema,
 *       },
 *       config: {
 *         rateLimit: {
 *           max: 30,
 *           timeWindow: "1 minute",
 *         },
 *       },
 *     },
 *     async (request, reply) => {
 *       const q = request.query.q.trim().toLowerCase();
 *       const cacheKey = `autocomplete:${q}`;
 *       const cached = await redis.get(cacheKey);
 *       if (cached) return JSON.parse(cached);
 *
 *       const result = await getAutocomplete(q);
 *       await redis.setex(cacheKey, 3600, JSON.stringify(result));
 *       return result;
 *     }
 *   );
 * }
 *
 * // Cache key builder: query parametrelerinin hash'i
 * function buildSearchCacheKey(query: Record<string, unknown>): string {
 *   const sorted = Object.keys(query)
 *     .sort()
 *     .map((k) => `${k}=${query[k] ?? ""}`)
 *     .join("&");
 *   // Basit hash (uretimde crypto.createHash('sha256') kullanilabilir)
 *   let hash = 0;
 *   for (let i = 0; i < sorted.length; i++) {
 *     const char = sorted.charCodeAt(i);
 *     hash = ((hash << 5) - hash + char) | 0;
 *   }
 *   return `search:${Math.abs(hash).toString(16)}`;
 * }
 * ```
 */

// ============================================================================
// REDIS CACHE OZET TABLOSU
// ============================================================================

/**
 * +---------------------+-------------------------------+-----------+-------------------------+
 * | Endpoint            | Key Format                    | TTL       | Invalidation Tetigi     |
 * +---------------------+-------------------------------+-----------+-------------------------+
 * | /search             | search:{hash}                 | 5 dk      | TTL-expire (yeterli)    |
 * |                     |                               |           | + food_scores update    |
 * +---------------------+-------------------------------+-----------+-------------------------+
 * | /restaurants/:slug  | restaurant:{slug}             | 15 dk     | Restoran/yorum/food     |
 * |                     |                               |           | score degisiminde DEL   |
 * +---------------------+-------------------------------+-----------+-------------------------+
 * | /dishes/:slug       | dish:{slug}                   | 30 dk     | food_scores update      |
 * |                     |                               |           | restaurant_dishes chg   |
 * +---------------------+-------------------------------+-----------+-------------------------+
 * | /autocomplete       | autocomplete:{normalizedQ}    | 1 saat    | Yeni restoran/yemek     |
 * |                     |                               |           | eklendiginde (nadir)    |
 * +---------------------+-------------------------------+-----------+-------------------------+
 *
 * GENEL INVALIDATION STRATEJISI:
 * - NLP pipeline tamamlandiginda: butun etkilenen restaurant:{slug} ve dish:{slug} keyleri temizlenir
 * - Yeni restoran eklendiginde: autocomplete:* ve ilgili search:* keyleri temizlenir
 * - Gunluk bakim: Redis SCAN ile suresi dolmus keylerin kontrolu (TTL otomatik halleder)
 */

// ============================================================================
// PERFORMANS HEDEFLERI OZET TABLOSU
// ============================================================================

/**
 * +---------------------+------------------+------------------+--------------------------+
 * | Endpoint            | Cache Miss (max) | Cache Hit (max)  | Kritik Optimizasyon      |
 * +---------------------+------------------+------------------+--------------------------+
 * | /search             | 300ms            | 50ms             | FTS indeks + parallel    |
 * |                     |                  |                  | food_scores sorgusu      |
 * +---------------------+------------------+------------------+--------------------------+
 * | /restaurants/:slug  | 200ms            | 30ms             | Promise.all (4 sorgu     |
 * |                     |                  |                  | paralel)                 |
 * +---------------------+------------------+------------------+--------------------------+
 * | /dishes/:slug       | 250ms            | 30ms             | unaccent+lower indeks,   |
 * |                     |                  |                  | LIMIT 20                 |
 * +---------------------+------------------+------------------+--------------------------+
 * | /autocomplete       | 150ms            | 20ms             | pg_trgm indeks, LIMIT 5, |
 * |                     |                  |                  | agresif cache (1 saat)   |
 * +---------------------+------------------+------------------+--------------------------+
 *
 * ORTAK OPTIMIZASYONLAR:
 * - Connection pooling: postgres.js max=10, idle_timeout=20s
 * - Prepared statements: Drizzle ORM otomatik olarak kullanir
 * - Redis pipeline: Autocomplete icin restoran+yemek tek roundtrip
 * - Indeks kullanimi: GIN (FTS, trigram), GiST (PostGIS), B-tree (FK, score)
 */

// ============================================================================
// RATE LIMITING DETAYLARI
// ============================================================================

/**
 * Global:       100 req/dk per IP (mevcut @fastify/rate-limit konfigurasyonu)
 * /autocomplete: 30 req/dk per IP (ek konfigurayon - yuksek trafik riski)
 * /search:       Global limit yeterli
 * /restaurants:  Global limit yeterli
 * /dishes:       Global limit yeterli
 *
 * Rate limit asildifinda:
 * {
 *   "statusCode": 429,
 *   "error": "Too Many Requests",
 *   "message": "Rate limit asildi. Lutfen 60 saniye sonra tekrar deneyin."
 * }
 */

// ============================================================================
// TECRUBE NOTLARI
// ============================================================================

/**
 * ---TECRUBE BASLANGIC---
 * ## iyisiniye.com - 2026-02-01
 * ### Gorev: TASK-035 API endpoint sozlesmesi
 *
 * 1. DB SEMASI ANALIZI:
 *    - food_scores tablosu UNIQUE(restaurantId, foodName) constraint'ine sahip.
 *      Bu, dishes tablosundaki canonicalName ile food_scores.foodName arasindaki
 *      eslestirmenin unaccent+lower ile yapilmasini gerektiriyor.
 *    - reviews tablosu dogrudan restaurantId icermiyor, restaurant_platforms
 *      uzerinden baglanti kuruluyor. Bu, restoran detay sorgusunda ek JOIN gerektiriyor.
 *    - overallScore decimal(3,2) yani max 9.99. food_scores.score ise decimal(4,2)
 *      yani max 99.99 ama 1-10 arasi kullanilacak.
 *
 * 2. TURKCE ARAMA STRATEJISI:
 *    - pg_trgm similarity_threshold=0.2 Turkce icin iyi calisiyor (test edildi).
 *    - unaccent eklentisi aktif: "ciya" yazinca "Çiya" da bulunuyor.
 *    - to_tsvector('turkish', ...) Turkce stemming yapiyor: "kebaplar" -> "kebap".
 *    - FTS + trigram birlestirmesi: once FTS rank, sonra trigram similarity ile
 *      fallback. Bu yaklasim hem tam eslesmede hem de typo toleransinda iyi sonuc veriyor.
 *
 * 3. CACHE KATMANI:
 *    - Redis henuz entegre degil. ioredis paketinin eklenmesi gerekiyor.
 *    - Cache key stratejisi: search icin hash-based (parametreler degisken),
 *      diger endpointler icin slug-based (deterministik).
 *    - Autocomplete agresif cache (1 saat) mantikli cunku yemek/restoran isimleri
 *      nadiren degisiyor. Yeni eklenmeler NLP pipeline sonrasi geliyor.
 *
 * 4. MIMARI KARARLAR:
 *    - Service layer pattern: Her endpoint icin ayri service fonksiyonu.
 *    - Drizzle ORM raw SQL kullanimi: PostGIS ve pg_trgm fonksiyonlari icin
 *      sql`` template literal zorunlu.
 *    - Zod + fastify-type-provider-zod: Compile-time tip guvenligi + runtime validasyon.
 *    - Response'larda decimal degerler string olarak donuyor (JavaScript floating point
 *      hassasiyeti sorunu icin). Frontend parseFloat ile cevirecek.
 *
 * 5. EKSIK/GELECEK ISLER:
 *    - Redis entegrasyonu (ioredis kurulumu + connection config)
 *    - Error handling middleware (global Fastify error handler)
 *    - Request logging middleware (pino zaten var, structured log eklenmeli)
 *    - Health check'e DB ve Redis baglanti durumu eklenmeli
 *    - food_scores.foodName <-> dishes.canonicalName eslestirme tutarliligi
 *      icin bir normalizasyon fonksiyonu gerekiyor
 *
 * ---TECRUBE BITIS---
 */
