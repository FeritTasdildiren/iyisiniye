/**
 * GET /api/v1/search - Restoran & Yemek Arama
 *
 * FTS + pg_trgm fuzzy + PostGIS mesafe kombine arama.
 * Her restoran icin en iyi 3 yemek (food_scores).
 */

import type { FastifyInstance } from "fastify";
import type { ZodTypeProvider } from "fastify-type-provider-zod";
import { db, restaurants, foodScores } from "@iyisiniye/db";
import { sql, and, eq, gte, desc } from "drizzle-orm";
import { z } from "zod/v4";
import { createHash } from "crypto";
import { cacheGet, cacheSet } from "../lib/cache.js";

// --- Zod Schemas ---

const SearchQuerySchema = z.object({
  q: z.string().min(2, "Arama sorgusu en az 2 karakter olmalidir.").max(100),
  district: z.string().max(100).optional(),
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
  price_range: z.coerce.number().int().min(1).max(4).optional(),
  min_score: z.coerce.number().min(1).max(10).optional(),
  sort_by: z.enum(["score", "distance", "newest"]).default("score"),
  page: z.coerce.number().int().positive().default(1),
  limit: z.coerce.number().int().min(1).max(50).default(20),
  lat: z.coerce.number().min(-90).max(90).optional(),
  lng: z.coerce.number().min(-180).max(180).optional(),
});

// --- Route ---

export async function searchRoutes(app: FastifyInstance) {
  const server = app.withTypeProvider<ZodTypeProvider>();

  server.get(
    "/api/v1/search",
    {
      schema: {
        querystring: SearchQuerySchema,
      },
    },
    async (request, reply) => {
      const {
        q,
        district,
        cuisine,
        price_range,
        min_score,
        sort_by,
        page,
        limit,
        lat,
        lng,
      } = request.query;

      // Cache kontrolu
      const cacheKey = `search:${createHash("md5").update(JSON.stringify(Object.fromEntries(Object.entries(request.query).sort()))).digest("hex")}`;
      const cached = await cacheGet(cacheKey);
      if (cached) {
        reply.header("X-Cache", "HIT");
        return cached;
      }

      // sort_by=distance ama lat/lng yoksa hata
      if (sort_by === "distance" && (lat == null || lng == null)) {
        return reply.status(400).send({
          statusCode: 400,
          error: "Bad Request",
          message:
            "Mesafeye gore siralama icin lat ve lng parametreleri gereklidir.",
        });
      }

      const offset = (page - 1) * limit;

      // Dinamik WHERE kosullari
      const conditions: ReturnType<typeof sql>[] = [
        sql`${restaurants.isActive} = true`,
        // FTS + Trigram birlestirmesi
        sql`(
          to_tsvector('turkish', coalesce(${restaurants.name}, '') || ' ' || coalesce(${restaurants.address}, ''))
          @@ plainto_tsquery('turkish', unaccent(${q}))
          OR similarity(${restaurants.name}, ${q}) > 0.2
        )`,
      ];

      if (district) {
        conditions.push(
          sql`lower(${restaurants.district}) = lower(${district})`
        );
      }

      if (cuisine) {
        conditions.push(sql`${cuisine} = ANY(${restaurants.cuisineType})`);
      }

      if (price_range) {
        conditions.push(sql`${restaurants.priceRange} = ${price_range}`);
      }

      if (min_score) {
        conditions.push(
          sql`${restaurants.overallScore}::numeric >= ${min_score}`
        );
      }

      // PostGIS mesafe filtresi (10km yaricap)
      if (lat != null && lng != null) {
        conditions.push(
          sql`ST_DWithin(
            ${restaurants.location}::geography,
            ST_SetSRID(ST_MakePoint(${lng}, ${lat}), 4326)::geography,
            10000
          )`
        );
      }

      // WHERE birlestir
      const whereClause = sql.join(conditions, sql` AND `);

      // Siralama
      let orderClause: ReturnType<typeof sql>;
      switch (sort_by) {
        case "distance":
          orderClause = sql`ST_Distance(
            ${restaurants.location}::geography,
            ST_SetSRID(ST_MakePoint(${lng}, ${lat}), 4326)::geography
          ) ASC`;
          break;
        case "newest":
          orderClause = sql`${restaurants.createdAt} DESC`;
          break;
        case "score":
        default:
          orderClause = sql`${restaurants.overallScore} DESC NULLS LAST`;
          break;
      }

      // Paralel: sonuclar + count
      const distanceSelect =
        lat != null && lng != null
          ? sql<string>`(ST_Distance(
              ${restaurants.location}::geography,
              ST_SetSRID(ST_MakePoint(${lng}, ${lat}), 4326)::geography
            ) / 1000.0)`.as("distance_km")
          : sql<null>`NULL`.as("distance_km");

      const [results, countResult] = await Promise.all([
        db
          .select({
            id: restaurants.id,
            name: restaurants.name,
            slug: restaurants.slug,
            address: restaurants.address,
            district: restaurants.district,
            neighborhood: restaurants.neighborhood,
            cuisineType: restaurants.cuisineType,
            priceRange: restaurants.priceRange,
            overallScore: restaurants.overallScore,
            totalReviews: restaurants.totalReviews,
            imageUrl: restaurants.imageUrl,
            distanceKm: distanceSelect,
          })
          .from(restaurants)
          .where(whereClause)
          .orderBy(orderClause)
          .limit(limit)
          .offset(offset),

        db
          .select({ count: sql<number>`count(*)::int` })
          .from(restaurants)
          .where(whereClause),
      ]);

      const total = countResult[0]?.count ?? 0;

      // Her restoran icin en iyi 3 yemek
      const restaurantIds = results.map((r) => r.id);

      let dishMap = new Map<
        number,
        { foodName: string; score: string; reviewCount: number }[]
      >();

      if (restaurantIds.length > 0) {
        const topDishesResult = await db
          .select({
            restaurantId: foodScores.restaurantId,
            foodName: foodScores.foodName,
            score: foodScores.score,
            reviewCount: foodScores.reviewCount,
          })
          .from(foodScores)
          .where(
            sql`${foodScores.restaurantId} IN (${sql.join(
              restaurantIds.map((id) => sql`${id}`),
              sql`, `
            )}) AND ${foodScores.score} IS NOT NULL`
          )
          .orderBy(desc(foodScores.score));

        for (const dish of topDishesResult) {
          const existing = dishMap.get(dish.restaurantId) ?? [];
          if (existing.length < 3) {
            existing.push({
              foodName: dish.foodName,
              score: dish.score,
              reviewCount: dish.reviewCount,
            });
            dishMap.set(dish.restaurantId, existing);
          }
        }
      }

      const totalPages = Math.ceil(total / limit);

      const response = {
        data: results.map((r) => ({
          id: r.id,
          name: r.name,
          slug: r.slug,
          address: r.address ?? null,
          district: r.district ?? null,
          neighborhood: r.neighborhood ?? null,
          cuisineType: r.cuisineType ?? null,
          priceRange: r.priceRange ?? null,
          overallScore: r.overallScore ?? null,
          totalReviews: r.totalReviews,
          imageUrl: r.imageUrl ?? null,
          distance: r.distanceKm != null ? Number(r.distanceKm) : null,
          topDishes: dishMap.get(r.id) ?? [],
        })),
        pagination: {
          page,
          limit,
          total,
          totalPages,
          hasNext: page < totalPages,
          hasPrev: page > 1,
        },
        meta: {
          query: q,
          appliedFilters: {
            district: district ?? null,
            cuisine: cuisine ?? null,
            priceRange: price_range ?? null,
            minScore: min_score ?? null,
          },
          sortBy: sort_by,
        },
      };

      await cacheSet(cacheKey, response, 300);
      reply.header("X-Cache", "MISS");
      return response;
    }
  );
}
