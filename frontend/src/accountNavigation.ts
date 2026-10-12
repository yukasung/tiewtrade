import { useEffect, useState, type MouseEvent } from "react";

export const accountPages = ["chart", "account", "security", "api-keys", "trading-account", "prices"] as const;
export type AccountPage = (typeof accountPages)[number];
function currentPage(): AccountPage {
  return accountPages.find(page => window.location.pathname === `/${page}`) ?? "chart";
}
/** Preserve native modified clicks, new tabs and downloads. */
export function navigateAccountPage(event: MouseEvent<HTMLAnchorElement>): void {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey ||
      event.currentTarget.hasAttribute("download") || (event.currentTarget.target && event.currentTarget.target !== "_self")) return;
  const url = new URL(event.currentTarget.href);
  if (url.origin !== window.location.origin || !accountPages.some(page => url.pathname === `/${page}`)) return;
  event.preventDefault();
  if (window.location.href !== url.href) window.history.pushState(null, "", url.href);
  window.dispatchEvent(new PopStateEvent("popstate"));
}
/** Mounted only after authentication; page changes preserve the session provider. */
export function useAccountPage(): AccountPage {
  const [page, setPage] = useState(currentPage);
  useEffect(() => {
    const changed = () => {
      const next = currentPage();
      if (window.location.pathname !== `/${next}`) window.history.replaceState(window.history.state, "", `/${next}${window.location.search}`);
      setPage(next);
    };
    changed();
    window.addEventListener("popstate", changed);
    return () => window.removeEventListener("popstate", changed);
  }, []);
  return page;
}
