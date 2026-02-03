import React, { useState, useRef, useEffect } from 'react';

interface AutocompleteResult {
  restaurants: { name: string; slug: string }[];
  dishes: { name: string }[];
}

const API_BASE_URL = '/api/v1';

export default function HeroSearch() {
  const [query, setQuery] = useState('');
  const [location, setLocation] = useState('');
  const [suggestions, setSuggestions] = useState<AutocompleteResult | null>(null);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const debounceTimeout = useRef<NodeJS.Timeout | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const navigate = () => {
    const trimmed = query.trim();
    if (!trimmed) return;
    const params = new URLSearchParams({ q: trimmed });
    if (location.trim()) params.append('location', location.trim());
    window.location.href = `/search?${params.toString()}`;
  };

  const handleQueryChange = (e: React.ChangeEvent<HTMLInputElement>) => {
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
        } catch {
          // Autocomplete is non-critical; silently ignore
        }
      }, 300);
    } else {
      setShowSuggestions(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      navigate();
    }
  };

  const selectSuggestion = (text: string) => {
    setQuery(text);
    setShowSuggestions(false);
    const params = new URLSearchParams({ q: text });
    if (location.trim()) params.append('location', location.trim());
    window.location.href = `/search?${params.toString()}`;
  };

  return (
    <div className="max-w-3xl mx-auto relative" ref={wrapperRef}>
      <div className="bg-white p-2 rounded-2xl md:rounded-full shadow-lg border border-gray-100 flex flex-col md:flex-row gap-2">
        <div className="flex-1 px-4 py-2 flex items-center border-b md:border-b-0 md:border-r border-gray-100">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-gray-400 mr-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Yemek veya mekan ara..."
            aria-label="Yemek veya mekan ara"
            className="w-full bg-transparent focus:outline-none text-gray-700 placeholder-gray-400"
            value={query}
            onChange={handleQueryChange}
            onKeyDown={handleKeyDown}
          />
        </div>
        <div className="flex-1 px-4 py-2 flex items-center">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-gray-400 mr-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          <input
            type="text"
            placeholder="Konum (Semt, İlçe)"
            aria-label="Konum ara"
            className="w-full bg-transparent focus:outline-none text-gray-700 placeholder-gray-400"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            onKeyDown={handleKeyDown}
          />
        </div>
        <button
          onClick={navigate}
          className="bg-orange-600 text-white px-8 py-3 rounded-xl md:rounded-full font-medium hover:bg-orange-700 transition-all shadow-md hover:shadow-lg w-full md:w-auto"
        >
          En İyisini Bul
        </button>
      </div>

      {/* Autocomplete Dropdown */}
      {showSuggestions && suggestions && (suggestions.restaurants.length > 0 || suggestions.dishes.length > 0) && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-white rounded-xl shadow-xl border border-gray-100 overflow-hidden z-50">
          {suggestions.restaurants.length > 0 && (
            <div className="p-2">
              <div className="text-xs font-semibold text-gray-500 px-3 py-1 uppercase">Restoranlar</div>
              {suggestions.restaurants.slice(0, 5).map((r) => (
                <div
                  key={r.slug}
                  className="px-3 py-2 hover:bg-orange-50 cursor-pointer text-gray-800 rounded-lg"
                  onClick={() => selectSuggestion(r.name)}
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
                  className="px-3 py-2 hover:bg-orange-50 cursor-pointer text-gray-800 rounded-lg"
                  onClick={() => selectSuggestion(d.name)}
                >
                  {d.name}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
