/**
 * GET /api/v1/restaurants/:slug - Restoran Detay
 *
 * Promise.all ile 4 paralel sorgu: restoran, platforms, food_scores, son 10 yorum.
 * Sentiment aggregate: positive/negative/neutral yuzdeleri.
 * reviews -> restaurant_platforms -> restaurants JOIN zinciri.
 */

import type { FastifyInstance } from "fastify";
import type { ZodTypeProvider } from "fastify-type-provider-zod";
import {
  db,
  restaurants,
  restaurantPlatforms,
  foodScores,
  reviews,
  foodMentions,
} from "@iyisiniye/db";
import { sql, eq, and, desc } from "drizzle-orm";
import { z } from "zod/v4";
import { cacheGet, cacheSet } from "../lib/cache.js";

// --- Zod Schema ---

const RestaurantDetailParamsSchema = z.object({
  slug: z
    .string()
    .min(1)
    .max(255)
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Gecersiz slug formati."),
});

// --- Route ---

export async function restaurantRoutes(app: FastifyInstance) {
  const server = app.withTypeProvider<ZodTypeProvider>();

  server.get(
    "/api/v1/restaurants/:slug",
    {
      schema: {
        params: RestaurantDetailParamsSchema,
      },
    },
    async (request, reply) => {
      const { slug } = request.params;

      // Cache kontrolu
      const cacheKey = `restaurant:${slug}`;
      const cached = await cacheGet(cacheKey);
      if (cached) {
        reply.header("X-Cache", "HIT");
        return cached;
      }

      // 1. Restoran temel bilgileri
      const restaurantResult = await db
        .select()
        .from(restaurants)
        .where(and(eq(restaurants.slug, slug), eq(restaurants.isActive, true)))
        .limit(1);

      if (restaurantResult.length === 0) {
        return reply.status(404).send({
          statusCode: 404,
          error: "Not Found",
          message: `Restoran bulunamadi: ${slug}`,
        });
      }

      const rest = restaurantResult[0];

      // 2-5 paralel sorgular
      const [platforms, scores, recentReviewsRaw, sentimentAgg] =
        await Promise.all([
          // 2. Platform bilgileri
          db
            .select({
              platform: restaurantPlatforms.platform,
              externalUrl: restaurantPlatforms.externalUrl,
              platformScore: restaurantPlatforms.platformScore,
              platformReviews: restaurantPlatforms.platformReviews,
            })
            .from(restaurantPlatforms)
            .where(eq(restaurantPlatforms.restaurantId, rest.id)),

          // 3. Yemek puanlari (score DESC)
          db
            .select({
              foodName: foodScores.foodName,
              score: foodScores.score,
              reviewCount: foodScores.reviewCount,
              confidence: foodScores.confidence,
              sentimentDistribution: foodScores.sentimentDistribution,
            })
            .from(foodScores)
            .where(eq(foodScores.restaurantId, rest.id))
            .orderBy(desc(foodScores.score)),

          // 4. Son 10 yorum (reviews -> restaurant_platforms JOIN)
          db
            .select({
              id: reviews.id,
              authorName: reviews.authorName,
              rating: reviews.rating,
              text: reviews.text,
              reviewDate: reviews.reviewDate,
              platform: restaurantPlatforms.platform,
            })
            .from(reviews)
            .innerJoin(
              restaurantPlatforms,
              eq(reviews.restaurantPlatformId, restaurantPlatforms.id)
            )
            .where(eq(restaurantPlatforms.restaurantId, rest.id))
            .orderBy(desc(reviews.reviewDate))
            .limit(10),

          // 5. Sentiment ozeti (food_mentions -> reviews -> restaurant_platforms)
          db
            .select({
              totalAnalyzed: sql<number>`count(*)::int`,
              positiveCount: sql<number>`count(*) FILTER (WHERE ${foodMentions.sentiment} = 'positive')::int`,
              negativeCount: sql<number>`count(*) FILTER (WHERE ${foodMentions.sentiment} = 'negative')::int`,
              neutralCount: sql<number>`count(*) FILTER (WHERE ${foodMentions.sentiment} = 'neutral')::int`,
            })
            .from(foodMentions)
            .innerJoin(reviews, eq(foodMentions.reviewId, reviews.id))
            .innerJoin(
              restaurantPlatforms,
              eq(reviews.restaurantPlatformId, restaurantPlatforms.id)
            )
            .where(eq(restaurantPlatforms.restaurantId, rest.id)),
        ]);

      // 6. Her yorum icin bahsedilen yemekler (batch)
      const reviewIds = recentReviewsRaw.map((r) => r.id);

      const dishMentionsResult =
        reviewIds.length > 0
          ? await db
              .select({
                reviewId: foodMentions.reviewId,
                foodName: foodMentions.canonicalName,
                sentiment: foodMentions.sentiment,
              })
              .from(foodMentions)
              .where(
                sql`${foodMentions.reviewId} IN (${sql.join(
                  reviewIds.map((id) => sql`${id}`),
                  sql`, `
                )})`
              )
          : [];

      // Mention'lari review'a gore grupla
      const mentionsByReview = new Map<
        number,
        { dishName: string; sentiment: string | null }[]
      >();
      for (const m of dishMentionsResult) {
        const arr = mentionsByReview.get(m.reviewId) ?? [];
        arr.push({
          dishName: m.foodName ?? "Bilinmeyen",
          sentiment: m.sentiment,
        });
        mentionsByReview.set(m.reviewId, arr);
      }

      // Sentiment ozeti hesapla
      const sentimentData = sentimentAgg[0];
      const total = sentimentData?.totalAnalyzed ?? 0;
      const positivePerc =
        total > 0
          ? Math.round((sentimentData.positiveCount / total) * 100)
          : 0;
      const negativePerc =
        total > 0
          ? Math.round((sentimentData.negativeCount / total) * 100)
          : 0;
      const neutralPerc =
        total > 0 ? 100 - positivePerc - negativePerc : 0;

      let overallSentiment: "positive" | "negative" | "neutral" | "mixed";
      if (positivePerc >= 60) overallSentiment = "positive";
      else if (negativePerc >= 40) overallSentiment = "negative";
      else if (total === 0) overallSentiment = "neutral";
      else overallSentiment = "mixed";

      // Location parse
      const location = rest.location
        ? { lat: rest.location.lat, lng: rest.location.lng }
        : null;

      const response = {
        restaurant: {
          id: rest.id,
          name: rest.name,
          slug: rest.slug,
          address: rest.address ?? null,
          district: rest.district ?? null,
          neighborhood: rest.neighborhood ?? null,
          location,
          phone: rest.phone ?? null,
          website: rest.website ?? null,
          cuisineType: rest.cuisineType ?? null,
          priceRange: rest.priceRange ?? null,
          overallScore: rest.overallScore ?? null,
          totalReviews: rest.totalReviews,
          imageUrl: rest.imageUrl ?? null,
          platforms: platforms.map((p) => ({
            platform: p.platform,
            externalUrl: p.externalUrl ?? null,
            platformScore: p.platformScore ?? null,
            platformReviews: p.platformReviews,
          })),
        },
        foodScores: scores.map((s) => ({
          foodName: s.foodName,
          score: s.score,
          reviewCount: s.reviewCount,
          confidence: s.confidence ?? null,
          sentimentDistribution:
            (s.sentimentDistribution as {
              positive: number;
              negative: number;
              neutral: number;
            } | null) ?? null,
        })),
        recentReviews: recentReviewsRaw.map((r) => ({
          id: r.id,
          authorName: r.authorName ?? null,
          rating: r.rating ?? null,
          text: r.text,
          reviewDate: r.reviewDate?.toISOString() ?? null,
          platform: r.platform,
          mentionedDishes: mentionsByReview.get(r.id) ?? [],
        })),
        sentimentSummary: {
          totalAnalyzed: total,
          overallSentiment,
          distribution: {
            positive: positivePerc,
            negative: negativePerc,
            neutral: neutralPerc,
          },
        },
      };

      await cacheSet(cacheKey, response, 900);
      reply.header("X-Cache", "MISS");
      return response;
    }
  );
}
