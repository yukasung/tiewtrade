import { forwardRef, type ButtonHTMLAttributes } from "react";
/** Adapted from TailAdmin Pro 2.4.0 components/ui/button/Button.tsx. */
type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  size?: "sm" | "md";
  variant?: "primary" | "outline";
};

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonProps
>(function Button({ type = "button", size = "md", variant = "primary", className = "", disabled, ...props }, ref) {
  const sizeClasses = size === "sm" ? "px-4 py-3 text-sm" : "px-5 py-3.5 text-sm";
  const variantClasses = variant === "primary"
    ? "bg-brand-500 text-white shadow-theme-xs hover:bg-brand-600 disabled:bg-brand-300"
    : "bg-white text-gray-700 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-400 dark:ring-gray-700 dark:hover:bg-white/3 dark:hover:text-gray-300";
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled}
      className={`account-button inline-flex items-center justify-center gap-2 rounded-lg border-0 font-medium transition ${sizeClasses} ${variantClasses} ${disabled ? "cursor-not-allowed opacity-50" : ""} ${className}`}
      {...props}
    />
  );
});
