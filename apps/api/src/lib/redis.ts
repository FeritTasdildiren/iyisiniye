/**
 * Redis Client Singleton
 *
 * ioredis ile Redis baglantisi.
 * Graceful disconnect + retry stratejisi.
 */

import Redis from "ioredis";

const REDIS_URL = process.env.REDIS_URL || "redis://localhost:6379";

export const redis = new Redis(REDIS_URL, {
  maxRetriesPerRequest: 3,
  retryStrategy(times) {
    if (times > 10) {
      console.error(`[Redis] ${times} deneme sonrasi yeniden baglanmaktan vazgecildi.`);
      return null; // Baglanti denemesini durdur
    }
    const delay = Math.min(times * 200, 5000);
    console.warn(`[Redis] Yeniden baglanma denemesi #${times}, ${delay}ms sonra...`);
    return delay;
  },
  lazyConnect: false,
});

redis.on("connect", () => {
  console.log("[Redis] Baglanti kuruldu.");
});

redis.on("error", (err) => {
  console.error("[Redis] Baglanti hatasi:", err.message);
});

redis.on("close", () => {
  console.warn("[Redis] Baglanti kapandi.");
});

// Graceful shutdown
const gracefulDisconnect = async () => {
  try {
    await redis.quit();
    console.log("[Redis] Baglanti duzgun sekilde kapatildi.");
  } catch {
    // Zaten kapanmis olabilir
  }
};

process.on("SIGINT", gracefulDisconnect);
process.on("SIGTERM", gracefulDisconnect);
