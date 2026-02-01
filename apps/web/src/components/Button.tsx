import React from "react";

type ButtonProps = {
  variant: "primary" | "secondary" | "ghost";
  size: "base" | "lg";
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
};

const variantClasses: Record<ButtonProps["variant"], string> = {
  primary: "bg-orange-600 text-white hover:bg-orange-700",
  secondary: "border-2 border-orange-600 text-orange-600 hover:bg-orange-50",
  ghost: "text-slate-600 hover:text-orange-600 hover:bg-slate-100",
};

const sizeClasses: Record<ButtonProps["size"], string> = {
  base: "h-10 px-4 rounded-md",
  lg: "h-12 px-6 rounded-lg",
};

export default function Button({
  variant,
  size,
  children,
  onClick,
  disabled = false,
  className = "",
}: ButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={
        "inline-flex items-center justify-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-400 focus-visible:ring-offset-2 transition " +
        variantClasses[variant] +
        " " +
        sizeClasses[size] +
        " " +
        (disabled ? "opacity-50 cursor-not-allowed" : "") +
        " " +
        className
      }
    >
      {children}
    </button>
  );
}
