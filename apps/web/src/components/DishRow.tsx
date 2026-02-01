import React from "react";
import ScoreBadge from "./ScoreBadge";

type DishRowProps = {
  name: string;
  score: number;
  reviewCount: number;
  sentimentPositive?: number;
  description?: string;
  onClick?: () => void;
};

export default function DishRow({
  name,
  score,
  reviewCount,
  sentimentPositive,
  description,
  onClick,
}: DishRowProps) {
  return (
    <div
      className={
        "flex items-center gap-4 py-3 px-2 border-b border-slate-100 last:border-0 hover:bg-orange-50/50 transition-colors duration-150 " +
        (onClick ? "cursor-pointer" : "")
      }
      onClick={onClick}
      onKeyDown={onClick ? (e: React.KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } } : undefined}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <ScoreBadge score={score} size="sm" />
      <div className="flex-1 min-w-0">
        <div className="font-semibold text-slate-900 truncate">{name}</div>
        {description ? <div className="text-sm text-slate-500 truncate">{description}</div> : null}
      </div>
      <div className="text-right text-sm text-slate-500">
        <div>{reviewCount} yorum</div>
        {typeof sentimentPositive === "number" ? (
          <div className="text-xs text-slate-400">%{sentimentPositive} pozitif</div>
        ) : null}
      </div>
    </div>
  );
}
