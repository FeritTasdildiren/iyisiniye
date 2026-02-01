/**
 * iyisiniye Ortak Yardimci Fonksiyonlar
 */

/**
 * Turkce karakterleri ASCII'ye donusturur
 * Ornek: "Cankaya" -> "cankaya", "Uskudar" -> "uskudar"
 */
export function turkishToAscii(text: string): string {
  const map: Record<string, string> = {
    "ç": "c", "Ç": "C",
    "ğ": "g", "Ğ": "G",
    "ı": "i", "İ": "I",
    "ö": "o", "Ö": "O",
    "ş": "s", "Ş": "S",
    "ü": "u", "Ü": "U",
  };
  return text.replace(/[çÇğĞıİöÖşŞüÜ]/g, (char) => map[char] || char);
}

/**
 * URL-uyumlu slug olusturur
 * Ornek: "Karadeniz Pidesi" -> "karadeniz-pidesi"
 */
export function slugify(text: string): string {
  return turkishToAscii(text)
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, "")
    .replace(/[\s_]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/**
 * Fiyati formatlar
 * Ornek: 15050 -> "150,50 TL"
 */
export function formatPrice(priceInKurus: number): string {
  const lira = Math.floor(priceInKurus / 100);
  const kurus = priceInKurus % 100;
  return `${lira.toLocaleString("tr-TR")}${kurus > 0 ? `,${kurus.toString().padStart(2, "0")}` : ""} TL`;
}

/**
 * Rating'i yildiz olarak gosterir
 * Ornek: 4.3 -> "4.3"
 */
export function formatRating(rating: number): string {
  return rating.toFixed(1);
}

/**
 * Sayfalama meta bilgisi hesaplar
 */
export function calculatePagination(total: number, page: number, limit: number) {
  const totalPages = Math.ceil(total / limit);
  return {
    page,
    limit,
    total,
    totalPages,
    hasNext: page < totalPages,
    hasPrev: page > 1,
  };
}

/**
 * Iki koordinat arasindaki mesafeyi km olarak hesaplar (Haversine)
 */
export function calculateDistance(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number {
  const R = 6371; // Dunya yaricapi (km)
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) *
      Math.cos(toRad(lat2)) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

function toRad(deg: number): number {
  return (deg * Math.PI) / 180;
}
