import { useId, useState, type ReactNode } from "react";

/** Adapted from references/admin-template/src/components/faqs/FaqOne.tsx. */
export function Disclosure({ title, children, defaultOpen = false, className = "" }: {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const contentId = useId();
  return <div className={`overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/3 ${className}`}>
    <button type="button" aria-expanded={open} aria-controls={contentId} onClick={() => setOpen(value => !value)}
      className={`flex w-full items-center justify-between border-0 px-4 py-3 text-start text-sm font-medium text-gray-800 dark:text-white/90 ${open ? "bg-gray-50 dark:bg-white/3" : "bg-transparent"}`}>
      <span>{title}</span>
      <svg aria-hidden="true" viewBox="0 0 20 20" fill="none"
        className={`size-5 shrink-0 text-gray-500 transition-transform duration-200 dark:text-gray-400 ${open ? "rotate-180" : ""}`}>
        <path d="M4.792 8.021 10 13.229l5.208-5.208" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    </button>
    {open && <div id={contentId} className="space-y-4 border-t border-gray-100 px-4 py-4 dark:border-gray-800">{children}</div>}
  </div>;
}
