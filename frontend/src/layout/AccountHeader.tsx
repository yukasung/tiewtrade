import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { flushSync } from "react-dom";
import { Button } from "../components/ui/Button";
import { Dropdown } from "../components/ui/Dropdown";
import { ThemeToggleButton } from "../components/common/ThemeToggleButton";
import { KillSwitchControls } from "../KillSwitchControls";
import { accountText as t } from "../accountMessages";
import { navigateAccountPage, type AccountPage } from "../accountNavigation";
import { AccountNavigation } from "./AccountNavigation";

/** Adapted from TailAdmin example-header/header-six.tsx and header/UserDropdown.tsx.
 * Fullscreen compact navigation and the stable safety row follow the approved spec. */
export function AccountHeader({ page, isPlatformAdmin, owner, content }: {
  page: AccountPage;
  isPlatformAdmin: boolean;
  owner?: string | undefined;
  content: RefObject<HTMLDivElement>;
}) {
  const [desktop, setDesktop] = useState(() => window.matchMedia("(min-width: 1280px)").matches);
  const [menu, setMenu] = useState(false);
  const [account, setAccount] = useState(false);
  const modeId = useId();
  const modeText = page === "paper/trade" ? t("paperMode") : page === "live/trade" ? t("liveMode") : null;
  const header = useRef<HTMLElement>(null);
  const menuTrigger = useRef<HTMLButtonElement>(null);
  const accountTrigger = useRef<HTMLButtonElement>(null);
  const accountLink = useRef<HTMLAnchorElement>(null);
  const primary = useRef<HTMLDivElement>(null);
  const desktopActions = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const close = useCallback(() => { setMenu(false); setAccount(false); }, []);
  const closeAccount = useCallback(() => setAccount(false), []);

  useEffect(() => {
    const media = window.matchMedia("(min-width: 1280px)");
    const changed = () => {
      const active = document.activeElement;
      const hidden = media.matches
        ? active === menuTrigger.current || active === accountLink.current || panel.current?.contains(active)
        : desktopActions.current?.contains(active) || primary.current?.contains(active);
      // Restore the old panel's scroll lock before any safety dialog can open.
      flushSync(() => { close(); setDesktop(media.matches); });
      if (hidden) (media.matches ? accountTrigger.current : menuTrigger.current)?.focus();
    };
    media.addEventListener("change", changed);
    return () => media.removeEventListener("change", changed);
  }, [close]);
  useEffect(() => {
    close();
    window.addEventListener("popstate", close);
    return () => window.removeEventListener("popstate", close);
  }, [page, owner, close]);

  useLayoutEffect(() => {
    const element = header.current;
    if (!element) return;
    const workspace = element.parentElement;
    const property = "--navigation-header-height";
    const previous = workspace?.style.getPropertyValue(property);
    const measure = () => workspace?.style.setProperty(property, `${element.getBoundingClientRect().height}px`);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => {
      observer.disconnect();
      if (previous) workspace?.style.setProperty(property, previous);
      else workspace?.style.removeProperty(property);
    };
  }, []);

  useLayoutEffect(() => {
    if (!menu || desktop) return;
    const background = content.current;
    const previousInert = background?.inert;
    const previousHidden = background?.getAttribute("aria-hidden");
    const previousOverflow = document.body.style.overflow;
    if (background) { background.inert = true; background.setAttribute("aria-hidden", "true"); }
    document.body.style.overflow = "hidden";
    menuTrigger.current?.focus();
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); close(); menuTrigger.current?.focus(); return; }
      if (event.key !== "Tab") return;
      const controls = Array.from(header.current?.querySelectorAll<HTMLElement>("button:not([disabled]),a[href],[tabindex='0']") ?? [])
        .filter(element => element.getClientRects().length > 0 && !element.closest("[hidden]"));
      const first = controls[0];
      const last = controls.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener("keydown", keyboard);
    return () => {
      document.removeEventListener("keydown", keyboard);
      document.body.style.overflow = previousOverflow;
      if (background) {
        background.inert = previousInert ?? false;
        if (previousHidden === null || previousHidden === undefined) background.removeAttribute("aria-hidden");
        else background.setAttribute("aria-hidden", previousHidden);
      }
    };
  }, [menu, desktop, content, close]);

  return <header ref={header} className="account-header" role={menu && !desktop ? "dialog" : undefined}
    aria-modal={menu && !desktop ? true : undefined} aria-label={menu && !desktop ? t("menuTitle") : undefined}>
    <div className="account-brand"><strong>TiewTrade</strong></div>
    <div ref={primary} className="account-primary" hidden={!desktop}>
      {desktop && <AccountNavigation page={page} group="primary" isPlatformAdmin={isPlatformAdmin} onNavigate={close} />}
    </div>
    <div className="account-compact-actions" hidden={desktop}>
      <a ref={accountLink} className="account-icon-button" href="/account" aria-label={t("account")}
        onClick={event => { const prevented = event.defaultPrevented; navigateAccountPage(event); if (!prevented && event.defaultPrevented) close(); }}><span className="navigation-icon icon-account" aria-hidden="true" /></a>
      <Button ref={menuTrigger} variant="outline" className={`account-icon-button ${modeText ? "account-menu-mode-trigger" : ""}`} aria-label={t(menu ? "close" : "menu")} aria-describedby={modeText ? modeId : undefined}
        aria-expanded={menu} aria-controls="compact-navigation" onClick={() => { setMenu(value => !value); menuTrigger.current?.focus(); }}>
        <span className={`navigation-toggle-icon ${menu ? "is-close" : ""}`} aria-hidden="true" />
        {modeText && <span id={modeId} className="account-current-mode">{modeText}</span>}
      </Button>
    </div>
    <div ref={desktopActions} className="account-desktop-actions" hidden={!desktop}>
      {desktop && <ThemeToggleButton />}
      <div className="account-disclosure">
        <Button ref={accountTrigger} variant="outline" className="account-icon-button" aria-label={t("accountMenu")}
          aria-expanded={account} aria-controls="account-dropdown" onClick={() => setAccount(value => !value)}>
          <span className="navigation-icon icon-account" aria-hidden="true" />
        </Button>
        <Dropdown open={desktop && account} onClose={closeAccount} trigger={accountTrigger} id="account-dropdown">
          <AccountNavigation page={page} group="account" isPlatformAdmin={isPlatformAdmin} onNavigate={close} />
        </Dropdown>
      </div>
    </div>
    <div className="account-safety" onClickCapture={() => { if (menu || account) flushSync(close); }}>
      {owner && <KillSwitchControls owner={owner} navigationScope={page} />}
    </div>
    <div ref={panel} id="compact-navigation" className="account-navigation-panel" hidden={desktop || !menu}>
      {!desktop && menu && <>
        <AccountNavigation page={page} group="primary" isPlatformAdmin={isPlatformAdmin} onNavigate={close} />
        <AccountNavigation page={page} group="account" isPlatformAdmin={isPlatformAdmin} onNavigate={close} />
        <ThemeToggleButton />
      </>}
    </div>
  </header>;
}
