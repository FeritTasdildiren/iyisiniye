/**
 * Cache Mekanizmasi Testleri
 *
 * 1. cacheGet / cacheSet unit testleri (Redis mock uzerinden)
 * 2. HTTP seviyesinde X-Cache header MISS/HIT kontrolu
 */

import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import type { FastifyInstance } from "fastify";
import { buildApp } from "../index.js";
import {
  setQueryResults,
  clearRedisStore,
  resetQueryMocks,
  redisStore,
} from "./setup.js";
import { cacheGet, cacheSet } from "../lib/cache.js";

// ---- Unit testler: cacheGet / cacheSet ----

describe("cacheGet / cacheSet unit testleri", () => {
  beforeEach(() => {
    clearRedisStore();
  });

  it("cacheSet ile veri yazilir, cacheGet ile okunur", async () => {
    await cacheSet("test-key", { hello: "world" }, 60);

    const result = await cacheGet<{ hello: string }>("test-key");
    expect(result).toEqual({ hello: "world" });
  });

  it("mevcut olmayan key icin cacheGet null doner", async () => {
    const result = await cacheGet("olmayan-key");
    expect(result).toBeNull();
  });

  it("cacheSet ile yazilan veri JSON olarak saklanir", async () => {
    const data = { items: [1, 2, 3], count: 3 };
    await cacheSet("json-test", data, 120);

    const entry = redisStore.get("json-test");
    expect(entry).toBeDefined();
    expect(entry!.value).toBe(JSON.stringify(data));
  });

  it("cacheSet TTL parametresi dogru sekilde uygulanir", async () => {
    await cacheSet("ttl-test", "data", 300);

    const entry = redisStore.get("ttl-test");
    expect(entry).toBeDefined();
    expect(entry!.expiry).not.toBeNull();
    // TTL yaklasik 300 saniye ileride olmali
    const expectedExpiry = Date.now() + 300 * 1000;
    expect(Math.abs(entry!.expiry! - expectedExpiry)).toBeLessThan(2000);
  });

  it("bos obje cacheSet ile yazilip okunabilir", async () => {
    await cacheSet("empty-obj", {}, 60);
    const result = await cacheGet("empty-obj");
    expect(result).toEqual({});
  });

  it("array veri cacheSet ile yazilip okunabilir", async () => {
    const data = [1, "iki", { uc: 3 }];
    await cacheSet("array-test", data, 60);
    const result = await cacheGet("array-test");
    expect(result).toEqual(data);
  });
});

// ---- Entegrasyon testleri: X-Cache header ----

describe("X-Cache header entegrasyon testleri", () => {
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

  it("ilk istek X-Cache: MISS header'i doner", async () => {
    setQueryResults([
      // search results
      [],
      // count
      [{ count: 0 }],
    ]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/search?q=test-miss",
    });

    expect(res.statusCode).toBe(200);
    expect(res.headers["x-cache"]).toBe("MISS");
  });

  it("ikinci istek ayni parametrelerle X-Cache: HIT doner", async () => {
    setQueryResults([
      [],
      [{ count: 0 }],
    ]);

    // Ilk istek - MISS
    const firstRes = await app.inject({
      method: "GET",
      url: "/api/v1/search?q=cache-test",
    });
    expect(firstRes.statusCode).toBe(200);
    expect(firstRes.headers["x-cache"]).toBe("MISS");

    // Ikinci istek - HIT (ayni query)
    const secondRes = await app.inject({
      method: "GET",
      url: "/api/v1/search?q=cache-test",
    });
    expect(secondRes.statusCode).toBe(200);
    expect(secondRes.headers["x-cache"]).toBe("HIT");
  });

  it("farkli parametrelerle yapilan istek MISS doner", async () => {
    setQueryResults([
      [],
      [{ count: 0 }],
    ]);

    // Ilk istek
    await app.inject({
      method: "GET",
      url: "/api/v1/search?q=query-a",
    });

    // Farkli sorgu ile
    setQueryResults([
      [],
      [{ count: 0 }],
    ]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/search?q=query-b",
    });

    expect(res.headers["x-cache"]).toBe("MISS");
  });

  it("autocomplete endpoint'i de cache mekanizmasini kullanir", async () => {
    setQueryResults([
      [], // restaurants
      [], // dishes
    ]);

    // Ilk istek - MISS
    const firstRes = await app.inject({
      method: "GET",
      url: "/api/v1/autocomplete?q=ke",
    });
    expect(firstRes.headers["x-cache"]).toBe("MISS");

    // Ikinci istek - HIT
    const secondRes = await app.inject({
      method: "GET",
      url: "/api/v1/autocomplete?q=ke",
    });
    expect(secondRes.headers["x-cache"]).toBe("HIT");
  });

  it("restaurant detail endpoint'i de cache mekanizmasini kullanir", async () => {
    const mockRest = {
      id: 1, name: "Test", slug: "test-restaurant",
      address: null, district: null, neighborhood: null,
      location: null, phone: null, website: null,
      cuisineType: null, priceRange: null,
      overallScore: null, totalReviews: 0,
      isActive: true, imageUrl: null,
      createdAt: new Date(), updatedAt: new Date(),
    };

    setQueryResults([
      [mockRest],        // restaurant
      [],                // platforms
      [],                // food scores
      [],                // reviews
      [{ totalAnalyzed: 0, positiveCount: 0, negativeCount: 0, neutralCount: 0 }], // sentiment
    ]);

    // Ilk istek - MISS
    const firstRes = await app.inject({
      method: "GET",
      url: "/api/v1/restaurants/test-restaurant",
    });
    expect(firstRes.statusCode).toBe(200);
    expect(firstRes.headers["x-cache"]).toBe("MISS");

    // Ikinci istek - HIT
    const secondRes = await app.inject({
      method: "GET",
      url: "/api/v1/restaurants/test-restaurant",
    });
    expect(secondRes.statusCode).toBe(200);
    expect(secondRes.headers["x-cache"]).toBe("HIT");
  });
});
