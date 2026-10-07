import type { LabelHTMLAttributes } from "react";
/** Adapted from TailAdmin Pro 2.4.0 components/form/Label.tsx; no alias helper needed. */
export function Label({
  className = "",
  ...props
}: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={`account-label block font-medium ${className}`}
      {...props}
    />
  );
}
