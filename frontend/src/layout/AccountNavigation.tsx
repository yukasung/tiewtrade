import { useCallback, useEffect, useId, useRef, useState, type MouseEvent } from "react";
import { accountText as t } from "../accountMessages";
import { Button } from "../components/ui/Button";
import { Dropdown } from "../components/ui/Dropdown";
import { chartText } from "../chartMessages";
import { navigateAccountPage, visibleAccountPages, type AccountPage } from "../accountNavigation";

type TradingPage = "paper/trade" | "live/trade";

/** Disclosure pattern from TailAdmin ChatBoxHeader/UserDropdown, using the shared dropdown. */
function MarketMenu({ destination, active, open, onToggle, onClose, onNavigate }: {
  destination: TradingPage;
  active: boolean;
  open: boolean;
  onToggle: () => void;
  onClose: (destination: TradingPage) => void;
  onNavigate: (event: MouseEvent<HTMLAnchorElement>) => void;
}) {
  const trigger = useRef<HTMLButtonElement>(null);
  const id = useId();
  const close = useCallback(() => onClose(destination), [destination, onClose]);
  const label = t(destination === "paper/trade" ? "paperMode" : "liveMode");
  return <div className="account-market-menu" onKeyDown={event => {
    if (open && event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close();
      trigger.current?.focus();
    }
  }}>
    <Button ref={trigger} variant="outline" className="account-market-trigger"
      aria-expanded={open} aria-controls={id} aria-current={active ? "true" : undefined}
      data-active={active} data-market-page={destination} onClick={onToggle}>
      {label}
      <svg aria-hidden="true" width="16" height="16" viewBox="0 0 20 20" fill="none">
        <path d="M4.79175 8.02075L10.0001 13.2291L15.2084 8.02075" stroke="currentColor"
          strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    </Button>
    <Dropdown open={open} onClose={close} outsideEvent="click" trigger={trigger} id={id} className="account-market-dropdown">
      <a href={`/${destination}`} aria-current={active ? "page" : undefined} onClick={onNavigate}>{t("spot")}</a>
      <Button variant="outline" disabled aria-disabled="true" aria-label={t("futures")}
        aria-describedby={`${id}-unavailable`} title={t("futuresUnavailable")} className="account-nav-unavailable">
        {t("futures")}<span id={`${id}-unavailable`} className="account-market-unavailable">{t("futuresUnavailable")}</span>
      </Button>
    </Dropdown>
  </div>;
}

/** Shared links for the horizontal header, account disclosure and compact panel. */
export function AccountNavigation({ page, group, isPlatformAdmin, onNavigate }: {
  page: AccountPage;
  group: "primary" | "account";
  isPlatformAdmin: boolean;
  onNavigate: () => void;
}) {
  const [openMarket, setOpenMarket] = useState<TradingPage | null>(null);
  const closeMarket = useCallback(() => setOpenMarket(null), []);
  const closeMarketPage = useCallback((destination: TradingPage) => {
    setOpenMarket(current => current === destination ? null : current);
  }, []);
  useEffect(() => {
    closeMarket();
    window.addEventListener("popstate", closeMarket);
    return () => window.removeEventListener("popstate", closeMarket);
  }, [page, closeMarket]);
  const followLink = (event: MouseEvent<HTMLAnchorElement>) => {
    const prevented = event.defaultPrevented;
    navigateAccountPage(event);
    if (!prevented && event.defaultPrevented) {
      closeMarket();
      onNavigate();
    }
  };
  return <nav className={`account-nav account-nav-${group}`} aria-label={t(group === "primary" ? "primaryNavigation" : "navigation")}>
    {visibleAccountPages(group, import.meta.env.VITE_CHART_ENABLED === "1", isPlatformAdmin).map(item => {
      if (item === "paper/trade" || item === "live/trade") {
        return <MarketMenu key={item} destination={item} active={page === item} open={openMarket === item}
          onToggle={() => setOpenMarket(current => current === item ? null : item)} onClose={closeMarketPage} onNavigate={followLink}/>;
      }
      return <a key={item} href={`/${item}`} aria-current={page === item ? "page" : undefined} onClick={followLink}>
        <span className={`navigation-icon icon-${item}`} aria-hidden="true"/>
        {item === "chart" ? chartText("heading") : t(item === "api-keys" ? "keys" : item === "trading-account" ? "trading" : item)}
      </a>;
    })}
  </nav>;
}
