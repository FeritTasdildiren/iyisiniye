import React, { useState, useEffect, useRef } from 'react';
import ScoreBadge from './ScoreBadge';
import VenueCard from './VenueCard';
import FilterChip from './FilterChip';
import EmptyState from './EmptyState';
import Button from './Button';

// Types
interface SearchResult {
  id: string;
  name: string;
  slug: string;
  imageUrl?: string;
  cuisineType: string;
  priceRange: number;
  overallScore: number;
  district: string;
  topDishes: { name: string; score: number }[];
  reviewCount: number;
}

interface AutocompleteResult {
  restaurants: { name: string; slug: string }[];
  dishes: { name: string }[];
}

interface SearchIslandProps {
  initialQuery?: string;
}

const CUISINES = [
  'Kebap', 'Döner', 'Pide', 'Burger', 'Pizza', 'Sushi',
  'Makarna', 'Balık', 'Ev Yemekleri', 'Tatlı', 'Kahvaltı',
  'Steak', 'Vegan', 'Dünya Mutfağı'
];

const API_BASE_URL = typeof window !== 'undefined' ? '/api/v1' : 'http://localhost:3001/api/v1';

export default function SearchIsland({ initialQuery = '' }: SearchIslandProps) {
  // State
  const [query, setQuery] = useState(initialQuery);
  const [suggestions, setSuggestions] = useState<AutocompleteResult | null>(null);
  const [showSuggestions, setShowSuggestions] = useState(false);

  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);

  // Filters
  const [selectedCuisines, setSelectedCuisines] = useState<string[]>([]);
  const [priceRange, setPriceRange] = useState<number | null>(null); // 1-4
  const [minScore, setMinScore] = useState<number>(0);
  const [sortBy, setSortBy] = useState('score_desc');
  const [showFilters, setShowFilters] = useState(false);

  const debounceTimeout = useRef<NodeJS.Timeout | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Click outside to close suggestions
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Autocomplete
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);

    if (debounceTimeout.current) clearTimeout(debounceTimeout.current);

    if (val.length > 1) {
      debounceTimeout.current = setTimeout(async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/autocomplete?q=${encodeURIComponent(val)}`);
          if (res.ok) {
            const data = await res.json();
            setSuggestions(data);
            setShowSuggestions(true);
          }
        } catch (error) {
          console.error('Autocomplete error:', error);
        }
      }, 300);
    } else {
      setShowSuggestions(false);
    }
  };

  // Main Search
  const searchVenues = async (resetPage = false) => {
    setLoading(true);
    setShowSuggestions(false);

    const currentPage = resetPage ? 1 : page;
    if (resetPage) setPage(1);

    const params = new URLSearchParams();
    if (query) params.append('q', query);
    selectedCuisines.forEach(c => params.append('cuisine', c));
    if (priceRange) params.append('price_range', priceRange.toString());
    if (minScore > 0) params.append('min_score', minScore.toString());
    params.append('sort_by', sortBy);
    params.append('page', currentPage.toString());
    params.append('limit', '12');

    try {
      const res = await fetch(`${API_BASE_URL}/search?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setResults(data.results);
        setTotalCount(data.total);
      } else {
        setResults([]);
        setTotalCount(0);
      }
    } catch (error) {
      console.error('Search error:', error);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  // Trigger search on filter change or page change
  useEffect(() => {
    searchVenues();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, selectedCuisines, priceRange, minScore, sortBy]);

  // Trigger search on Enter key
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      searchVenues(true);
    }
  };

  return (
    <div className="w-full max-w-7xl mx-auto px-4 py-8 space-y-8">
      {/* Search Input Section */}
      <div className="relative z-20" ref={wrapperRef}>
        <div className="flex gap-2">
          <input
            type="text"
            className="w-full p-4 text-lg border-2 border-orange-200 rounded-xl focus:border-orange-600 focus:outline-none shadow-sm font-poppins"
            placeholder="Yemek veya mekan ara..."
            aria-label="Yemek veya mekan ara"
            value={query}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
          />
          <Button onClick={() => searchVenues(true)} variant="primary" size="base" className="px-8">
            Ara
          </Button>
        </div>

        {/* Autocomplete Dropdown */}
        {showSuggestions && suggestions && (
          <div className="absolute top-full left-0 right-0 mt-2 bg-white rounded-xl shadow-xl border border-gray-100 overflow-hidden">
            {suggestions.restaurants.length > 0 && (
              <div className="p-2">
                <div className="text-xs font-semibold text-gray-500 px-3 py-1 uppercase">Restoranlar</div>
                {suggestions.restaurants.slice(0, 5).map((r) => (
                  <div
                    key={r.slug}
                    className="px-3 py-2 hover:bg-orange-50 cursor-pointer text-gray-800"
                    onClick={() => {
                      setQuery(r.name);
                      searchVenues(true);
                    }}
                  >
                    {r.name}
                  </div>
                ))}
              </div>
            )}
            {suggestions.dishes.length > 0 && (
              <div className="p-2 border-t border-gray-100">
                <div className="text-xs font-semibold text-gray-500 px-3 py-1 uppercase">Yemekler</div>
                {suggestions.dishes.slice(0, 5).map((d, idx) => (
                  <div
                    key={idx}
                    className="px-3 py-2 hover:bg-orange-50 cursor-pointer text-gray-800"
                    onClick={() => {
                      setQuery(d.name);
                      searchVenues(true);
                    }}
                  >
                    {d.name}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex flex-col lg:flex-row gap-8 items-start">
        {/* Mobile Filter Toggle */}
        <button
          type="button"
          className="lg:hidden flex items-center gap-2 px-4 py-2 bg-orange-50 text-orange-700 border border-orange-200 rounded-lg font-medium text-sm hover:bg-orange-100 transition-colors focus:outline-none focus:ring-2 focus:ring-orange-400"
          onClick={() => setShowFilters(!showFilters)}
          aria-expanded={showFilters}
          aria-controls="filter-sidebar"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
          </svg>
          {showFilters ? 'Filtreleri Gizle' : 'Filtreler'}
        </button>

        {/* Sidebar Filters */}
        <aside
          id="filter-sidebar"
          className={`w-full lg:w-64 flex-shrink-0 space-y-6 bg-white p-6 rounded-xl border border-gray-100 shadow-sm ${showFilters ? 'block' : 'hidden'} lg:block`}
        >
          <div>
            <h3 className="font-semibold mb-3 font-poppins">Sıralama</h3>
            <select
              className="w-full p-2 border rounded-lg"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="score_desc">En Yüksek Puan</option>
              <option value="reviews_desc">En Çok Yorum</option>
              <option value="price_asc">Fiyat (Artan)</option>
              <option value="price_desc">Fiyat (Azalan)</option>
            </select>
          </div>

          <div>
            <h3 className="font-semibold mb-3 font-poppins">Fiyat Aralığı</h3>
            <div className="flex gap-2">
              {[1, 2, 3, 4].map((p) => (
                <button
                  key={p}
                  onClick={() => setPriceRange(priceRange === p ? null : p)}
                  className={`flex-1 py-1 rounded border ${priceRange === p ? 'bg-orange-600 text-white border-orange-600' : 'bg-white text-gray-600 border-gray-300'}`}
                >
                  {Array(p).fill('₺').join('')}
                </button>
              ))}
            </div>
          </div>

          <div>
            <h3 className="font-semibold mb-3 font-poppins">Minimum Puan</h3>
            <input
              type="range"
              min="0"
              max="10"
              step="0.5"
              value={minScore}
              onChange={(e) => setMinScore(parseFloat(e.target.value))}
              className="w-full accent-orange-600"
            />
            <div className="text-center mt-1 font-medium text-orange-600">{minScore > 0 ? minScore : 'Tümü'}</div>
          </div>

          <div>
            <h3 className="font-semibold mb-3 font-poppins">Mutfak</h3>
            <div className="flex flex-wrap gap-2">
              {CUISINES.map(c => (
                <FilterChip
                  key={c}
                  label={c}
                  selected={selectedCuisines.includes(c)}
                  onToggle={() => {
                    setSelectedCuisines(prev =>
                      prev.includes(c) ? prev.filter(i => i !== c) : [...prev, c]
                    );
                  }}
                />
              ))}
            </div>
          </div>
        </aside>

        {/* Results Area */}
        <div className="flex-1 w-full">
          {/* Header */}
          <div className="mb-4 text-gray-600">
            {loading ? (
              <span>Aranıyor...</span>
            ) : (
              <span><strong>{totalCount}</strong> sonuç bulundu</span>
            )}
          </div>

          {/* Grid */}
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[1, 2, 3, 4, 5, 6].map(i => (
                <div key={i} className="h-80 bg-gray-100 animate-pulse rounded-xl"></div>
              ))}
            </div>
          ) : results.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {results.map(venue => (
                <VenueCard key={venue.id} {...venue} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="Bu arama için sonuç bulamadık"
              subtitle="Farklı bir terimle tekrar deneyebilir veya filtreleri temizleyebilirsiniz."
            />
          )}

          {/* Pagination */}
          {results.length > 0 && (
            <div className="mt-10 flex justify-center gap-4">
              <Button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1 || loading}
                variant="secondary"
                size="base"
              >
                Önceki
              </Button>
              <span className="flex items-center px-4 font-semibold text-gray-700">Sayfa {page}</span>
              <Button
                onClick={() => setPage(p => p + 1)}
                disabled={results.length < 12 || loading}
                variant="secondary"
                size="base"
              >
                Sonraki
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
