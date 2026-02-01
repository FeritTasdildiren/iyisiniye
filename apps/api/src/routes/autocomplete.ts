/**
 * GET /api/v1/autocomplete - Anlik Oneri
 *
 * Paralel: 5 restoran (pg_trgm name) + 5 yemek (pg_trgm canonical_name).
 * Ek rate limit: 30/dk per IP.
 */

import type { FastifyInstance } from "fastify";
import type { ZodTypeProvider } from "fastify-type-provider-zod";
import { db, restaurants, dishes, foodScores } from "@iyisiniye/db";
import { sql, desc } from "drizzle-orm";
import { z } from "zod/v4";
import { cacheGet, cacheSet } from "../lib/cache.js";

// --- Zod Schema ---

const AutocompleteQuerySchema = z.object({
  q: z.string().min(2, "Oneri icin en az 2 karakter gereklidir.").max(50),
});

// --- Route ---

export async function autocompleteRoutes(app: FastifyInstance) {
  const server = app.withTypeProvider<ZodTypeProvider>();

  server.get(
    "/api/v1/autocomplete",
    {
      schema: {
        querystring: AutocompleteQuerySchema,
      },
      config: {
        rateLimit: {
          max: 30,
          timeWindow: "1 minute",
        },
      },
    },
    async (request, reply) => {
      const q = request.query.q.trim();

      // Cache kontrolu
      const cacheKey = `autocomplete:${q.toLowerCase().trim()}`;
      const cached = await cacheGet(cacheKey);
      if (cached) {
        reply.header("X-Cache", "HIT");
        return cached;
      }

      // Restoran ve yemek sorgularini paralel calistir
      const [restaurantResults, dishResults] = await Promise.all([
        // 1. Restoran onerileri (trigram similarity + FTS, max 5)
        db
          .select({
            id: restaurants.id,
            name: restaurants.name,
            slug: restaurants.slug,
            district: restaurants.district,
            cuisineType: restaurants.cuisineType,
            overallScore: restaurants.overallScore,
            similarity:
              sql<number>`similarity(${restaurants.name}, ${q})`.as(
                "similarity"
              ),
          })
          .from(restaurants)
          .where(
            sql`(
              similarity(${restaurants.name}, ${q}) > 0.2
              OR to_tsvector('turkish', ${restaurants.name})
                 @@ plainto_tsquery('turkish', unaccent(${q}))
            )
            AND ${restaurants.isActive} = true`
          )
          .orderBy(
            sql`similarity(${restaurants.name}, ${q}) DESC`,
            desc(restaurants.overallScore)
          )
          .limit(5),

        // 2. Yemek onerileri (trigram similarity + FTS, max 5)
        db
          .select({
            id: dishes.id,
            name: dishes.name,
            slug: dishes.slug,
            category: dishes.category,
            similarity:
              sql<number>`similarity(coalesce(${dishes.canonicalName}, ${dishes.name}), ${q})`.as(
                "similarity"
              ),
            restaurantCount: sql<number>`(
              SELECT count(DISTINCT ${foodScores.restaurantId})::int
              FROM food_scores
              WHERE lower(unaccent(food_scores.food_name)) = lower(unaccent(coalesce(${dishes.canonicalName}, ${dishes.name})))
            )`.as("restaurant_count"),
          })
          .from(dishes)
          .where(
            sql`(
              similarity(coalesce(${dishes.canonicalName}, ${dishes.name}), ${q}) > 0.2
              OR ${dishes.searchVector} @@ plainto_tsquery('turkish', unaccent(${q}))
            )`
          )
          .orderBy(
            sql`similarity(coalesce(${dishes.canonicalName}, ${dishes.name}), ${q}) DESC`
          )
          .limit(5),
      ]);

      const response = {
        restaurants: restaurantResults.map(
          ({ similarity: _sim, ...rest }) => ({
            id: rest.id,
            name: rest.name,
            slug: rest.slug,
            district: rest.district ?? null,
            cuisineType: rest.cuisineType ?? null,
            overallScore: rest.overallScore ?? null,
          })
        ),
        dishes: dishResults.map(({ similarity: _sim, ...rest }) => ({
          id: rest.id,
          name: rest.name,
          slug: rest.slug,
          category: rest.category ?? null,
          restaurantCount: rest.restaurantCount ?? 0,
        })),
      };

      await cacheSet(cacheKey, response, 3600);
      reply.header("X-Cache", "MISS");
      return response;
    }
  );
}
