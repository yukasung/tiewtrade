import type { HTMLAttributes, ReactNode } from "react";

/** Adapted from references/admin-template/src/components/common/ComponentCard.tsx. */
export function ComponentCard({
  title,
  headingId,
  desc,
  headerAction,
  children,
  className = "",
  ...props
}: {
  title: string;
  headingId: string;
  desc?: string;
  headerAction?: ReactNode;
  children: ReactNode;
} & Omit<HTMLAttributes<HTMLElement>, "title">) {
  const heading = (
    <>
      <h2 id={headingId} className="text-base font-medium">
        {title}
      </h2>
      {desc && <p className="mt-1 text-sm">{desc}</p>}
    </>
  );

  return (
    <section
      {...props}
      aria-labelledby={headingId}
      className={`template-card rounded-2xl ${className}`}
    >
      <div
        className={`template-card-header px-6 py-5${headerAction ? " template-card-header-with-action" : ""}`}
      >
        {headerAction ? (
          <>
            <div>{heading}</div>
            {headerAction}
          </>
        ) : (
          heading
        )}
      </div>
      <div className="template-card-body p-4 sm:p-6">
        <div className="space-y-6">{children}</div>
      </div>
    </section>
  );
}
