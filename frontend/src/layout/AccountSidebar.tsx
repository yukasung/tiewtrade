import { accountText as t } from "../accountMessages";
import { chartText } from "../chartMessages";
import { accountPages, navigateAccountPage, type AccountPage } from "../accountNavigation";
/** Adapted from TailAdmin Pro 2.4.0 layout/AppSidebar.tsx. */
export function AccountSidebar({
  open,
  close,
  page,
  isPlatformAdmin = false,
}: {
  open: boolean;
  close: () => void;
  page: AccountPage;
  isPlatformAdmin?: boolean;
}) {
  return (
    <nav
      id="account-navigation"
      className={`account-sidebar ${open ? "is-open" : ""}`}
      aria-label={t("navigation")}
    >
      <strong className="sidebar-wordmark"><span className="sidebar-label">TiewTrade</span><span className="sidebar-monogram" aria-hidden="true">TT</span></strong>
      {accountPages.filter(item =>
        (item !== "chart" || import.meta.env.VITE_CHART_ENABLED === "1") &&
        (item !== "supported-symbols" || isPlatformAdmin)
      ).map(item => (
        <a key={item} href={`/${item}`} aria-current={page === item ? "page" : undefined} onClick={event => { navigateAccountPage(event); close(); }}>
          <span className={`sidebar-icon icon-${item}`} aria-hidden="true" />
          <span className="sidebar-label">{item === "chart" ? chartText("heading") : t(item === "api-keys" ? "keys" : item === "trading-account" ? "trading" : item)}</span>
        </a>
      ))}
    </nav>
  );
}
