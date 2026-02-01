/**
 * iyisiniye Ortak Sabitler
 */

/** API versiyonu */
export const API_VERSION = "v1";

/** Varsayilan sayfalama limiti */
export const DEFAULT_PAGE_LIMIT = 20;

/** Maksimum sayfalama limiti */
export const MAX_PAGE_LIMIT = 100;

/** Desteklenen sehirler */
export const SUPPORTED_CITIES = [
  "istanbul",
  "ankara",
  "izmir",
  "antalya",
  "bursa",
  "adana",
  "gaziantep",
  "konya",
  "mersin",
  "diyarbakir",
  "trabzon",
  "eskisehir",
] as const;

export type SupportedCity = (typeof SUPPORTED_CITIES)[number];

/** Fiyat araligi etiketleri */
export const PRICE_RANGE_LABELS: Record<string, string> = {
  budget: "Uygun",
  mid: "Orta",
  fine: "Ust Segment",
  luxury: "Luks",
};

/** Mutfak turu etiketleri */
export const CUISINE_TYPE_LABELS: Record<string, string> = {
  turk: "Turk Mutfagi",
  kebap: "Kebap",
  balik: "Balik & Deniz Urunleri",
  doner: "Doner",
  pide_lahmacun: "Pide & Lahmacun",
  ev_yemekleri: "Ev Yemekleri",
  sokak_lezzetleri: "Sokak Lezzetleri",
  tatli_pasta: "Tatli & Pasta",
  kahvalti: "Kahvalti",
  italyan: "Italyan",
  uzakdogu: "Uzakdogu",
  fast_food: "Fast Food",
  vegan: "Vegan & Vejetaryen",
  diger: "Diger",
};

/** Rating sinir degerleri */
export const RATING = {
  MIN: 1,
  MAX: 5,
  EXCELLENT_THRESHOLD: 4.5,
  GOOD_THRESHOLD: 3.5,
  AVERAGE_THRESHOLD: 2.5,
} as const;

/** Scraper kaynaklari */
export const SCRAPER_SOURCES = {
  GOOGLE_MAPS: "google_maps",
  YEMEKSEPETI: "yemeksepeti",
  TRENDYOL_YEMEK: "trendyol_yemek",
  TRIPADVISOR: "tripadvisor",
  FOURSQUARE: "foursquare",
} as const;
