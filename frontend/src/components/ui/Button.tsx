import { forwardRef, type ButtonHTMLAttributes } from "react";
/** Adapted from TailAdmin Pro 2.4.0 components/ui/button/Button.tsx. */
export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement>
>(function Button({ type = "button", className = "", ...props }, ref) {
  return (
    <button
      ref={ref}
      type={type}
      className={`account-button inline-flex items-center justify-center gap-2 rounded-lg font-medium ${className}`}
      {...props}
    />
  );
});
