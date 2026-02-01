/**
 * iyisiniye Seed Data Scripti
 *
 * 5 ornek Istanbul restorani, platform kayitlari ve 10 Turkce yorum ekler.
 *
 * Calistirma: npx tsx src/seed.ts
 */

import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import "dotenv/config";
import {
  restaurants,
  restaurantPlatforms,
  reviews,
} from "./schema.js";

// ============================================================================
// VERITABANI BAGLANTISI
// ============================================================================

const DATABASE_URL = process.env.DATABASE_URL;
if (!DATABASE_URL) {
  throw new Error("DATABASE_URL ortam degiskeni tanimlanmamis!");
}

const client = postgres(DATABASE_URL, {
  max: 1,
  connect_timeout: 10,
});

const db = drizzle(client);

// ============================================================================
// SEED VERILERI
// ============================================================================

const restaurantData = [
  {
    name: "Ciya Sofrasi",
    slug: "ciya-sofrasi",
    address: "Caferaga Mah. Guneslibahce Sok. No:43, Kadikoy",
    district: "Kadikoy",
    neighborhood: "Caferaga",
    location: { lat: 40.9903, lng: 29.0252 },
    phone: "+90 216 330 3190",
    website: "https://ciya.com.tr",
    cuisineType: ["Turk Mutfagi", "Anadolu Mutfagi", "Kebap"],
    priceRange: 2 as number,
    overallScore: "4.60",
    totalReviews: 0,
    isActive: true,
    imageUrl: null,
  },
  {
    name: "Mikla",
    slug: "mikla",
    address: "The Marmara Pera, Mesrutiyet Cad. No:15, Beyoglu",
    district: "Beyoglu",
    neighborhood: "Asmalimescit",
    location: { lat: 41.0312, lng: 28.9744 },
    phone: "+90 212 293 5656",
    website: "https://miklarestaurant.com",
    cuisineType: ["Modern Turk", "Fine Dining", "Akdeniz"],
    priceRange: 4 as number,
    overallScore: "4.50",
    totalReviews: 0,
    isActive: true,
    imageUrl: null,
  },
  {
    name: "Karakoy Lokantasi",
    slug: "karakoy-lokantasi",
    address: "Kemankes Cad. No:37/A, Karakoy, Beyoglu",
    district: "Beyoglu",
    neighborhood: "Karakoy",
    location: { lat: 41.0226, lng: 28.9771 },
    phone: "+90 212 292 4455",
    website: "https://karakoylokantasi.com",
    cuisineType: ["Turk Mutfagi", "Deniz Urunleri", "Ev Yemekleri"],
    priceRange: 3 as number,
    overallScore: "4.30",
    totalReviews: 0,
    isActive: true,
    imageUrl: null,
  },
  {
    name: "Pandeli",
    slug: "pandeli",
    address: "Misir Carsisi No:1, Eminonu, Fatih",
    district: "Fatih",
    neighborhood: "Eminonu",
    location: { lat: 41.0163, lng: 28.9708 },
    phone: "+90 212 527 3909",
    website: null,
    cuisineType: ["Osmanli Mutfagi", "Turk Mutfagi", "Klasik"],
    priceRange: 3 as number,
    overallScore: "4.20",
    totalReviews: 0,
    isActive: true,
    imageUrl: null,
  },
  {
    name: "Kanaat Lokantasi",
    slug: "kanaat-lokantasi",
    address: "Selmanipak Cad. No:25, Uskudar",
    district: "Uskudar",
    neighborhood: "Selmanipak",
    location: { lat: 41.0239, lng: 29.0155 },
    phone: "+90 216 553 3791",
    website: null,
    cuisineType: ["Turk Mutfagi", "Ev Yemekleri", "Tatli"],
    priceRange: 2 as number,
    overallScore: "4.40",
    totalReviews: 0,
    isActive: true,
    imageUrl: null,
  },
];

// Her restoran icin Google Maps platform kaydı
const platformTemplate = (restaurantId: number, idx: number) => ({
  restaurantId,
  platform: "google_maps" as const,
  externalId: `ChIJ_fake_id_${idx}`,
  externalUrl: `https://maps.google.com/?cid=${1000000 + idx}`,
  platformScore: restaurantData[idx].overallScore,
  platformReviews: 0,
  matchConfidence: "0.95",
  lastScraped: null as Date | null,
  rawData: null,
});

// 10 gercekci Turkce yorum (5 restoran x 2 yorum)
const reviewsData = [
  // Ciya Sofrasi yorumlari
  {
    platformIdx: 0,
    externalReviewId: "gm_rev_001",
    authorName: "Ahmet Yilmaz",
    rating: 5,
    text: "Ciya'nin kuzu tandir ve ali nazik kebabi inanilmaz lezzetli. Yillardir gelirim, kalitesi hic dusmuyor. Ozellikle gunduz menusundeki ev yemekleri muhtesem. Kadikoy'e gelip buraya ugramayan cok sey kacirir.",
    reviewDate: new Date("2025-12-15T14:30:00+03:00"),
    language: "tr",
    processed: false,
  },
  {
    platformIdx: 0,
    externalReviewId: "gm_rev_002",
    authorName: "Elif Demir",
    rating: 4,
    text: "Lezzetler harika ama ogle saatlerinde cok kalabalik oluyor. Sirasiz gitmek lazim. Ickli koftesi ve yaprak sarmasi favorilerim. Fiyatlar da gayet makul, kalitesine gore cok uygun.",
    reviewDate: new Date("2025-11-20T12:00:00+03:00"),
    language: "tr",
    processed: false,
  },
  // Mikla yorumlari
  {
    platformIdx: 1,
    externalReviewId: "gm_rev_003",
    authorName: "Mehmet Kaya",
    rating: 5,
    text: "Fine dining kategorisinde Istanbul'un en iyilerinden biri. Manzara muhtetesem, yemekler sanat eseri gibi sunuluyor. Sef Mehmet Gurs'un yaratici dokunuslari her tabakta hissediliyor. Ozel geceler icin ideal.",
    reviewDate: new Date("2025-10-05T20:00:00+03:00"),
    language: "tr",
    processed: false,
  },
  {
    platformIdx: 1,
    externalReviewId: "gm_rev_004",
    authorName: "Zeynep Arslan",
    rating: 4,
    text: "Yemekler ve sunum olarak kusursuz. Fiyatlar yuksek ama karsiligi veriliyor. Teras katindaki manzara ile akam yemegi unutulmaz bir deneyim. Saraplari da cok iyi secilmis.",
    reviewDate: new Date("2025-09-18T21:00:00+03:00"),
    language: "tr",
    processed: false,
  },
  // Karakoy Lokantasi yorumlari
  {
    platformIdx: 2,
    externalReviewId: "gm_rev_005",
    authorName: "Can Ozturk",
    rating: 5,
    text: "Karakoy Lokantasi'nin ogle menusu harika. Zeytinyagli enginar, karniyarik ve tatli icin kazandibi mutlaka denenecekler listesinde. Mekan sade ama samimi, personel cok ilgili.",
    reviewDate: new Date("2025-12-01T13:00:00+03:00"),
    language: "tr",
    processed: false,
  },
  {
    platformIdx: 2,
    externalReviewId: "gm_rev_006",
    authorName: "Selin Yildiz",
    rating: 3,
    text: "Yemekler fena degil ama eskisi kadar iyi bulmadim. Hamsi tava siparisi verdim, porsiyonu kucuk geldi. Fiyatlar Karakoy icin normal ama beklentimi tam karsilamadi. Mekan olarak guzel bir ambiyans var.",
    reviewDate: new Date("2025-11-10T12:30:00+03:00"),
    language: "tr",
    processed: false,
  },
  // Pandeli yorumlari
  {
    platformIdx: 3,
    externalReviewId: "gm_rev_007",
    authorName: "Burak Celik",
    rating: 4,
    text: "Misir Carsisi'nin ust katindaki bu tarihi mekan gercekten ozel. Hunkar begendi ve ic pilav cok lezzetliydi. Mekanin tarihini dusununce yemek yemek ayri bir keyif. Turistik ama yerli halki da memnun ediyor.",
    reviewDate: new Date("2025-08-22T13:00:00+03:00"),
    language: "tr",
    processed: false,
  },
  {
    platformIdx: 3,
    externalReviewId: "gm_rev_008",
    authorName: "Ayse Sahin",
    rating: 4,
    text: "Pandeli'de klasik Turk ve Osmanli lezzetlerini bulmak mumkun. Patlican kebabi ve baklava nefisti. Servis biraz yavas olabiliyor ama mekanin atmosferi bunu telafi ediyor. Tavsiye ederim.",
    reviewDate: new Date("2025-07-30T14:00:00+03:00"),
    language: "tr",
    processed: false,
  },
  // Kanaat Lokantasi yorumlari
  {
    platformIdx: 4,
    externalReviewId: "gm_rev_009",
    authorName: "Fatih Dogan",
    rating: 5,
    text: "Uskudar'in efsanesi Kanaat Lokantasi. Tavuk gogsu tatlisi Turkiye'nin en iyisi desem abartmam. Kuru fasulye, pilav ve ayran uclusu muthis. 1933'ten beri ayni kaliteyi korumak buyuk basari.",
    reviewDate: new Date("2025-12-20T12:00:00+03:00"),
    language: "tr",
    processed: false,
  },
  {
    platformIdx: 4,
    externalReviewId: "gm_rev_010",
    authorName: "Merve Akin",
    rating: 4,
    text: "Kanaat'in tatlilari esasiz. Ozellikle sutlac ve kazandibi icin gidilir. Yemekleri de ev yapimi tadinda, sade ve doyurucu. Fiyatlar uygun, Uskudar'a gelen herkesin ugramasi gereken bir yer.",
    reviewDate: new Date("2025-11-05T13:30:00+03:00"),
    language: "tr",
    processed: false,
  },
];

// ============================================================================
// SEED FONKSIYONU
// ============================================================================

async function seed() {
  console.log("Seed islemi basliyor...\n");

  try {
    // 1. Mevcut verileri temizle (sirasiyla - foreign key kisitlamalarindan dolayi)
    console.log("1. Mevcut veriler temizleniyor...");
    await db.delete(reviews);
    await db.delete(restaurantPlatforms);
    await db.delete(restaurants);
    console.log("   Mevcut veriler temizlendi.\n");

    // 2. Restoranlari ekle
    console.log("2. Restoranlar ekleniyor...");
    const insertedRestaurants = await db
      .insert(restaurants)
      .values(restaurantData)
      .returning({ id: restaurants.id, name: restaurants.name });

    for (const r of insertedRestaurants) {
      console.log(`   [+] Restoran #${r.id}: ${r.name}`);
    }
    console.log(`   Toplam ${insertedRestaurants.length} restoran eklendi.\n`);

    // 3. Platform kayitlarini ekle (her restoran icin google_maps)
    console.log("3. Platform kayitlari ekleniyor...");
    const platformValues = insertedRestaurants.map((r, idx) =>
      platformTemplate(r.id, idx)
    );
    const insertedPlatforms = await db
      .insert(restaurantPlatforms)
      .values(platformValues)
      .returning({
        id: restaurantPlatforms.id,
        restaurantId: restaurantPlatforms.restaurantId,
        platform: restaurantPlatforms.platform,
      });

    for (const p of insertedPlatforms) {
      console.log(
        `   [+] Platform #${p.id}: Restoran ${p.restaurantId} -> ${p.platform}`
      );
    }
    console.log(
      `   Toplam ${insertedPlatforms.length} platform kaydi eklendi.\n`
    );

    // 4. Yorumlari ekle
    console.log("4. Yorumlar ekleniyor...");
    const reviewValues = reviewsData.map((review) => ({
      restaurantPlatformId: insertedPlatforms[review.platformIdx].id,
      externalReviewId: review.externalReviewId,
      authorName: review.authorName,
      rating: review.rating,
      text: review.text,
      reviewDate: review.reviewDate,
      language: review.language,
      processed: review.processed,
    }));

    const insertedReviews = await db
      .insert(reviews)
      .values(reviewValues)
      .returning({
        id: reviews.id,
        authorName: reviews.authorName,
        rating: reviews.rating,
      });

    for (const r of insertedReviews) {
      console.log(
        `   [+] Yorum #${r.id}: ${r.authorName} (${r.rating}/5)`
      );
    }
    console.log(`   Toplam ${insertedReviews.length} yorum eklendi.\n`);

    // 5. Restoranlarin total_reviews alanini guncelle
    console.log("5. Restoran yorum sayilari guncelleniyor...");
    for (let i = 0; i < insertedRestaurants.length; i++) {
      const rid = insertedRestaurants[i].id;
      // Her restoran icin 2 yorum var
      await client`UPDATE restaurants SET total_reviews = 2 WHERE id = ${rid}`;
      console.log(
        `   [~] Restoran #${rid}: total_reviews = 2`
      );
    }
    console.log("   Yorum sayilari guncellendi.\n");

    // 6. Dogrulama
    console.log("6. Dogrulama...");
    const restaurantCount =
      await client`SELECT count(*) as c FROM restaurants`;
    const platformCount =
      await client`SELECT count(*) as c FROM restaurant_platforms`;
    const reviewCount = await client`SELECT count(*) as c FROM reviews`;

    console.log(`   Restoranlar: ${restaurantCount[0].c}`);
    console.log(`   Platform kayitlari: ${platformCount[0].c}`);
    console.log(`   Yorumlar: ${reviewCount[0].c}`);
    console.log("\nSeed islemi basariyla tamamlandi!");
  } catch (error) {
    console.error("SEED HATASI:", error);
    process.exit(1);
  } finally {
    await client.end();
  }
}

seed();
