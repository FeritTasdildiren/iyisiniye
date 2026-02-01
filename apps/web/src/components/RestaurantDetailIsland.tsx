import React, { useEffect, useState } from 'react';
import ScoreBadge from './ScoreBadge';
import DishRow from './DishRow';
import Button from './Button';

interface RestaurantDetailIslandProps {
  slug: string;
}

interface DishScore {
  foodName: string;
  score: number;
  reviewCount: number;
  confidence: number;
  sentimentDistribution: { positive: number; negative: number; neutral: number };
}

interface Review {
  id: string;
  authorName: string;
  rating: number;
  text: string;
  reviewDate: string;
  platform: string;
  mentionedDishes: { dishName: string; sentiment: 'positive' | 'negative' | 'neutral' }[];
}

interface RestaurantData {
  restaurant: {
    id: string;
    name: string;
    slug: string;
    address: string;
    district: string;
    phone: string;
    cuisineType: string;
    priceRange: number;
    overallScore: number;
    totalReviews: number;
    imageUrl: string;
    platforms: string[];
  };
  foodScores: DishScore[];
  recentReviews: Review[];
  sentimentSummary: {
    totalAnalyzed: number;
    overallSentiment: string;
    distribution: { positive: number; negative: number; neutral: number };
  };
}

const API_BASE_URL = typeof window !== 'undefined' ? '/api/v1' : 'http://localhost:3001/api/v1';

export default function RestaurantDetailIsland({ slug }: RestaurantDetailIslandProps) {
  const [data, setData] = useState<RestaurantData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openDishIndex, setOpenDishIndex] = useState<number | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetch(`${API_BASE_URL}/restaurants/${slug}`);
        if (!res.ok) throw new Error('Restoran bilgileri yüklenemedi');
        const jsonData = await res.json();
        setData(jsonData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Bir hata oluştu');
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [slug]);

  if (loading) {
    return (
      <div className="w-full max-w-5xl mx-auto p-4 space-y-8 animate-pulse">
        <div className="h-64 bg-gray-200 rounded-xl w-full"></div>
        <div className="h-40 bg-gray-200 rounded-xl w-full"></div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-20">
        <h2 className="text-xl font-bold text-gray-800">Veri alınamadı</h2>
        <p className="text-gray-600 mt-2">{error}</p>
        <Button onClick={() => window.location.reload()} className="mt-4">Tekrar Dene</Button>
      </div>
    );
  }

  const { restaurant, foodScores, recentReviews, sentimentSummary } = data;

  return (
    <div className="w-full max-w-5xl mx-auto px-4 pb-12">
      {/* Header Section */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold font-poppins text-gray-900 mb-2">{restaurant.name}</h1>
        <div className="flex flex-wrap items-center gap-2 sm:gap-4 text-gray-600">
            <span>{restaurant.district}</span>
            <span>&bull;</span>
            <span className="capitalize">{restaurant.cuisineType}</span>
            <span>&bull;</span>
            <span className="flex">{Array(restaurant.priceRange).fill('₺').join('')}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Dish Scoreboard */}
        <div className="lg:col-span-2 space-y-8">
            <section>
                <h2 className="text-2xl font-bold font-poppins mb-4 text-orange-950">Ne Yenir?</h2>
                <div className="bg-white rounded-xl shadow-sm border border-orange-100 overflow-hidden">
                    {foodScores.sort((a, b) => b.score - a.score).map((dish, index) => (
                        <div key={index} className="border-b last:border-0 border-gray-100">
                             <DishRow
                                name={dish.foodName}
                                score={dish.score}
                                reviewCount={dish.reviewCount}
                                sentiment={dish.sentimentDistribution}
                                onClick={() => setOpenDishIndex(openDishIndex === index ? null : index)}
                                isOpen={openDishIndex === index}
                             />
                        </div>
                    ))}
                </div>
            </section>

            <section>
                <h2 className="text-2xl font-bold font-poppins mb-4 text-orange-950">Son Değerlendirmeler</h2>
                <div className="space-y-4">
                    {recentReviews.map(review => (
                        <div key={review.id} className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
                            <div className="flex justify-between items-start mb-2">
                                <span className="font-semibold text-gray-900">{review.authorName}</span>
                                <span className="text-xs text-gray-500">{new Date(review.reviewDate).toLocaleDateString()}</span>
                            </div>
                            <div className="flex items-center gap-2 mb-3">
                                <div className="bg-orange-100 text-orange-700 px-2 py-0.5 rounded text-xs font-bold">
                                    {review.rating}/5
                                </div>
                                <span className="text-xs text-gray-400 uppercase tracking-wide">{review.platform}</span>
                            </div>
                            <p className="text-gray-700 leading-relaxed line-clamp-3 mb-3">&ldquo;{review.text}&rdquo;</p>
                            {review.mentionedDishes.length > 0 && (
                                <div className="flex flex-wrap gap-2">
                                    {review.mentionedDishes.map((d, i) => (
                                        <span
                                            key={i}
                                            className={`text-xs px-2 py-1 rounded-full ${
                                                d.sentiment === 'positive' ? 'bg-green-50 text-green-700' :
                                                d.sentiment === 'negative' ? 'bg-red-50 text-red-700' :
                                                'bg-gray-100 text-gray-700'
                                            }`}
                                        >
                                            {d.dishName}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </section>
        </div>

        {/* Right Column: Sentiment Dashboard */}
        <div className="space-y-6">
            <div className="bg-white p-6 rounded-xl border border-gray-200 sticky top-4">
                <div className="flex items-center justify-between mb-6">
                    <h3 className="font-bold text-lg font-poppins">Yapay Zeka Analizi</h3>
                    <ScoreBadge score={restaurant.overallScore} size="lg" />
                </div>

                <div className="space-y-4 mb-6">
                    <div>
                        <div className="flex justify-between text-sm mb-1">
                            <span className="text-green-700 font-medium">Olumlu</span>
                            <span className="text-green-700">{sentimentSummary.distribution.positive}%</span>
                        </div>
                        <div className="h-2 bg-gray-100 rounded-full overflow-hidden" role="progressbar" aria-label={`Olumlu yorum oranı: %${sentimentSummary.distribution.positive}`} aria-valuenow={sentimentSummary.distribution.positive} aria-valuemin={0} aria-valuemax={100}>
                            <div className="h-full bg-green-500 transition-all duration-500" style={{ width: `${sentimentSummary.distribution.positive}%` }}></div>
                        </div>
                    </div>
                    <div>
                        <div className="flex justify-between text-sm mb-1">
                            <span className="text-gray-600 font-medium">Notr</span>
                            <span className="text-gray-600">{sentimentSummary.distribution.neutral}%</span>
                        </div>
                        <div className="h-2 bg-gray-100 rounded-full overflow-hidden" role="progressbar" aria-label={`Notr yorum oranı: %${sentimentSummary.distribution.neutral}`} aria-valuenow={sentimentSummary.distribution.neutral} aria-valuemin={0} aria-valuemax={100}>
                            <div className="h-full bg-gray-400 transition-all duration-500" style={{ width: `${sentimentSummary.distribution.neutral}%` }}></div>
                        </div>
                    </div>
                    <div>
                        <div className="flex justify-between text-sm mb-1">
                            <span className="text-red-700 font-medium">Olumsuz</span>
                            <span className="text-red-700">{sentimentSummary.distribution.negative}%</span>
                        </div>
                        <div className="h-2 bg-gray-100 rounded-full overflow-hidden" role="progressbar" aria-label={`Olumsuz yorum oranı: %${sentimentSummary.distribution.negative}`} aria-valuenow={sentimentSummary.distribution.negative} aria-valuemin={0} aria-valuemax={100}>
                            <div className="h-full bg-red-500 transition-all duration-500" style={{ width: `${sentimentSummary.distribution.negative}%` }}></div>
                        </div>
                    </div>
                </div>

                <div className="pt-6 border-t border-gray-100 text-center">
                    <p className="text-sm text-gray-500 mb-1">Analiz edilen yorum</p>
                    <p className="text-2xl font-bold text-gray-900">{sentimentSummary.totalAnalyzed}</p>
                </div>
            </div>
        </div>
      </div>
    </div>
  );
}
