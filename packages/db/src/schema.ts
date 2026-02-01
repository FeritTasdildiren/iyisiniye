/**
 * iyisiniye Veritabani Semasi - Drizzle ORM
 *
 * 8 tablo: restaurants, restaurant_platforms, dishes, restaurant_dishes,
 *          reviews, review_dish_mentions, scrape_jobs, advertisements
 *
 * Aktif PostgreSQL eklentileri:
 *   - PostGIS 3.5.2 (mekansal sorgular)
 *   - pg_trgm 1.6 (benzerlik arama - trigram)
 *   - unaccent 1.1 (aksan/ozel karakter kaldirim)
 *
 * Veritabani: postgresql://iyisiniye_app:...@157.173.116.230:5433/iyisiniye
 */

import { relations, sql } from "drizzle-orm";
import {
  boolean,
  customType,
  date,
  decimal,
  index,
  integer,
  jsonb,
  pgTable,
  serial,
  smallint,
  text,
  timestamp,
  uniqueIndex,
  varchar,
} from "drizzle-orm/pg-core";

// ============================================================================
// OZEL TIPLER (Custom Types)
// ============================================================================

/**
 * PostGIS geography(POINT, 4326) tipi.
 * Enlem/boylam degerlerini WGS84 koordinat sisteminde saklar.
 */
const geography = customType<{
  data: { lat: number; lng: number };
  driverData: string;
}>({
  dataType() {
    return "geography(POINT, 4326)";
  },
  toDriver(value: { lat: number; lng: number }): string {
    return `SRID=4326;POINT(${value.lng} ${value.lat})`;
  },
  fromDriver(value: string): { lat: number; lng: number } {
    // PostGIS WKT formati: POINT(lng lat) veya hex WKB
    // WKT parse
    const match = value.match(/POINT\(([^ ]+) ([^ ]+)\)/);
    if (match) {
      return {
        lng: parseFloat(match[1]),
        lat: parseFloat(match[2]),
      };
    }
    // Deger parse edilemezse varsayilan dondur
    return { lat: 0, lng: 0 };
  },
});

/**
 * PostgreSQL tsvector tipi (tam metin arama icin).
 */
const tsvector = customType<{
  data: string;
  driverData: string;
}>({
  dataType() {
    return "tsvector";
  },
  toDriver(value: string): string {
    return value;
  },
  fromDriver(value: string): string {
    return value;
  },
});

// ============================================================================
// TABLO 1: restaurants - Restoran Bilgileri
// ============================================================================

export const restaurants = pgTable(
  "restaurants",
  {
    id: serial("id").primaryKey(),
    name: varchar("name", { length: 255 }).notNull(),
    slug: varchar("slug", { length: 255 }).unique().notNull(),
    address: text("address"),
    district: varchar("district", { length: 100 }),
    neighborhood: varchar("neighborhood", { length: 100 }),
    location: geography("location"),
    phone: varchar("phone", { length: 20 }),
    website: varchar("website", { length: 500 }),
    cuisineType: text("cuisine_type").array(),
    priceRange: smallint("price_range"), // 1-4 arasi
    overallScore: decimal("overall_score", { precision: 3, scale: 2 }),
    totalReviews: integer("total_reviews").default(0).notNull(),
    isActive: boolean("is_active").default(true).notNull(),
    imageUrl: varchar("image_url", { length: 500 }),
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [
    // GIN indeks: Tam metin arama (name + address)
    index("idx_restaurants_fts").using(
      "gin",
      sql`to_tsvector('turkish', coalesce(${table.name}, '') || ' ' || coalesce(${table.address}, ''))`
    ),
    // GIN indeks: Trigram benzerlik arama (name)
    index("idx_restaurants_name_trgm").using(
      "gin",
      sql`${table.name} gin_trgm_ops`
    ),
    // GiST indeks: PostGIS mekansal sorgular (location)
    index("idx_restaurants_location").using("gist", table.location),
  ]
);

// ============================================================================
// TABLO 2: restaurant_platforms - Restoran Platform Baglantilari
// ============================================================================

export const restaurantPlatforms = pgTable(
  "restaurant_platforms",
  {
    id: serial("id").primaryKey(),
    restaurantId: integer("restaurant_id")
      .references(() => restaurants.id, { onDelete: "cascade" })
      .notNull(),
    platform: varchar("platform", { length: 50 }).notNull(),
    externalId: varchar("external_id", { length: 255 }).notNull(),
    externalUrl: varchar("external_url", { length: 1000 }),
    platformScore: decimal("platform_score", { precision: 3, scale: 2 }),
    platformReviews: integer("platform_reviews").default(0).notNull(),
    matchConfidence: decimal("match_confidence", { precision: 3, scale: 2 }),
    lastScraped: timestamp("last_scraped", { withTimezone: true }),
    rawData: jsonb("raw_data"),
  },
  (table) => [
    // Benzersiz: Bir platformda bir restoran sadece bir kez olabilir
    uniqueIndex("idx_restaurant_platforms_unique").on(
      table.platform,
      table.externalId
    ),
    // B-tree: Restoran ID'ye gore hizli arama
    index("idx_restaurant_platforms_restaurant_id").on(table.restaurantId),
  ]
);

// ============================================================================
// TABLO 3: dishes - Yemek Bilgileri
// ============================================================================

export const dishes = pgTable(
  "dishes",
  {
    id: serial("id").primaryKey(),
    name: varchar("name", { length: 255 }).notNull(),
    slug: varchar("slug", { length: 255 }).unique().notNull(),
    canonicalName: varchar("canonical_name", { length: 255 }),
    category: varchar("category", { length: 50 }),
    subcategory: varchar("subcategory", { length: 100 }),
    isMainDish: boolean("is_main_dish").default(true).notNull(),
    aliases: text("aliases").array(),
    searchVector: tsvector("search_vector"),
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [
    // GIN indeks: Tam metin arama (search_vector)
    index("idx_dishes_search_vector").using("gin", table.searchVector),
    // GIN indeks: Trigram benzerlik arama (canonical_name)
    index("idx_dishes_canonical_name_trgm").using(
      "gin",
      sql`${table.canonicalName} gin_trgm_ops`
    ),
  ]
);

// ============================================================================
// TABLO 4: restaurant_dishes - Restoran-Yemek Iliskisi
// ============================================================================

export const restaurantDishes = pgTable(
  "restaurant_dishes",
  {
    id: serial("id").primaryKey(),
    restaurantId: integer("restaurant_id")
      .references(() => restaurants.id, { onDelete: "cascade" })
      .notNull(),
    dishId: integer("dish_id")
      .references(() => dishes.id, { onDelete: "cascade" })
      .notNull(),
    avgSentiment: decimal("avg_sentiment", { precision: 3, scale: 2 }),
    positiveCount: integer("positive_count").default(0).notNull(),
    negativeCount: integer("negative_count").default(0).notNull(),
    neutralCount: integer("neutral_count").default(0).notNull(),
    totalMentions: integer("total_mentions").default(0).notNull(),
    computedScore: decimal("computed_score", { precision: 3, scale: 2 }),
    price: decimal("price", { precision: 8, scale: 2 }),
    lastUpdated: timestamp("last_updated", { withTimezone: true }),
  },
  (table) => [
    // Benzersiz: Bir restoran-yemek cifti sadece bir kez olabilir
    uniqueIndex("idx_restaurant_dishes_unique").on(
      table.restaurantId,
      table.dishId
    ),
    // B-tree: Restoran ve yemek ID'ye gore hizli arama
    index("idx_restaurant_dishes_restaurant_id_dish_id").on(
      table.restaurantId,
      table.dishId
    ),
  ]
);

// ============================================================================
// TABLO 5: reviews - Kullanici Yorumlari
// ============================================================================

export const reviews = pgTable(
  "reviews",
  {
    id: serial("id").primaryKey(),
    restaurantPlatformId: integer("restaurant_platform_id")
      .references(() => restaurantPlatforms.id, { onDelete: "cascade" })
      .notNull(),
    externalReviewId: varchar("external_review_id", { length: 255 }),
    authorName: varchar("author_name", { length: 255 }),
    rating: smallint("rating"),
    text: text("text").notNull(),
    reviewDate: timestamp("review_date", { withTimezone: true }),
    language: varchar("language", { length: 10 }).default("tr").notNull(),
    scrapedAt: timestamp("scraped_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
    processed: boolean("processed").default(false).notNull(),
  },
  (table) => [
    // Benzersiz: Bir platformda bir yorum sadece bir kez olabilir
    uniqueIndex("idx_reviews_unique").on(
      table.restaurantPlatformId,
      table.externalReviewId
    ),
    // B-tree: Platform ID'ye gore hizli arama
    index("idx_reviews_restaurant_platform_id").on(
      table.restaurantPlatformId
    ),
    // B-tree: Islenmemis yorumlari hizli bulmak icin kismi indeks
    index("idx_reviews_unprocessed").on(table.processed).where(
      sql`NOT ${table.processed}`
    ),
  ]
);

// ============================================================================
// TABLO 6: review_dish_mentions - Yorum Icindeki Yemek Bahisleri
// ============================================================================

export const reviewDishMentions = pgTable(
  "review_dish_mentions",
  {
    id: serial("id").primaryKey(),
    reviewId: integer("review_id")
      .references(() => reviews.id, { onDelete: "cascade" })
      .notNull(),
    dishId: integer("dish_id")
      .references(() => dishes.id, { onDelete: "cascade" })
      .notNull(),
    mentionText: text("mention_text"),
    sentiment: varchar("sentiment", { length: 10 }), // positive, negative, neutral
    sentimentScore: decimal("sentiment_score", { precision: 4, scale: 3 }),
    extractionMethod: varchar("extraction_method", { length: 20 }), // nlp, regex, manual
    confidence: decimal("confidence", { precision: 3, scale: 2 }),
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [
    // B-tree: Yorum ve yemek ID'ye gore hizli arama
    index("idx_review_dish_mentions_review_id").on(table.reviewId),
    index("idx_review_dish_mentions_dish_id").on(table.dishId),
  ]
);

// ============================================================================
// TABLO 7: scrape_jobs - Scrape Gorev Kayitlari
// ============================================================================

export const scrapeJobs = pgTable(
  "scrape_jobs",
  {
    id: serial("id").primaryKey(),
    platform: varchar("platform", { length: 50 }).notNull(),
    targetType: varchar("target_type", { length: 50 }).notNull(),
    targetId: varchar("target_id", { length: 255 }),
    status: varchar("status", { length: 20 }).default("pending").notNull(),
    startedAt: timestamp("started_at", { withTimezone: true }),
    completedAt: timestamp("completed_at", { withTimezone: true }),
    itemsScraped: integer("items_scraped").default(0).notNull(),
    errorMessage: text("error_message"),
    metadata: jsonb("metadata"),
  },
  (table) => [
    // B-tree: Durum ve platforma gore arama
    index("idx_scrape_jobs_status").on(table.status),
    index("idx_scrape_jobs_platform").on(table.platform),
  ]
);

// ============================================================================
// TABLO 8: advertisements - Reklam Bilgileri
// ============================================================================

export const advertisements = pgTable(
  "advertisements",
  {
    id: serial("id").primaryKey(),
    restaurantId: integer("restaurant_id")
      .references(() => restaurants.id, { onDelete: "cascade" })
      .notNull(),
    adType: varchar("ad_type", { length: 50 }).notNull(),
    title: varchar("title", { length: 255 }),
    content: text("content"),
    imageUrl: varchar("image_url", { length: 500 }),
    targetUrl: varchar("target_url", { length: 500 }),
    startDate: date("start_date"),
    endDate: date("end_date"),
    isActive: boolean("is_active").default(false).notNull(),
    impressions: integer("impressions").default(0).notNull(),
    clicks: integer("clicks").default(0).notNull(),
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [
    // B-tree: Restoran ID'ye gore arama
    index("idx_advertisements_restaurant_id").on(table.restaurantId),
    // B-tree: Aktif reklamlari hizli bulmak icin
    index("idx_advertisements_active").on(table.isActive).where(
      sql`${table.isActive} = true`
    ),
  ]
);

// ============================================================================
// TABLO 9: food_mentions - NLP Yemek Bahisleri
// ============================================================================

export const foodMentions = pgTable(
  "food_mentions",
  {
    id: serial("id").primaryKey(),
    reviewId: integer("review_id")
      .references(() => reviews.id, { onDelete: "cascade" })
      .notNull(),
    foodName: varchar("food_name", { length: 255 }).notNull(),
    canonicalName: varchar("canonical_name", { length: 255 }),
    category: varchar("category", { length: 100 }),
    confidence: decimal("confidence", { precision: 4, scale: 3 }),
    sentiment: varchar("sentiment", { length: 10 }),
    sentimentScore: decimal("sentiment_score", { precision: 4, scale: 3 }),
    isFood: boolean("is_food").default(true).notNull(),
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [
    index("idx_food_mentions_review_id").on(table.reviewId),
    index("idx_food_mentions_canonical_name").on(table.canonicalName),
    index("idx_food_mentions_category").on(table.category),
  ]
);

// ============================================================================
// TABLO 10: food_scores - NLP Yemek Puanlari
// ============================================================================

export const foodScores = pgTable(
  "food_scores",
  {
    id: serial("id").primaryKey(),
    restaurantId: integer("restaurant_id")
      .references(() => restaurants.id, { onDelete: "cascade" })
      .notNull(),
    foodName: varchar("food_name", { length: 255 }).notNull(),
    score: decimal("score", { precision: 4, scale: 2 }).notNull(),
    reviewCount: integer("review_count").default(0).notNull(),
    confidence: decimal("confidence", { precision: 4, scale: 3 }),
    sentimentDistribution: jsonb("sentiment_distribution"),
    lastUpdated: timestamp("last_updated", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [
    uniqueIndex("idx_food_scores_unique").on(
      table.restaurantId,
      table.foodName
    ),
    index("idx_food_scores_restaurant_id").on(table.restaurantId),
    index("idx_food_scores_score").on(table.score),
  ]
);

// ============================================================================
// TABLO 11: nlp_jobs - NLP Pipeline Gorev Kayitlari
// ============================================================================

export const nlpJobs = pgTable(
  "nlp_jobs",
  {
    id: serial("id").primaryKey(),
    startedAt: timestamp("started_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
    completedAt: timestamp("completed_at", { withTimezone: true }),
    reviewsProcessed: integer("reviews_processed").default(0).notNull(),
    foodMentionsCreated: integer("food_mentions_created").default(0).notNull(),
    foodScoresUpdated: integer("food_scores_updated").default(0).notNull(),
    status: varchar("status", { length: 20 }).default("running").notNull(),
    errorLog: text("error_log"),
  },
  (table) => [
    index("idx_nlp_jobs_status").on(table.status),
  ]
);

// ============================================================================
// ILISKILER (Relations)
// ============================================================================

/**
 * restaurants iliskileri:
 *   - restaurant_platforms (1:N)
 *   - restaurant_dishes (1:N)
 *   - advertisements (1:N)
 */
export const restaurantsRelations = relations(restaurants, ({ many }) => ({
  platforms: many(restaurantPlatforms),
  dishes: many(restaurantDishes),
  advertisements: many(advertisements),
  foodScores: many(foodScores),
}));

/**
 * restaurant_platforms iliskileri:
 *   - restaurants (N:1)
 *   - reviews (1:N)
 */
export const restaurantPlatformsRelations = relations(
  restaurantPlatforms,
  ({ one, many }) => ({
    restaurant: one(restaurants, {
      fields: [restaurantPlatforms.restaurantId],
      references: [restaurants.id],
    }),
    reviews: many(reviews),
  })
);

/**
 * dishes iliskileri:
 *   - restaurant_dishes (1:N)
 *   - review_dish_mentions (1:N)
 */
export const dishesRelations = relations(dishes, ({ many }) => ({
  restaurantDishes: many(restaurantDishes),
  mentions: many(reviewDishMentions),
}));

/**
 * restaurant_dishes iliskileri:
 *   - restaurants (N:1)
 *   - dishes (N:1)
 */
export const restaurantDishesRelations = relations(
  restaurantDishes,
  ({ one }) => ({
    restaurant: one(restaurants, {
      fields: [restaurantDishes.restaurantId],
      references: [restaurants.id],
    }),
    dish: one(dishes, {
      fields: [restaurantDishes.dishId],
      references: [dishes.id],
    }),
  })
);

/**
 * reviews iliskileri:
 *   - restaurant_platforms (N:1)
 *   - review_dish_mentions (1:N)
 */
export const reviewsRelations = relations(reviews, ({ one, many }) => ({
  restaurantPlatform: one(restaurantPlatforms, {
    fields: [reviews.restaurantPlatformId],
    references: [restaurantPlatforms.id],
  }),
  dishMentions: many(reviewDishMentions),
  foodMentions: many(foodMentions),
}));

/**
 * review_dish_mentions iliskileri:
 *   - reviews (N:1)
 *   - dishes (N:1)
 */
export const reviewDishMentionsRelations = relations(
  reviewDishMentions,
  ({ one }) => ({
    review: one(reviews, {
      fields: [reviewDishMentions.reviewId],
      references: [reviews.id],
    }),
    dish: one(dishes, {
      fields: [reviewDishMentions.dishId],
      references: [dishes.id],
    }),
  })
);

/**
 * advertisements iliskileri:
 *   - restaurants (N:1)
 */
export const advertisementsRelations = relations(
  advertisements,
  ({ one }) => ({
    restaurant: one(restaurants, {
      fields: [advertisements.restaurantId],
      references: [restaurants.id],
    }),
  })
);

/**
 * food_mentions iliskileri:
 *   - reviews (N:1)
 */
export const foodMentionsRelations = relations(
  foodMentions,
  ({ one }) => ({
    review: one(reviews, {
      fields: [foodMentions.reviewId],
      references: [reviews.id],
    }),
  })
);

/**
 * food_scores iliskileri:
 *   - restaurants (N:1)
 */
export const foodScoresRelations = relations(
  foodScores,
  ({ one }) => ({
    restaurant: one(restaurants, {
      fields: [foodScores.restaurantId],
      references: [restaurants.id],
    }),
  })
);
