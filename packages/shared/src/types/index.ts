/**
 * iyisiniye Ortak Tip Tanimlari
 * Tum uygulamalar ve paketler tarafindan kullanilan tipler
 */

/** Restoran temel bilgileri */
export interface Restaurant {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  address: string;
  city: string;
  district: string;
  latitude: number;
  longitude: number;
  phone: string | null;
  website: string | null;
  cuisineTypes: CuisineType[];
  priceRange: PriceRange;
  averageRating: number;
  totalReviews: number;
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
}

/** Yemek bilgileri */
export interface Dish {
  id: string;
  restaurantId: string;
  name: string;
  slug: string;
  description: string | null;
  price: number | null;
  currency: "TRY";
  category: DishCategory;
  tags: string[];
  averageRating: number;
  totalReviews: number;
  imageUrl: string | null;
  isAvailable: boolean;
  createdAt: Date;
  updatedAt: Date;
}

/** Yorum/Degerlendirme */
export interface Review {
  id: string;
  restaurantId: string;
  dishId: string | null;
  source: ReviewSource;
  sourceId: string;
  authorName: string;
  rating: number;
  comment: string;
  sentiment: SentimentScore | null;
  visitDate: Date | null;
  createdAt: Date;
  updatedAt: Date;
}

/** Duygu analizi skoru */
export interface SentimentScore {
  positive: number;
  negative: number;
  neutral: number;
  overall: "positive" | "negative" | "neutral";
}

/** Mutfak turleri */
export type CuisineType =
  | "turk"
  | "kebap"
  | "balik"
  | "doner"
  | "pide_lahmacun"
  | "ev_yemekleri"
  | "sokak_lezzetleri"
  | "tatli_pasta"
  | "kahvalti"
  | "italyan"
  | "uzakdogu"
  | "fast_food"
  | "vegan"
  | "diger";

/** Fiyat araligi */
export type PriceRange = "budget" | "mid" | "fine" | "luxury";

/** Yemek kategorisi */
export type DishCategory =
  | "ana_yemek"
  | "baslangic"
  | "salata"
  | "corba"
  | "tatli"
  | "icecek"
  | "kahvalti"
  | "aperatif"
  | "diger";

/** Yorum kaynagi */
export type ReviewSource =
  | "google_maps"
  | "yemeksepeti"
  | "trendyol_yemek"
  | "tripadvisor"
  | "foursquare"
  | "manual";

/** Sayfalama parametreleri */
export interface PaginationParams {
  page: number;
  limit: number;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
}

/** Sayfalama yaniti */
export interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
    hasNext: boolean;
    hasPrev: boolean;
  };
}

/** API hata yaniti */
export interface ApiError {
  statusCode: number;
  error: string;
  message: string;
  details?: unknown;
}
