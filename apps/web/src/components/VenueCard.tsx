import React from "react";
import ScoreBadge from "./ScoreBadge";

type TopDish = {
  name: string;
  score: number;
};

type VenueCardProps = {
  name: string;
  slug: string;
  district: string;
  cuisineType: string;
  overallScore: number;
  topDishes: TopDish[];
  reviewCount: number;
  priceRange: number;
  imageUrl?: string;
};

const priceLabels = (priceRange: number) => {
  const clamped = Math.max(1, Math.min(4, priceRange));
  return "₺".repeat(clamped);
};

export default function VenueCard({
  name,
  slug,
  district,
  cuisineType,
  overallScore,
  topDishes,
  reviewCount,
  priceRange,
  imageUrl,
}: VenueCardProps) {
  return (
    <a href={`/restaurant/${slug}`} className="block no-underline">
      <article
        className="group rounded-lg shadow-sm hover:shadow-lg transition-shadow duration-200 focus-within:ring-2 focus-within:ring-orange-400 border border-slate-200 overflow-hidden bg-white"
        aria-label={`${name} - ${district}, ${cuisineType}`}
      >
        <div className="aspect-video w-full overflow-hidden bg-slate-100">
          {imageUrl ? (
            <img
              src={imageUrl}
              alt={name}
              className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
              loading="lazy"
            />
          ) : (
            <div className="h-full w-full bg-gradient-to-br from-slate-100 to-slate-200" />
          )}
        </div>
        <div className="p-4 space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="font-poppins font-bold text-slate-900">{name}</h3>
              <p className="text-sm text-slate-500">
                {district} · {cuisineType} · {priceLabels(priceRange)}
              </p>
            </div>
            <ScoreBadge score={overallScore} size="md" />
          </div>
          <div className="text-sm text-slate-500">{reviewCount} yorum</div>
          <div className="flex flex-wrap gap-2">
            {topDishes.map((dish) => (
              <div key={`${slug}-${dish.name}`} className="flex items-center gap-2 rounded-full bg-slate-50 px-3 py-1">
                <ScoreBadge score={dish.score} size="sm" />
                <span className="text-sm text-slate-700">{dish.name}</span>
              </div>
            ))}
          </div>
        </div>
      </article>
    </a>
  );
}
