import type { ReactNode } from "react";
import { authText as t } from "../authMessages";
import "../styles/admin-theme.css";

/** Adapted from TailAdmin Pro 2.4.0 AuthPageLayout; retains the existing auth flow. */
export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="app-theme auth-layout">
      <div className="auth-content">
        <div className="auth-form-container">
          <a className="auth-wordmark" href="/">
            TiewTrade
          </a>
          {children}
        </div>
      </div>
      <aside className="auth-brand" aria-label="TiewTrade">
        <div>
          <strong>TiewTrade</strong>
          <p>{t("brandHelp")}</p>
          <p className="auth-brand-caption">{t("noTrading")}</p>
        </div>
      </aside>
    </div>
  );
}
