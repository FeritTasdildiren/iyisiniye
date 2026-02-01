import React from "react";

type ScoreBadgeProps = {
  score: number;
  size: "sm" | "md" | "lg";
};

const sizeClasses: Record<ScoreBadgeProps["size"], string> = {
  sm: "h-6 w-6 text-xs",
  md: "h-8 w-8 text-sm",
  lg: "h-12 w-12 text-lg",
};

const getColorClass = (score: number) => {
  if (score >= 8) return "bg-green-600";
  if (score >= 5) return "bg-orange-500";
  return "bg-red-600";
};

export default function ScoreBadge({ score, size }: ScoreBadgeProps) {
  const colorClass = getColorClass(score);
  return (
    <div
      className={
        "rounded-full text-white font-mono font-bold tabular-nums flex items-center justify-center " +
        sizeClasses[size] +
        " " +
        colorClass
      }
      aria-label={`Puan: 10 üzerinden ${score}`}
    >
      {score}
    </div>
  );
}
