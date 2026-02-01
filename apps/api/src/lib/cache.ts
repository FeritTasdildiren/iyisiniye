/**
 * Cache Yardimci Fonksiyonlari
 *
 * Redis uzerinde JSON cache islemleri.
 * Tum fonksiyonlarda graceful degradation: Redis hatalarinda sessizce devam eder.
 */

import { redis } from "./redis.js";

/**
 * Cache'den veri oku.
 * Hata durumunda veya cache miss'te null doner.
 */
export async function cacheGet<T>(key: string): Promise<T | null> {
  try {
    const data = await redis.get(key);
    if (data === null) return null;
    return JSON.parse(data) as T;
  } catch {
    return null;
  }
}

/**
 * Cache'e veri yaz.
 * @param key - Cache anahtari
 * @param data - Kaydedilecek veri (JSON.stringify yapilir)
 * @param ttlSeconds - Gecerlilik suresi (saniye)
 */
export async function cacheSet(
  key: string,
  data: unknown,
  ttlSeconds: number
): Promise<void> {
  try {
    await redis.set(key, JSON.stringify(data), "EX", ttlSeconds);
  } catch {
    // Redis hatasi — sessizce devam et
  }
}

/**
 * Tek bir cache anahtarini sil.
 */
export async function cacheDelete(key: string): Promise<void> {
  try {
    await redis.del(key);
  } catch {
    // Redis hatasi — sessizce devam et
  }
}

/**
 * Pattern'e uyan tum anahtarlari sil.
 * SCAN kullanarak buyuk veri setlerinde blocking'i onler.
 * @param pattern - Glob pattern (orn: "search:*", "restaurant:*")
 */
export async function cacheDeletePattern(pattern: string): Promise<void> {
  try {
    let cursor = "0";
    do {
      const [nextCursor, keys] = await redis.scan(
        cursor,
        "MATCH",
        pattern,
        "COUNT",
        100
      );
      cursor = nextCursor;
      if (keys.length > 0) {
        await redis.del(...keys);
      }
    } while (cursor !== "0");
  } catch {
    // Redis hatasi — sessizce devam et
  }
}
