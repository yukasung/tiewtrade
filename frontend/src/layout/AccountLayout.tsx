import { useEffect, useRef, useState, type ReactNode } from "react";
import { AccountHeader } from "./AccountHeader";
import { AccountSidebar } from "./AccountSidebar";
import { accountText as t } from "../accountMessages";
import type { AccountPage } from "../accountNavigation";
import { PageBreadcrumb } from "./PageBreadcrumb";
import { ThemeProvider } from "../context/ThemeContext";
import "../styles/admin-theme.css";
import { KillSwitchBanner } from "../KillSwitchControls";
/** Adapted from TailAdmin Pro 2.4.0 AppLayout/SidebarContext; children replace Outlet. */
export function AccountLayout({ children, page = "chart", isPlatformAdmin = false, owner }: { children: ReactNode; page?: AccountPage; isPlatformAdmin?: boolean; owner?: string | undefined }) {
  return <ThemeProvider><AccountLayoutContent page={page} isPlatformAdmin={isPlatformAdmin} owner={owner}>{children}</AccountLayoutContent></ThemeProvider>;
}
function AccountLayoutContent({ children, page, isPlatformAdmin, owner }: { children: ReactNode; page: AccountPage; isPlatformAdmin: boolean; owner?: string | undefined }) {
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [desktop, setDesktop] = useState(() => window.innerWidth >= 1280);
  const trigger = useRef<HTMLButtonElement>(null);
  const close = () => {
    setOpen(false);
    if (open) trigger.current?.focus();
  };
  useEffect(() => {
    const resize = () => { setDesktop(window.innerWidth >= 1280); setOpen(false); };
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);
  useEffect(() => {
    if (!open) return;
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
    };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [open]);
  const isTradingWorkspace = page === "paper/trade" || page === "live/trade";
  return (
    <div className={`app-theme account-layout min-h-screen xl:flex ${desktop && !expanded ? "sidebar-collapsed" : ""}`}>
      <AccountSidebar open={open} close={close} page={page} isPlatformAdmin={isPlatformAdmin} />
      {open && (
        <button
          type="button"
          className="account-backdrop"
          aria-label={t("close")}
          onClick={close}
        />
      )}
      <div className="account-workspace flex-1">
        <AccountHeader mode={page === "paper/trade" ? "PAPER" : page === "live/trade" ? "LIVE" : undefined} open={desktop ? expanded : open} mobileOpen={open} trigger={trigger} owner={owner}
          toggle={() => { if (desktop) setExpanded(value => !value); else setOpen(value => !value); }} />
        {owner && <KillSwitchBanner owner={owner} />}
        <div className={`account-content mx-auto p-4 md:p-6 ${page === "chart" ? "account-content-chart" : isTradingWorkspace ? "account-content-trade" : ""}`}>
          {page !== "chart" && !isTradingWorkspace && <PageBreadcrumb title={t(page === "api-keys" ? "keys" : page === "trading-account" ? "trading" : page)} />}
          {children}
        </div>
      </div>
    </div>
  );
}
