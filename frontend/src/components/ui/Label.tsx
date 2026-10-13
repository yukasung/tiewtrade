import type { LabelHTMLAttributes } from "react";
/** Adapted from TailAdmin Pro 2.4.0 components/form/Label.tsx; no alias helper needed. */
export function Label({
  className = "",
  ...props
}: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={`account-label mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-400 ${className}`}
      {...props}
    />
  );
}
