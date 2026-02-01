/**
 * iyisiniye Veritabani Paketi
 *
 * Drizzle ORM ile PostgreSQL baglantisi ve sema tanimlari.
 *
 * Kullanim:
 *   import { db, restaurants, reviews } from "@iyisiniye/db";
 *   import { eq } from "drizzle-orm";
 *
 *   const result = await db.select().from(restaurants).where(eq(restaurants.isActive, true));
 */

import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import "dotenv/config";

import * as schema from "./schema.js";

// Veritabani baglanti URL'i
const DATABASE_URL = process.env.DATABASE_URL;

if (!DATABASE_URL) {
  throw new Error("DATABASE_URL ortam degiskeni tanimlanmamis!");
}

// PostgreSQL istemcisi
const client = postgres(DATABASE_URL, {
  max: 10, // Maksimum baglanti sayisi
  idle_timeout: 20, // Bosta bekleme suresi (saniye)
  connect_timeout: 10, // Baglanti zaman asimi (saniye)
});

// Drizzle ORM ornegi (sema ile birlikte - relations sorgulari icin)
export const db = drizzle(client, { schema });

// Tum sema export'lari
export * from "./schema.js";

// Baglanti kapatma fonksiyonu (graceful shutdown icin)
export async function closeConnection(): Promise<void> {
  await client.end();
}
