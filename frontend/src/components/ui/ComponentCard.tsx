import type { HTMLAttributes, ReactNode } from "react";

/** Adapted from references/admin-template/src/components/common/ComponentCard.tsx. */
export function ComponentCard({ title, headingId, desc, children, className = "", ...props }: {
  title: string; headingId: string; desc?: string; children: ReactNode;
} & Omit<HTMLAttributes<HTMLElement>, "title">) {
  return <section {...props} aria-labelledby={headingId} className={`template-card rounded-2xl ${className}`}>
    <div className="template-card-header px-6 py-5">
      <h2 id={headingId} className="text-base font-medium">{title}</h2>
      {desc && <p className="mt-1 text-sm">{desc}</p>}
    </div>
    <div className="template-card-body p-4 sm:p-6"><div className="space-y-6">{children}</div></div>
  </section>;
}
