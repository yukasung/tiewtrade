import { accountText as t } from "../accountMessages";
/** Adapted from TailAdmin Pro 2.4.0 layout/AppSidebar.tsx; real account anchors only. */
export function AccountSidebar({
  open,
  close,
}: {
  open: boolean;
  close: () => void;
}) {
  return (
    <nav
      id="account-navigation"
      className={`account-sidebar ${open ? "is-open" : ""}`}
      aria-label={t("navigation")}
    >
      <strong>TiewTrade</strong>
      <a href="#account-details" onClick={close}>
        {t("account")}
      </a>
      <a href="#api-key-heading" onClick={close}>
        {t("keys")}
      </a>
      <a href="#trading-account-heading" onClick={close}>
        {t("trading")}
      </a>
    </nav>
  );
}
