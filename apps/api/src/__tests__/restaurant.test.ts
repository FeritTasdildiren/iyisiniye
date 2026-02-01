/**
 * GET /api/v1/restaurants/:slug - Restoran Detay Endpoint Entegrasyon Testleri
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

describe("GET /api/v1/restaurants/:slug", () => {
  it("gecersiz slug formati (ABC!@#) ile 400 doner", async () => {
    const res = await app.inject({
      method: "GET",
      url: "/api/v1/restaurants/ABC!@%23",
    });

    expect(res.statusCode).toBe(400);
  });

  it("buyuk harfli slug ile 400 doner", async () => {
    const res = await app.inject({
      method: "GET",
      url: "/api/v1/restaurants/INVALID-SLUG",
    });

    expect(res.statusCode).toBe(400);
  });

  it("mevcut olmayan slug ile 404 doner", async () => {
    // Restoran bulunamadi - bos array
    setQueryResults([
      [], // restoran sorgusu - bos donuyor
    ]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/restaurants/olmayan-restoran",
    });

    expect(res.statusCode).toBe(404);
    const body = res.json();
    expect(body.error).toBe("Not Found");
    expect(body.message).toContain("olmayan-restoran");
  });

  it("mevcut restoran icin 200 ve dogru response yapisi doner", async () => {
    const mockRestaurant = {
      id: 1,
      name: "Kebapci Mehmet",
      slug: "kebapci-mehmet",
      address: "Kadikoy Moda Cad. No:5",
      district: "Kadikoy",
      neighborhood: "Moda",
      location: { lat: 40.9865, lng: 29.0237 },
      phone: "05551234567",
      website: "https://kebapci.com",
      cuisineType: ["kebap", "turk"],
      priceRange: 2,
      overallScore: "8.50",
      totalReviews: 150,
      isActive: true,
      imageUrl: "https://img.example.com/kebapci.jpg",
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    setQueryResults([
      // 1. Restoran temel bilgileri
      [mockRestaurant],
      // 2. Platform bilgileri
      [
        {
          platform: "google",
          externalUrl: "https://maps.google.com/place/123",
          platformScore: "4.50",
          platformReviews: 80,
        },
      ],
      // 3. Yemek puanlari (food_scores)
      [
        {
          foodName: "Adana Kebap",
          score: "9.10",
          reviewCount: 45,
          confidence: "0.92",
          sentimentDistribution: { positive: 40, negative: 3, neutral: 2 },
        },
      ],
      // 4. Son 10 yorum
      [
        {
          id: 101,
          authorName: "Ali K.",
          rating: 5,
          text: "Muhtesem kebap!",
          reviewDate: new Date("2025-01-15"),
          platform: "google",
        },
      ],
      // 5. Sentiment aggregate
      [
        {
          totalAnalyzed: 100,
          positiveCount: 75,
          negativeCount: 10,
          neutralCount: 15,
        },
      ],
      // 6. Dish mentions (for review IDs)
      [
        {
          reviewId: 101,
          foodName: "Adana Kebap",
          sentiment: "positive",
        },
      ],
    ]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/restaurants/kebapci-mehmet",
    });

    expect(res.statusCode).toBe(200);

    const body = res.json();

    // Temel yapisal kontroller
    expect(body).toHaveProperty("restaurant");
    expect(body).toHaveProperty("foodScores");
    expect(body).toHaveProperty("recentReviews");
    expect(body).toHaveProperty("sentimentSummary");

    // Restaurant objesi kontrol
    expect(body.restaurant).toHaveProperty("id");
    expect(body.restaurant).toHaveProperty("name");
    expect(body.restaurant).toHaveProperty("slug");
    expect(body.restaurant).toHaveProperty("platforms");
    expect(body.restaurant.slug).toBe("kebapci-mehmet");

    // Sentiment summary kontrol
    expect(body.sentimentSummary).toHaveProperty("totalAnalyzed");
    expect(body.sentimentSummary).toHaveProperty("overallSentiment");
    expect(body.sentimentSummary).toHaveProperty("distribution");
  });

  it("restaurant response'unda foodScores array donmeli", async () => {
    setQueryResults([
      // Restoran
      [{
        id: 2, name: "Balikci", slug: "balikci",
        address: null, district: null, neighborhood: null,
        location: null, phone: null, website: null,
        cuisineType: ["balik"], priceRange: 3,
        overallScore: "7.00", totalReviews: 30,
        isActive: true, imageUrl: null,
        createdAt: new Date(), updatedAt: new Date(),
      }],
      // Platforms
      [],
      // Food scores
      [
        { foodName: "Levrek", score: "8.50", reviewCount: 15, confidence: "0.85", sentimentDistribution: null },
        { foodName: "Hamsi", score: "7.20", reviewCount: 10, confidence: "0.80", sentimentDistribution: null },
      ],
      // Reviews
      [],
      // Sentiment aggregate
      [{ totalAnalyzed: 0, positiveCount: 0, negativeCount: 0, neutralCount: 0 }],
    ]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/restaurants/balikci",
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(Array.isArray(body.foodScores)).toBe(true);
    expect(body.foodScores.length).toBe(2);
    expect(body.foodScores[0]).toHaveProperty("foodName");
    expect(body.foodScores[0]).toHaveProperty("score");
    expect(body.foodScores[0]).toHaveProperty("reviewCount");
  });

  it("bos slug ile 400 doner", async () => {
    const res = await app.inject({
      method: "GET",
      url: "/api/v1/restaurants/",
    });

    // Fastify /api/v1/restaurants/ route'u tanimli degil - 404
    expect([400, 404]).toContain(res.statusCode);
  });
});
