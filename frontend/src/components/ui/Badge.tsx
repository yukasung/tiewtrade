import type { ReactNode } from "react";
/** Adapted from references/admin-template/src/components/ui/badge/Badge.tsx (light/md). */
const colors = {
  primary: "bg-brand-50 text-brand-500 dark:bg-brand-500/15 dark:text-brand-400",
  warning: "bg-warning-50 text-warning-600 dark:bg-warning-500/15 dark:text-orange-400",
  success: "bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500",
  error: "bg-error-50 text-error-600 dark:bg-error-500/15 dark:text-error-500",
  light: "bg-gray-100 text-gray-700 dark:bg-white/5 dark:text-white/80",
};
export function Badge({ children, color = "light" }: { children: ReactNode; color?: keyof typeof colors }) {
  return <span className={`inline-flex items-center px-2.5 py-0.5 justify-center gap-1 rounded-full font-medium text-sm ${colors[color]}`}>{children}</span>;
}
