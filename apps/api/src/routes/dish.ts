/**
 * GET /api/v1/dishes/:slug - Yemek Detay
 *
 * Slug ile yemek bulunur, ardindan Promise.all ile 2 paralel sorgu:
 *   1. food_scores JOIN restaurants -> Bu yemegi sunan restoranlar (score DESC)
 *   2. food_mentions -> Sentiment aggregate (positive/negative/neutral count)
 *
 * Eslestirme: lower(unaccent(food_scores.food_name)) = lower(unaccent(dishes.canonical_name))
 */

import type { FastifyInstance } from "fastify";
import type { ZodTypeProvider } from "fastify-type-provider-zod";
import {
  db,
  dishes,
  foodScores,
  foodMentions,
  restaurants,
} from "@iyisiniye/db";
import { sql, eq, desc } from "drizzle-orm";
import { z } from "zod/v4";

// --- Zod Schema ---

const DishDetailParamsSchema = z.object({
  slug: z
    .string()
    .min(1)
    .max(255)
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Gecersiz slug formati."),
});

// --- Route ---

export async function dishRoutes(app: FastifyInstance) {
  const server = app.withTypeProvider<ZodTypeProvider>();

  server.get(
    "/api/v1/dishes/:slug",
    {
      schema: {
        params: DishDetailParamsSchema,
      },
    },
    async (request, reply) => {
      const { slug } = request.params;

      // 1. Yemek temel bilgileri
      const dishResult = await db
        .select()
        .from(dishes)
        .where(eq(dishes.slug, slug))
        .limit(1);

      if (dishResult.length === 0) {
        return reply.status(404).send({
          statusCode: 404,
          error: "Not Found",
          message: `Yemek bulunamadi: ${slug}`,
        });
      }

      const dish = dishResult[0];
      const canonicalName = dish.canonicalName ?? dish.name;

      // 2-3 paralel sorgular
      const [restaurantScores, sentimentAgg] = await Promise.all([
        // 2. Bu yemegi sunan restoranlar (food_scores JOIN restaurants, score DESC)
        db
          .select({
            name: restaurants.name,
            slug: restaurants.slug,
            district: restaurants.district,
            score: foodScores.score,
            reviewCount: foodScores.reviewCount,
          })
          .from(foodScores)
          .innerJoin(
            restaurants,
            eq(foodScores.restaurantId, restaurants.id)
          )
          .where(
            sql`lower(unaccent(${foodScores.foodName})) = lower(unaccent(${canonicalName}))
            AND ${restaurants.isActive} = true`
          )
          .orderBy(desc(foodScores.score)),

        // 3. Sentiment ozeti (food_mentions uzerinden)
        db
          .select({
            positiveCount: sql<number>`count(*) FILTER (WHERE ${foodMentions.sentiment} = 'positive')::int`,
            negativeCount: sql<number>`count(*) FILTER (WHERE ${foodMentions.sentiment} = 'negative')::int`,
            neutralCount: sql<number>`count(*) FILTER (WHERE ${foodMentions.sentiment} = 'neutral')::int`,
            total: sql<number>`count(*)::int`,
          })
          .from(foodMentions)
          .where(
            sql`lower(unaccent(${foodMentions.canonicalName})) = lower(unaccent(${canonicalName}))`
          ),
      ]);

      // Istatistikler hesapla
      const scores = restaurantScores.map((r) => Number(r.score));
      const totalReviews = restaurantScores.reduce(
        (sum, r) => sum + r.reviewCount,
        0
      );

      const stats = {
        avgScore:
          scores.length > 0
            ? Math.round((scores.reduce((a, b) => a + b, 0) / scores.length) * 100) / 100
            : null,
        maxScore: scores.length > 0 ? Math.max(...scores) : null,
        minScore: scores.length > 0 ? Math.min(...scores) : null,
        totalReviews,
      };

      // Sentiment ozeti
      const sentiment = sentimentAgg[0];

      return {
        dish: {
          name: dish.name,
          slug: dish.slug,
          canonicalName: dish.canonicalName ?? null,
          category: dish.category ?? null,
        },
        restaurants: restaurantScores.map((r) => ({
          name: r.name,
          slug: r.slug,
          district: r.district ?? null,
          score: Number(r.score),
          reviewCount: r.reviewCount,
        })),
        stats,
        sentimentSummary: {
          positive: sentiment?.positiveCount ?? 0,
          negative: sentiment?.negativeCount ?? 0,
          neutral: sentiment?.neutralCount ?? 0,
          total: sentiment?.total ?? 0,
        },
      };
    }
  );
}
