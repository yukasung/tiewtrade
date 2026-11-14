import { StrictMode, useEffect } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AuthPanel } from "../src/AuthPanel";
import { useQueryClient } from "@tanstack/react-query";
import { navigateAccountPage } from "../src/accountNavigation";
import type { MouseEvent } from "react";
import { accountI18n } from "../src/accountMessages";

const observed = vi.hoisted(() => ({ mounts: [] as string[], exits: [] as string[], clients: [] as unknown[] }));
let platformRole: string | null = null;
function Panel({ name }: { name: string }) {
  const client = useQueryClient();
  useEffect(() => {
    observed.mounts.push(name);
    observed.clients.push(client);
    return () => { observed.exits.push(name); };
  }, [name, client]);
  return <p data-testid={`module-${name}`}>{name}</p>;
}
vi.mock("../src/CandlestickChartPanel", () => ({ CandlestickChartPanel: () => <Panel name="chart" /> }));
vi.mock("../src/TotpPanel", () => ({ TotpPanel: () => <Panel name="security" /> }));
vi.mock("../src/ApiKeyPanel", () => ({ ApiKeyPanel: () => <Panel name="api-keys" /> }));
vi.mock("../src/TradingAccountPanel", () => ({ TradingAccountPanel: () => <Panel name="trading-account" /> }));
vi.mock("../src/PaperTradePage", () => ({ PaperTradePage: () => <Panel name="paper/trade"/> }));
vi.mock("../src/LiveTradePage", () => ({ LiveTradePage: () => <Panel name="live/trade"/> }));
vi.mock("../src/SupportedSymbolPanel", () => ({ SupportedSymbolPanel: () => <Panel name="supported-symbols" /> }));
beforeEach(() => {
  vi.stubGlobal("innerWidth", 1440);
  observed.mounts = []; observed.exits = []; observed.clients = [];
  platformRole = null;
  window.history.replaceState(null, "", "/");
  vi.stubEnv("VITE_CHART_ENABLED", "1");
  vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(
    url.endsWith("auth/me") ? { user_id: "nav-owner", totp_enabled: false, platform_role: platformRole } : { csrf_token: "t" },
  )))));
});
afterEach(async () => { cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); await accountI18n.changeLanguage("th"); });
async function navigate(page: string) {
  await act(async () => {
    window.history.replaceState(null, "", `/${page}`);
    window.dispatchEvent(new PopStateEvent("popstate"));
    await Promise.resolve();
  });
}
it("defaults to chart and mounts only the selected module without replacing the session", async () => {
  render(<StrictMode><AuthPanel /></StrictMode>);
  await screen.findByTestId("module-chart");
  await waitFor(() => expect(window.location.pathname).toBe("/chart"));
  expect(observed.mounts.every(name => name === "chart")).toBe(true);
  const client = observed.clients.at(-1);
  for (const page of ["security", "api-keys", "trading-account", "paper/trade", "live/trade", "chart"]) {
    await navigate(page);
    expect(screen.getAllByTestId(/^module-/)).toHaveLength(1);
    expect(screen.getByTestId(`module-${page}`)).toBeTruthy();
    expect(observed.clients.at(-1)).toBe(client);
    if (["security", "api-keys", "trading-account"].includes(page)) fireEvent.click(screen.getByRole("button", { name: "เมนูบัญชี" }));
    if (page === "paper/trade" || page === "live/trade") {
      fireEvent.click(screen.getByRole("button", { name: page === "paper/trade" ? "Paper" : "Live" }));
    }
    expect(screen.getByRole("link", { current: "page" }).getAttribute("href")).toBe(`/${page}`);
  }
  expect(observed.exits).toContain("live/trade");
  await navigate("account");
  expect(screen.queryByTestId(/^module-/)).toBeNull();
  expect(screen.getByTestId("log-out")).toBeTruthy();
  expect(screen.getByTestId("user-id").textContent).toBe("nav-owner");
});
it("preserves a direct link through authentication and handles a changed or unknown path", async () => {
  window.history.replaceState(null, "", "/security");
  render(<AuthPanel />);
  await screen.findByTestId("module-security");
  await navigate("api-keys");
  expect(screen.getByTestId("module-api-keys")).toBeTruthy();
  await navigate("unknown");
  expect(window.location.pathname).toBe("/chart");
  expect(screen.getByTestId("module-chart")).toBeTruthy();
});
it.each(["th", "en"])("redirects retired prices links and removes the menu in %s", async language => {
  await accountI18n.changeLanguage(language);
  const sockets = vi.fn();
  vi.stubGlobal("WebSocket", sockets);
  window.history.replaceState(null, "", "/prices?from=bookmark");
  render(<AuthPanel />);
  await screen.findByTestId("module-chart");
  await waitFor(() => expect(window.location.pathname).toBe("/chart"));
  expect(window.location.search).toBe("?from=bookmark");
  expect(screen.queryByRole("link", { name: /ราคาสด|Live prices/ })).toBeNull();
  expect(document.querySelector('a[href="/prices"]')).toBeNull();
  const client = observed.clients.at(-1);
  await navigate("api-keys");
  await navigate("prices");
  expect(window.location.pathname).toBe("/chart");
  expect(observed.clients.at(-1)).toBe(client);
  expect(observed.mounts).not.toContain("prices");
  expect(vi.mocked(fetch).mock.calls.some(([url]) => typeof url === "string" && url.includes("/market-data/prices"))).toBe(false);
  expect(sockets).not.toHaveBeenCalled();
});
it("keeps a retired prices bookmark behind authentication", async () => {
  window.history.replaceState(null, "", "/prices");
  vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(
    url.endsWith("auth/me") ? { detail: "AUTH_REQUIRED" } : { csrf_token: "t" },
  ), { status: url.endsWith("auth/me") ? 401 : 200 }))));
  render(<AuthPanel />);
  await screen.findByTestId("signed-out");
  expect(window.location.pathname).toBe("/prices");
  expect(observed.mounts).toEqual([]);
});
it("keeps the disabled chart default without mounting modules or starting their requests", async () => {
  vi.stubEnv("VITE_CHART_ENABLED", "0");
  window.history.replaceState(null, "", "/prices");
  render(<AuthPanel />);
  await screen.findByText("กราฟยังไม่เปิดใช้งาน");
  expect(screen.queryByTestId(/^module-/)).toBeNull();
  expect(screen.queryByRole("link", { name: "กราฟแท่งเทียน" })).toBeNull();
  expect(observed.mounts).toEqual([]);
  await waitFor(() => expect(window.location.pathname).toBe("/chart"));
});

it("shows catalog management only to a platform role and rejects a trader deep link", async () => {
  window.history.replaceState(null, "", "/supported-symbols");
  render(<AuthPanel />);
  await screen.findByTestId("module-chart");
  expect(screen.queryByRole("link", { name: "คู่เทรดที่รองรับ" })).toBeNull();
  cleanup();
  platformRole = "PLATFORM_ADMIN";
  window.history.replaceState(null, "", "/supported-symbols");
  render(<AuthPanel />);
  expect(await screen.findByTestId("module-supported-symbols")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "เมนูบัญชี" }));
  expect(screen.getByRole("link", { name: "คู่เทรดที่รองรับ", current: "page" })).toBeTruthy();
});

it("navigates a plain internal click without reloading and preserves modified clicks", async () => {
  render(<AuthPanel />);
  await screen.findByTestId("module-chart");
  // Chart DOM can appear before the navigation effect installs its popstate listener.
  await waitFor(() => expect(window.location.pathname).toBe("/chart"));
  const client = observed.clients.at(-1);
  fireEvent.click(screen.getByRole("button", { name: "เมนูบัญชี" }));
  const link = screen.getByRole<HTMLAnchorElement>("link", { name: "API key" });
  fireEvent.click(link);
  expect(window.location.pathname).toBe("/api-keys");
  expect(window.location.hash).toBe("");
  expect(await screen.findByTestId("module-api-keys")).toBeTruthy();
  expect(observed.clients.at(-1)).toBe(client);
  for (const modifier of ["ctrlKey", "metaKey", "shiftKey", "altKey"]) {
    const preventDefault = vi.fn();
    navigateAccountPage({ button: 0, currentTarget: link, [modifier]: true, preventDefault } as unknown as MouseEvent<HTMLAnchorElement>);
    expect(preventDefault).not.toHaveBeenCalled();
  }
});
it.each(["download", "new-tab", "external", "already-prevented", "middle-click"])("preserves native or prevented navigation (%s)", kind => {
  const link = document.createElement("a");
  link.href = kind === "external" ? "https://example.com/account" : "/account";
  if (kind === "download") link.setAttribute("download", "fixture");
  if (kind === "new-tab") link.target = "_blank";
  const preventDefault = vi.fn();
  const before = window.location.href;
  navigateAccountPage({
    button: kind === "middle-click" ? 1 : 0, currentTarget: link,
    defaultPrevented: kind === "already-prevented", preventDefault,
  } as unknown as MouseEvent<HTMLAnchorElement>);
  expect(preventDefault).not.toHaveBeenCalled();
  expect(window.location.href).toBe(before);
});
