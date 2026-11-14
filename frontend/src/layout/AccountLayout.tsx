import { useRef, type ReactNode } from "react";
import { AccountHeader } from "./AccountHeader";
import { accountText as t } from "../accountMessages";
import type { AccountPage } from "../accountNavigation";
import { PageBreadcrumb } from "./PageBreadcrumb";
import { ThemeProvider } from "../context/ThemeContext";
import "../styles/admin-theme.css";
import { KillSwitchBanner } from "../KillSwitchControls";
/** TailAdmin AppLayout adapted to the approved horizontal/fullscreen navigation. */
export function AccountLayout({ children, page = "chart", isPlatformAdmin = false, owner }: { children: ReactNode; page?: AccountPage; isPlatformAdmin?: boolean; owner?: string | undefined }) {
  const content = useRef<HTMLDivElement>(null);
  const isTradingWorkspace = page === "paper/trade" || page === "live/trade";
  return <ThemeProvider>
    <div className="app-theme account-layout min-h-screen">
      <div className="account-workspace">
        <AccountHeader page={page} isPlatformAdmin={isPlatformAdmin} owner={owner} content={content} />
        <div ref={content}>
          {owner && <KillSwitchBanner owner={owner} />}
          <div className={`account-content mx-auto p-4 md:p-6 ${page === "chart" ? "account-content-chart" : isTradingWorkspace ? "account-content-trade" : ""}`}>
            {page !== "chart" && !isTradingWorkspace && <PageBreadcrumb title={t(page === "api-keys" ? "keys" : page === "trading-account" ? "trading" : page)} />}
            {children}
          </div>
        </div>
      </div>
    </div>
  </ThemeProvider>;
}
