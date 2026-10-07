import { forwardRef, type InputHTMLAttributes } from "react";
/** Adapted from TailAdmin Pro 2.4.0 components/form/input/InputField.tsx. */
export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(function Input({ className = "", ...props }, ref) {
  return (
    <input
      ref={ref}
      className={`account-input rounded-lg ${className}`}
      {...props}
    />
  );
});
