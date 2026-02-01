import Fastify from "fastify";
import cors from "@fastify/cors";
import helmet from "@fastify/helmet";
import rateLimit from "@fastify/rate-limit";
import {
  serializerCompiler,
  validatorCompiler,
} from "fastify-type-provider-zod";
import "dotenv/config";

import { searchRoutes } from "./routes/search.js";
import { restaurantRoutes } from "./routes/restaurant.js";
import { autocompleteRoutes } from "./routes/autocomplete.js";
import { dishRoutes } from "./routes/dish.js";

const PORT = Number(process.env.API_PORT) || 3001;
const HOST = process.env.API_HOST || "0.0.0.0";

export async function buildApp() {
  const isProduction = process.env.NODE_ENV === "production";
  const isTest = process.env.NODE_ENV === "test";

  const app = Fastify({
    logger: isTest
      ? false
      : {
          level: isProduction ? "info" : "debug",
          transport: !isProduction ? { target: "pino-pretty" } : undefined,
        },
  });

  // Zod entegrasyonu
  app.setValidatorCompiler(validatorCompiler);
  app.setSerializerCompiler(serializerCompiler);

  // Eklentiler
  await app.register(cors, {
    origin: process.env.NODE_ENV === "production"
      ? ["https://iyisiniye.com"]
      : true,
  });

  await app.register(helmet);

  await app.register(rateLimit, {
    max: 100,
    timeWindow: "1 minute",
  });

  // Saglik kontrolu
  app.get("/health", async () => {
    return {
      status: "ok",
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
    };
  });

  // API v1 root
  app.get("/api/v1", async () => {
    return {
      name: "iyisiniye API",
      version: "0.1.0",
      docs: "/api/v1/docs",
    };
  });

  // Route'lar
  await app.register(searchRoutes);
  await app.register(restaurantRoutes);
  await app.register(autocompleteRoutes);
  await app.register(dishRoutes);

  return app;
}

async function start() {
  try {
    const app = await buildApp();
    await app.listen({ port: PORT, host: HOST });
    console.log(`iyisiniye API sunucusu calisiyor: http://${HOST}:${PORT}`);
  } catch (error) {
    console.error("Sunucu baslatilamadi:", error);
    process.exit(1);
  }
}

// Test ortaminda otomatik baslatmayi engelle
if (process.env.NODE_ENV !== "test") {
  start();
}
