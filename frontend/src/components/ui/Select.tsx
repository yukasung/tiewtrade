import { forwardRef, type SelectHTMLAttributes } from "react";
/** Adapted from TailAdmin Pro 2.4.0 components/form/Select.tsx; native controlled semantics. */
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select({
  className = "",
  children,
  ...props
}, ref) {
  return (
    <div className="relative">
      <select
        ref={ref}
        className={`account-input h-11 w-full appearance-none rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 pe-11 text-sm text-gray-800 shadow-theme-xs focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-500 disabled:opacity-40 ${className}`}
        {...props}
      >
        {children}
      </select>
      <svg aria-hidden="true" className="pointer-events-none absolute inset-e-3 top-1/2 -translate-y-1/2 text-gray-700"
        width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M4.79175 8.02075L10.0001 13.2291L15.2084 8.02075" stroke="currentColor"
          strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    </div>
  );
});
