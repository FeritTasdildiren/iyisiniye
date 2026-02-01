/**
 * GET /api/v1/search - Arama Endpoint Entegrasyon Testleri
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

describe("GET /api/v1/search", () => {
  it("q=kebap ile arama yapildiginda 200 ve data array doner", async () => {
    // Mock: search results + count + top dishes
    setQueryResults([
      // 1. Restoran sonuclari (db.select().from(restaurants)...)
      [
        {
          id: 1,
          name: "Kebapci Mehmet",
          slug: "kebapci-mehmet",
          address: "Istanbul",
          district: "Kadikoy",
          neighborhood: "Moda",
          cuisineType: ["kebap"],
          priceRange: 2,
          overallScore: "8.50",
          totalReviews: 120,
          imageUrl: null,
          distanceKm: null,
        },
      ],
      // 2. Count sorgusu
      [{ count: 1 }],
      // 3. Top dishes (food_scores)
      [
        {
          restaurantId: 1,
          foodName: "Adana Kebap",
          score: "9.20",
          reviewCount: 45,
        },
      ],
    ]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/search?q=kebap",
    });

    expect(res.statusCode).toBe(200);

    const body = res.json();
    expect(body).toHaveProperty("data");
    expect(body).toHaveProperty("pagination");
    expect(body).toHaveProperty("meta");
    expect(Array.isArray(body.data)).toBe(true);
    expect(body.meta.query).toBe("kebap");
  });

  it("bos query ile istek atildiginda validation error doner", async () => {
    const res = await app.inject({
      method: "GET",
      url: "/api/v1/search",
    });

    // q parametresi zorunlu, olmadığında Zod validation error
    expect(res.statusCode).toBe(400);
  });

  it("q tek karakter oldugunda validation error doner (min 2)", async () => {
    const res = await app.inject({
      method: "GET",
      url: "/api/v1/search?q=a",
    });

    expect(res.statusCode).toBe(400);
  });

  it("filtre kombinasyonu (cuisine=kebap&price_range=2) ile 200 doner", async () => {
    setQueryResults([
      // Restoran sonuclari
      [
        {
          id: 2,
          name: "Kebap Ustasi",
          slug: "kebap-ustasi",
          address: "Ankara",
          district: "Cankaya",
          neighborhood: null,
          cuisineType: ["kebap"],
          priceRange: 2,
          overallScore: "7.80",
          totalReviews: 50,
          imageUrl: null,
          distanceKm: null,
        },
      ],
      // Count
      [{ count: 1 }],
      // Top dishes
      [],
    ]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/search?q=kebap&cuisine=kebap&price_range=2",
    });

    expect(res.statusCode).toBe(200);

    const body = res.json();
    expect(body.meta.appliedFilters.cuisine).toBe("kebap");
    expect(body.meta.appliedFilters.priceRange).toBe(2);
  });

  it("gecersiz page=-1 ile validation error doner", async () => {
    const res = await app.inject({
      method: "GET",
      url: "/api/v1/search?q=kebap&page=-1",
    });

    expect(res.statusCode).toBe(400);
  });

  it("gecersiz page=0 ile validation error doner", async () => {
    const res = await app.inject({
      method: "GET",
      url: "/api/v1/search?q=kebap&page=0",
    });

    expect(res.statusCode).toBe(400);
  });

  it("sayfalama parametreleri: page=1&limit=2 ile pagination objesi doner", async () => {
    setQueryResults([
      // 2 restoran
      [
        {
          id: 1, name: "A", slug: "a", address: null, district: null,
          neighborhood: null, cuisineType: null, priceRange: null,
          overallScore: null, totalReviews: 0, imageUrl: null, distanceKm: null,
        },
        {
          id: 2, name: "B", slug: "b", address: null, district: null,
          neighborhood: null, cuisineType: null, priceRange: null,
          overallScore: null, totalReviews: 0, imageUrl: null, distanceKm: null,
        },
      ],
      // Toplam 5 sonuc
      [{ count: 5 }],
      // Top dishes (id'ler 1 ve 2 icin)
      [],
    ]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/search?q=restoran&page=1&limit=2",
    });

    expect(res.statusCode).toBe(200);

    const body = res.json();
    expect(body.pagination).toBeDefined();
    expect(body.pagination.page).toBe(1);
    expect(body.pagination.limit).toBe(2);
    expect(body.pagination.total).toBe(5);
    expect(body.pagination.totalPages).toBe(3);
    expect(body.pagination.hasNext).toBe(true);
    expect(body.pagination.hasPrev).toBe(false);
  });

  it("sort_by=distance ama lat/lng yoksa 400 doner", async () => {
    // Bu test icin DB sorgulari calistirilmadan once 400 donmeli
    setQueryResults([[], [{ count: 0 }]]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/search?q=kebap&sort_by=distance",
    });

    expect(res.statusCode).toBe(400);
    const body = res.json();
    expect(body.message).toContain("lat");
  });

  it("response yapisinda data, pagination ve meta key'leri bulunur", async () => {
    setQueryResults([
      [],
      [{ count: 0 }],
    ]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/search?q=olmayan-yemek",
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body).toHaveProperty("data");
    expect(body).toHaveProperty("pagination");
    expect(body).toHaveProperty("meta");
    expect(body.meta).toHaveProperty("query");
    expect(body.meta).toHaveProperty("appliedFilters");
    expect(body.meta).toHaveProperty("sortBy");
  });
});
