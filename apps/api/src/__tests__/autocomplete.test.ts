/**
 * GET /api/v1/autocomplete - Otomatik Tamamlama Endpoint Entegrasyon Testleri
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

describe("GET /api/v1/autocomplete", () => {
  it('q="ke" ile 200 ve restaurants+dishes array doner', async () => {
    setQueryResults([
      // 1. Restoran onerileri
      [
        {
          id: 1,
          name: "Kebapci Mehmet",
          slug: "kebapci-mehmet",
          district: "Kadikoy",
          cuisineType: ["kebap"],
          overallScore: "8.50",
          similarity: 0.45,
        },
      ],
      // 2. Yemek onerileri
      [
        {
          id: 1,
          name: "Kebap",
          slug: "kebap",
          category: "kebap",
          similarity: 0.6,
          restaurantCount: 25,
        },
      ],
    ]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/autocomplete?q=ke",
    });

    expect(res.statusCode).toBe(200);

    const body = res.json();
    expect(body).toHaveProperty("restaurants");
    expect(body).toHaveProperty("dishes");
    expect(Array.isArray(body.restaurants)).toBe(true);
    expect(Array.isArray(body.dishes)).toBe(true);
  });

  it('q="a" (tek karakter) ile validation error doner', async () => {
    const res = await app.inject({
      method: "GET",
      url: "/api/v1/autocomplete?q=a",
    });

    expect(res.statusCode).toBe(400);
  });

  it("q parametresi olmadan 400 doner", async () => {
    const res = await app.inject({
      method: "GET",
      url: "/api/v1/autocomplete",
    });

    expect(res.statusCode).toBe(400);
  });

  it("bos string q ile 400 doner", async () => {
    const res = await app.inject({
      method: "GET",
      url: "/api/v1/autocomplete?q=",
    });

    expect(res.statusCode).toBe(400);
  });

  it("response yapisinda restaurants array'inin her elemani dogru alanlara sahiptir", async () => {
    setQueryResults([
      [
        {
          id: 5,
          name: "Pizza Roma",
          slug: "pizza-roma",
          district: "Besiktas",
          cuisineType: ["italyan"],
          overallScore: "7.20",
          similarity: 0.5,
        },
      ],
      [],
    ]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/autocomplete?q=pi",
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();

    if (body.restaurants.length > 0) {
      const r = body.restaurants[0];
      expect(r).toHaveProperty("id");
      expect(r).toHaveProperty("name");
      expect(r).toHaveProperty("slug");
      expect(r).toHaveProperty("district");
      expect(r).toHaveProperty("cuisineType");
      expect(r).toHaveProperty("overallScore");
      // similarity alanı response'da olmamali (strip ediliyor)
      expect(r).not.toHaveProperty("similarity");
    }
  });

  it("response yapisinda dishes array'inin her elemani dogru alanlara sahiptir", async () => {
    setQueryResults([
      [],
      [
        {
          id: 10,
          name: "Baklava",
          slug: "baklava",
          category: "tatli",
          similarity: 0.7,
          restaurantCount: 15,
        },
      ],
    ]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/autocomplete?q=ba",
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();

    if (body.dishes.length > 0) {
      const d = body.dishes[0];
      expect(d).toHaveProperty("id");
      expect(d).toHaveProperty("name");
      expect(d).toHaveProperty("slug");
      expect(d).toHaveProperty("category");
      expect(d).toHaveProperty("restaurantCount");
      // similarity alanı response'da olmamali
      expect(d).not.toHaveProperty("similarity");
    }
  });

  it("sonuc yoksa bos array'ler doner", async () => {
    setQueryResults([
      [], // Restoran yok
      [], // Yemek yok
    ]);

    const res = await app.inject({
      method: "GET",
      url: "/api/v1/autocomplete?q=xyzxyz",
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.restaurants).toEqual([]);
    expect(body.dishes).toEqual([]);
  });
});
