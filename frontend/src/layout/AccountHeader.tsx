import type { RefObject } from "react";
import { Button } from "../components/ui/Button";
import { accountText as t } from "../accountMessages";
/** Adapted from TailAdmin Pro 2.4.0 layout/AppHeader.tsx. */
export function AccountHeader({
  open,
  toggle,
  trigger,
}: {
  open: boolean;
  toggle: () => void;
  trigger: RefObject<HTMLButtonElement>;
}) {
  return (
    <header className="account-header">
      <Button
        ref={trigger}
        className="account-menu-trigger"
        aria-label={t("menu")}
        aria-expanded={open}
        aria-controls="account-navigation"
        onClick={toggle}
      >
        ☰
      </Button>
      <strong>TiewTrade</strong>
      <span>{t("navigation")}</span>
    </header>
  );
}
