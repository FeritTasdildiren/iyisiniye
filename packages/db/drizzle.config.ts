/**
 * Drizzle Kit Yapilandirmasi
 *
 * Migration olusturma ve veritabani senkronizasyonu icin kullanilir.
 *
 * Komutlar:
 *   pnpm db:generate  -> Migration dosyalari olusturur
 *   pnpm db:migrate   -> Migration'lari veritabanina uygular
 *   pnpm db:push      -> Semayi dogrudan veritabanina push eder (dev icin)
 *   pnpm db:studio    -> Drizzle Studio'yu acar (goruntuleyici)
 */

import "dotenv/config";
import { defineConfig } from "drizzle-kit";

const DATABASE_URL = process.env.DATABASE_URL;

if (!DATABASE_URL) {
  throw new Error(
    "DATABASE_URL ortam degiskeni tanimlanmamis! " +
      ".env dosyasini kontrol edin."
  );
}

export default defineConfig({
  // Sema dosyasi
  schema: "./src/schema.ts",

  // Migration cikti dizini
  out: "./src/migrations",

  // Veritabani surucusu
  dialect: "postgresql",

  // Baglanti bilgileri
  // NOT: Sifredeki ozel karakterler (#, !) URL parse sorunlarina neden oldugu icin
  // ayri parametreler kullaniliyor. Ortam degiskenleri .env dosyasindan okunur.
  dbCredentials: {
    host: process.env.DATABASE_HOST || "127.0.0.1",
    port: Number(process.env.DATABASE_PORT) || 5433,
    user: process.env.DATABASE_USER || "iyisiniye_app",
    password: process.env.DATABASE_PASSWORD || "",
    database: process.env.DATABASE_NAME || "iyisiniye",
    ssl: false,
  },

  // Verbose cikti (debug icin)
  verbose: true,

  // Katı mod - uyumsuz degisiklikleri uyar
  strict: true,
});
