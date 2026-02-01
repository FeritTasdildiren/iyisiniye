import React from "react";

type FilterChipProps = {
  label: string;
  selected: boolean;
  onToggle: () => void;
};

export default function FilterChip({ label, selected, onToggle }: FilterChipProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={selected}
      className={
        "inline-flex items-center gap-2 rounded-full h-8 px-3 text-sm border transition-colors duration-150 focus:ring-2 focus:ring-orange-400 focus:outline-none " +
        (selected
          ? "bg-orange-50 border-orange-600 text-orange-700 font-medium hover:bg-orange-100"
          : "bg-white border-slate-300 text-slate-700 hover:bg-orange-100")
      }
    >
      {selected ? (
        <svg
          className="h-4 w-4"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M16.704 5.29a1 1 0 010 1.42l-7.25 7.25a1 1 0 01-1.42 0l-3.25-3.25a1 1 0 111.42-1.42l2.54 2.54 6.54-6.54a1 1 0 011.42 0z"
            clipRule="evenodd"
          />
        </svg>
      ) : null}
      <span>{label}</span>
    </button>
  );
}
