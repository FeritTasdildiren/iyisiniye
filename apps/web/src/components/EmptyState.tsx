import React from "react";
import Button from "./Button";

type EmptyStateProps = {
  title: string;
  subtitle?: string;
  ctaText?: string;
  onCtaClick?: () => void;
};

export default function EmptyState({
  title,
  subtitle,
  ctaText,
  onCtaClick,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center text-center py-12 px-6" aria-live="polite">
      <div className="h-16 w-16 rounded-full bg-slate-100 flex items-center justify-center mb-4">
        <svg className="h-8 w-8 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z" />
        </svg>
      </div>
      <div className="text-lg font-semibold text-slate-900">{title}</div>
      {subtitle ? <div className="text-sm text-slate-500 mt-1">{subtitle}</div> : null}
      {ctaText ? (
        <div className="mt-4">
          <Button variant="primary" size="base" onClick={onCtaClick}>
            {ctaText}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
