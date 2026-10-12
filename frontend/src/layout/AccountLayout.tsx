import { useEffect, useRef, useState, type ReactNode } from "react";
import { AccountHeader } from "./AccountHeader";
import { AccountSidebar } from "./AccountSidebar";
import { accountText as t } from "../accountMessages";
import type { AccountPage } from "../accountNavigation";
import { PageBreadcrumb } from "./PageBreadcrumb";
import { chartText } from "../chartMessages";
import "../styles/admin-theme.css";
/** Adapted from TailAdmin Pro 2.4.0 AppLayout/SidebarContext; children replace Outlet. */
export function AccountLayout({ children, page = "chart" }: { children: ReactNode; page?: AccountPage }) {
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
  return (
    <div className={`app-theme account-layout min-h-screen xl:flex ${desktop && !expanded ? "sidebar-collapsed" : ""}`}>
      <AccountSidebar open={open} close={close} page={page} />
      {open && (
        <button
          type="button"
          className="account-backdrop"
          aria-label={t("close")}
          onClick={close}
        />
      )}
      <div className="account-workspace flex-1">
        <AccountHeader open={desktop ? expanded : open} mobileOpen={open} trigger={trigger}
          toggle={() => { if (desktop) setExpanded(value => !value); else setOpen(value => !value); }} />
        <div className="account-content mx-auto p-4 md:p-6">
          <PageBreadcrumb title={page === "chart" ? chartText("heading") : t(page === "api-keys" ? "keys" : page === "trading-account" ? "trading" : page)} />
          {children}
        </div>
      </div>
    </div>
  );
}
