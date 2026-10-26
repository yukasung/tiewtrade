import { Badge } from "../components/ui/Badge";
import type { RefObject } from "react";
import { Button } from "../components/ui/Button";
import { ThemeToggleButton } from "../components/common/ThemeToggleButton";
import { accountText as t } from "../accountMessages";
/** Adapted from TailAdmin Pro 2.4.0 layout/AppHeader.tsx. */
export function AccountHeader({
  mode,
  open,
  mobileOpen,
  toggle,
  trigger,
}: {
  mode?: "PAPER" | "LIVE" | undefined;
  open: boolean;
  mobileOpen: boolean;
  toggle: () => void;
  trigger: RefObject<HTMLButtonElement>;
}) {
  return (
    <header className="account-header">
      <Button
        ref={trigger}
        variant="outline"
        className="account-menu-trigger"
        aria-label={t("menu")}
        aria-expanded={open}
        aria-controls="account-navigation"
        onClick={toggle}
      >
        <span className={`sidebar-toggle-icon ${mobileOpen ? "is-close" : ""}`} aria-hidden="true" />
      </Button>
      <strong>TiewTrade</strong>
      {mode ? <Badge color={mode === "LIVE" ? "warning" : "primary"}>{mode}</Badge> : <span>{t("navigation")}</span>}
      <ThemeToggleButton />
    </header>
  );
}
