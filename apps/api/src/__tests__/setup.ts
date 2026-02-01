/**
 * Vitest Global Setup
 *
 * DB ve Redis mock'larini yukler.
 * Testler gercek veritabanina veya Redis'e baglanmaz.
 */

import { vi } from "vitest";

// ---- Redis Mock ----
const redisStore = new Map<string, { value: string; expiry: number | null }>();

vi.mock("../lib/redis.js", () => ({
  redis: {
    get: vi.fn(async (key: string) => {
      const entry = redisStore.get(key);
      if (!entry) return null;
      if (entry.expiry && Date.now() > entry.expiry) {
        redisStore.delete(key);
        return null;
      }
      return entry.value;
    }),
    set: vi.fn(async (key: string, value: string, _mode?: string, ttl?: number) => {
      redisStore.set(key, {
        value,
        expiry: ttl ? Date.now() + ttl * 1000 : null,
      });
      return "OK";
    }),
    del: vi.fn(async (...keys: string[]) => {
      let count = 0;
      for (const key of keys) {
        if (redisStore.delete(key)) count++;
      }
      return count;
    }),
    scan: vi.fn(async () => ["0", []]),
    quit: vi.fn(async () => "OK"),
    disconnect: vi.fn(),
    on: vi.fn(),
  },
}));

// ---- Chainable Mock Query Builder ----
// Drizzle ORM'nin chainable query builder'ini simule eder.
// Her chain metodu ayni builder'i dondurur.
// await edildiginde configuredResult'u dondurur.

let queryResults: unknown[][] = [];
let queryCallIndex = 0;

/**
 * Siradaki DB sorgularinin dondurecegi sonuclari ayarlar.
 * Her eleman bir sorgunun sonucudur. Sirayla tuketilir.
 *
 * Ornek:
 *   setQueryResults([
 *     [{ id: 1, name: "Restoran A" }],  // ilk sorgu
 *     [{ count: 1 }],                    // ikinci sorgu
 *   ]);
 */
export function setQueryResults(results: unknown[][]) {
  queryResults = results;
  queryCallIndex = 0;
}

function getNextResult(): unknown[] {
  if (queryCallIndex < queryResults.length) {
    return queryResults[queryCallIndex++];
  }
  return [];
}

function createChainableBuilder(): Record<string, unknown> {
  const builder: Record<string, unknown> = {};

  const chainMethods = [
    "select",
    "from",
    "where",
    "orderBy",
    "limit",
    "offset",
    "innerJoin",
    "leftJoin",
    "rightJoin",
    "fullJoin",
    "groupBy",
    "having",
  ];

  for (const method of chainMethods) {
    builder[method] = vi.fn((): unknown => builder);
  }

  // Promise.all destegi icin thenable yapiyoruz
  builder.then = function (
    resolve?: (val: unknown) => unknown,
    reject?: (err: unknown) => unknown
  ) {
    const result = getNextResult();
    if (resolve) return Promise.resolve(result).then(resolve, reject);
    return Promise.resolve(result);
  };

  // catch ve finally - Promise uyumlulugu
  builder.catch = function (reject?: (err: unknown) => unknown) {
    return Promise.resolve([]).catch(reject);
  };
  builder.finally = function (cb?: () => void) {
    return Promise.resolve([]).finally(cb);
  };

  return builder;
}

// Mock DB instance
const mockDb = {
  select: vi.fn((_fields?: unknown): unknown => {
    return createChainableBuilder();
  }),
  insert: vi.fn((): unknown => {
    const builder = createChainableBuilder();
    builder.values = vi.fn((): unknown => builder);
    builder.returning = vi.fn((): unknown => builder);
    return builder;
  }),
  update: vi.fn((): unknown => {
    const builder = createChainableBuilder();
    builder.set = vi.fn((): unknown => builder);
    builder.returning = vi.fn((): unknown => builder);
    return builder;
  }),
  delete: vi.fn((): unknown => {
    return createChainableBuilder();
  }),
};

vi.mock("@iyisiniye/db", () => {
  // Schema tablolari - route'lardaki sql template literal'lerinde referans olarak kullanilir
  const restaurants = {
    id: "id", name: "name", slug: "slug", address: "address",
    district: "district", neighborhood: "neighborhood", location: "location",
    phone: "phone", website: "website", cuisineType: "cuisine_type",
    priceRange: "price_range", overallScore: "overall_score",
    totalReviews: "total_reviews", isActive: "is_active",
    imageUrl: "image_url", createdAt: "created_at", updatedAt: "updated_at",
  };
  const restaurantPlatforms = {
    id: "id", restaurantId: "restaurant_id", platform: "platform",
    externalId: "external_id", externalUrl: "external_url",
    platformScore: "platform_score", platformReviews: "platform_reviews",
    matchConfidence: "match_confidence", lastScraped: "last_scraped",
    rawData: "raw_data",
  };
  const dishes = {
    id: "id", name: "name", slug: "slug", canonicalName: "canonical_name",
    category: "category", subcategory: "subcategory", isMainDish: "is_main_dish",
    aliases: "aliases", searchVector: "search_vector", createdAt: "created_at",
  };
  const foodScores = {
    id: "id", restaurantId: "restaurant_id", foodName: "food_name",
    score: "score", reviewCount: "review_count", confidence: "confidence",
    sentimentDistribution: "sentiment_distribution", lastUpdated: "last_updated",
  };
  const foodMentions = {
    id: "id", reviewId: "review_id", foodName: "food_name",
    canonicalName: "canonical_name", category: "category",
    confidence: "confidence", sentiment: "sentiment",
    sentimentScore: "sentiment_score", isFood: "is_food",
    createdAt: "created_at",
  };
  const reviews = {
    id: "id", restaurantPlatformId: "restaurant_platform_id",
    externalReviewId: "external_review_id", authorName: "author_name",
    rating: "rating", text: "text", reviewDate: "review_date",
    language: "language", scrapedAt: "scraped_at", processed: "processed",
  };
  const restaurantDishes = { id: "id", restaurantId: "restaurant_id", dishId: "dish_id" };
  const reviewDishMentions = { id: "id", reviewId: "review_id", dishId: "dish_id" };

  return {
    db: mockDb,
    restaurants,
    restaurantPlatforms,
    dishes,
    foodScores,
    foodMentions,
    reviews,
    restaurantDishes,
    reviewDishMentions,
    closeConnection: vi.fn(),
  };
});

// ---- Drizzle ORM Mock ----
// sql tagged template, eq, and, desc vb. fonksiyonlari basit pass-through mock olarak tanimliyoruz.
// Route handler'lar bunlari DB sorgularinda kullaniyor ama bizim mock DB bunlari yok sayiyor.
vi.mock("drizzle-orm", () => {
  // Proxy-based sql result: uzerinde herhangi bir metod cagirildiginda
  // (as, join, raw vb.) yine benzer bir proxy dondurur.
  function createSqlProxy(tag = "sql"): unknown {
    const target = { _tag: tag };
    return new Proxy(target, {
      get(_obj, prop) {
        if (prop === "_tag") return tag;
        if (prop === Symbol.toPrimitive) return () => `[${tag}]`;
        if (prop === "toString") return () => `[${tag}]`;
        if (prop === "toJSON") return () => ({ _tag: tag });
        // Herhangi bir property erisiminde fonksiyon dondur
        return (..._args: unknown[]) => createSqlProxy(`${tag}.${String(prop)}`);
      },
    });
  }

  // sql tagged template literal mock
  const sqlFn = (_strings: unknown, ..._values: unknown[]) => {
    return createSqlProxy("sql");
  };
  sqlFn.join = (_items: unknown[], _sep?: unknown) => createSqlProxy("sql.join");
  sqlFn.raw = (_s: string) => createSqlProxy("sql.raw");

  return {
    sql: sqlFn,
    eq: vi.fn((_col: unknown, _val: unknown) => createSqlProxy("eq")),
    and: vi.fn((..._conditions: unknown[]) => createSqlProxy("and")),
    or: vi.fn((..._conditions: unknown[]) => createSqlProxy("or")),
    gte: vi.fn((_col: unknown, _val: unknown) => createSqlProxy("gte")),
    lte: vi.fn((_col: unknown, _val: unknown) => createSqlProxy("lte")),
    desc: vi.fn((_col: unknown) => createSqlProxy("desc")),
    asc: vi.fn((_col: unknown) => createSqlProxy("asc")),
    inArray: vi.fn((_col: unknown, _arr: unknown[]) => createSqlProxy("inArray")),
    not: vi.fn((_condition: unknown) => createSqlProxy("not")),
    isNull: vi.fn((_col: unknown) => createSqlProxy("isNull")),
    isNotNull: vi.fn((_col: unknown) => createSqlProxy("isNotNull")),
    like: vi.fn((_col: unknown, _val: string) => createSqlProxy("like")),
    ilike: vi.fn((_col: unknown, _val: string) => createSqlProxy("ilike")),
    relations: vi.fn(() => ({})),
  };
});

// dotenv mock - test ortaminda .env dosyasi gerekmesin
vi.mock("dotenv/config", () => ({}));

export function clearRedisStore() {
  redisStore.clear();
}

export function resetQueryMocks() {
  queryResults = [];
  queryCallIndex = 0;
  mockDb.select.mockClear();
  mockDb.insert.mockClear();
  mockDb.update.mockClear();
  mockDb.delete.mockClear();
}

export { mockDb, redisStore };
