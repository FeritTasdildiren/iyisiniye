/**
 * GET /api/v1/dishes/:slug - Yemek Detay Endpoint Entegrasyon Testleri
 */

import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import type { FastifyInstance } from "fastify";
import { buildApp } from "../index.js";
import { setQueryResults, clearRedisStore, resetQueryMocks } from "./setup.js";

let app: FastifyInstance;

beforeAll(async () => {
  app = await buildApp();
  await app.ready();
});

afterAll(async () => {
  await app.close();
});

beforeEach(() => {
  clearRedisStore();
  resetQueryMocks();
});

describe("GET /api/v1/dishes/:slug", () => {
  it("gecersiz slug formati ile 400 doner", async () => {
    const res = await app.inject({
      method: "GET",
      url: "/api/v1/dishes/INVALID!slug",
    });

    expect(res.statusCode).toBe(400);
  });

  it("buyuk harfli slug ile 400 doner", async () => {
    const res = await app.inject({
      method: "GET",
      url: "/api/v1/dishes/Adana-Kebap",
    });

    expect(res.statusCode).toBe(400);
  });

  it("mevcut olmayan slug ile 404 doner", async () => {
    // Yemek bulunamadi
    setQueryResults([
      [], // dishes sorgusu - bos
    ]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/dishes/olmayan-yemek",
    });

    expect(res.statusCode).toBe(404);
    const body = res.json();
    expect(body.error).toBe("Not Found");
    expect(body.message).toContain("olmayan-yemek");
  });

  it("mevcut yemek icin 200 ve dogru response yapisi doner", async () => {
    setQueryResults([
      // 1. Yemek temel bilgileri (dishes)
      [
        {
          id: 1,
          name: "Adana Kebap",
          slug: "adana-kebap",
          canonicalName: "Adana Kebap",
          category: "kebap",
          subcategory: null,
          isMainDish: true,
          aliases: null,
          searchVector: null,
          createdAt: new Date(),
        },
      ],
      // 2. Restoran skorlari (food_scores JOIN restaurants)
      [
        { name: "Kebapci Mehmet", slug: "kebapci-mehmet", district: "Kadikoy", score: "9.10", reviewCount: 45 },
        { name: "Ocakbasi Ali", slug: "ocakbasi-ali", district: "Besiktas", score: "8.70", reviewCount: 30 },
      ],
      // 3. Sentiment aggregate (food_mentions)
      [
        { positiveCount: 60, negativeCount: 5, neutralCount: 10, total: 75 },
      ],
    ]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/dishes/adana-kebap",
    });

    expect(res.statusCode).toBe(200);

    const body = res.json();

    // Yapisal kontroller
    expect(body).toHaveProperty("dish");
    expect(body).toHaveProperty("restaurants");
    expect(body).toHaveProperty("stats");
    expect(body).toHaveProperty("sentimentSummary");
  });

  it("dish objesi dogru alanlari icerir", async () => {
    setQueryResults([
      [
        {
          id: 2,
          name: "Iskender",
          slug: "iskender",
          canonicalName: "Iskender Kebap",
          category: "kebap",
          subcategory: null,
          isMainDish: true,
          aliases: null,
          searchVector: null,
          createdAt: new Date(),
        },
      ],
      // Restoranlar
      [{ name: "Kebapci", slug: "kebapci", district: null, score: "8.00", reviewCount: 20 }],
      // Sentiment
      [{ positiveCount: 15, negativeCount: 2, neutralCount: 3, total: 20 }],
    ]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/dishes/iskender",
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();

    expect(body.dish).toHaveProperty("name");
    expect(body.dish).toHaveProperty("slug");
    expect(body.dish).toHaveProperty("canonicalName");
    expect(body.dish).toHaveProperty("category");
    expect(body.dish.slug).toBe("iskender");
  });

  it("restaurants array'indeki her eleman dogru alanlara sahip olur", async () => {
    setQueryResults([
      [{
        id: 3, name: "Lahmacun", slug: "lahmacun",
        canonicalName: "Lahmacun", category: "pide_lahmacun",
        subcategory: null, isMainDish: true, aliases: null,
        searchVector: null, createdAt: new Date(),
      }],
      [
        { name: "Pideci Ahmet", slug: "pideci-ahmet", district: "Uskudar", score: "7.50", reviewCount: 25 },
      ],
      [{ positiveCount: 20, negativeCount: 3, neutralCount: 2, total: 25 }],
    ]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/dishes/lahmacun",
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();

    expect(Array.isArray(body.restaurants)).toBe(true);
    if (body.restaurants.length > 0) {
      const r = body.restaurants[0];
      expect(r).toHaveProperty("name");
      expect(r).toHaveProperty("slug");
      expect(r).toHaveProperty("district");
      expect(r).toHaveProperty("score");
      expect(r).toHaveProperty("reviewCount");
    }
  });

  it("stats objesi avgScore, maxScore, minScore ve totalReviews icerir", async () => {
    setQueryResults([
      [{
        id: 4, name: "Pide", slug: "pide",
        canonicalName: "Pide", category: "pide_lahmacun",
        subcategory: null, isMainDish: true, aliases: null,
        searchVector: null, createdAt: new Date(),
      }],
      [
        { name: "Pideci 1", slug: "pideci-1", district: "A", score: "9.00", reviewCount: 10 },
        { name: "Pideci 2", slug: "pideci-2", district: "B", score: "7.00", reviewCount: 5 },
      ],
      [{ positiveCount: 10, negativeCount: 2, neutralCount: 3, total: 15 }],
    ]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/dishes/pide",
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();

    expect(body.stats).toHaveProperty("avgScore");
    expect(body.stats).toHaveProperty("maxScore");
    expect(body.stats).toHaveProperty("minScore");
    expect(body.stats).toHaveProperty("totalReviews");
    expect(body.stats.totalReviews).toBe(15);
  });

  it("sentimentSummary objesi positive, negative, neutral ve total icerir", async () => {
    setQueryResults([
      [{
        id: 5, name: "Doner", slug: "doner",
        canonicalName: "Doner", category: "doner",
        subcategory: null, isMainDish: true, aliases: null,
        searchVector: null, createdAt: new Date(),
      }],
      [],
      [{ positiveCount: 30, negativeCount: 5, neutralCount: 10, total: 45 }],
    ]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/dishes/doner",
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();

    expect(body.sentimentSummary).toHaveProperty("positive");
    expect(body.sentimentSummary).toHaveProperty("negative");
    expect(body.sentimentSummary).toHaveProperty("neutral");
    expect(body.sentimentSummary).toHaveProperty("total");
    expect(body.sentimentSummary.total).toBe(45);
  });
});
