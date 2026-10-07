import { useEffect, useRef, useState, type ReactNode } from "react";
import { AccountHeader } from "./AccountHeader";
import { AccountSidebar } from "./AccountSidebar";
import { accountText as t } from "../accountMessages";
import "../styles/admin-theme.css";
/** Adapted from TailAdmin Pro 2.4.0 AppLayout/SidebarContext; children replace Outlet. */
export function AccountLayout({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const close = () => {
    setOpen(false);
    trigger.current?.focus();
  };
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
    <div className="app-theme account-layout">
      <AccountHeader
        open={open}
        trigger={trigger}
        toggle={() => setOpen(!open)}
      />
      <AccountSidebar open={open} close={close} />
      {open && (
        <button
          type="button"
          className="account-backdrop"
          aria-label={t("close")}
          onClick={close}
        />
      )}
      <div className="account-content">{children}</div>
    </div>
  );
}
