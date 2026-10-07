import type { SelectHTMLAttributes } from "react";
/** Adapted from TailAdmin Pro 2.4.0 components/form/Select.tsx; native controlled semantics. */
export function Select({
  className = "",
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={`account-input rounded-lg ${className}`} {...props} />
  );
}
