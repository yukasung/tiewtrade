import { StrictMode, useEffect } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AuthPanel } from "../src/AuthPanel";
import { useQueryClient } from "@tanstack/react-query";
import { navigateAccountPage } from "../src/accountNavigation";
import type { MouseEvent } from "react";

const observed = vi.hoisted(() => ({ mounts: [] as string[], exits: [] as string[], clients: [] as unknown[] }));
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
vi.mock("../src/RealtimePricePanel", () => ({ RealtimePricePanel: () => <Panel name="prices" /> }));
beforeEach(() => {
  observed.mounts = []; observed.exits = []; observed.clients = [];
  window.history.replaceState(null, "", "/");
  vi.stubEnv("VITE_CHART_ENABLED", "1");
  vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(
    url.endsWith("auth/me") ? { user_id: "nav-owner", totp_enabled: false } : { csrf_token: "t" },
  )))));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); });
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
  for (const page of ["security", "api-keys", "trading-account", "prices", "chart"]) {
    await navigate(page);
    expect(screen.getAllByTestId(/^module-/)).toHaveLength(1);
    expect(screen.getByTestId(`module-${page}`)).toBeTruthy();
    expect(observed.clients.at(-1)).toBe(client);
    expect(screen.getByRole("link", { current: "page" }).getAttribute("href")).toBe(`/${page}`);
  }
  expect(observed.exits).toContain("prices");
  await navigate("account");
  expect(screen.queryByTestId(/^module-/)).toBeNull();
  expect(screen.getByTestId("log-out")).toBeTruthy();
  expect(screen.getByTestId("user-id").textContent).toBe("nav-owner");
});
it("preserves a direct link through authentication and handles a changed or unknown path", async () => {
  window.history.replaceState(null, "", "/security");
  render(<AuthPanel />);
  await screen.findByTestId("module-security");
  await navigate("prices");
  expect(screen.getByTestId("module-prices")).toBeTruthy();
  await navigate("unknown");
  expect(window.location.pathname).toBe("/chart");
  expect(screen.getByTestId("module-chart")).toBeTruthy();
});
it("keeps the disabled chart default without mounting modules or starting their requests", async () => {
  vi.stubEnv("VITE_CHART_ENABLED", "0");
  render(<AuthPanel />);
  await screen.findByText("กราฟยังไม่เปิดใช้งาน");
  expect(screen.queryByTestId(/^module-/)).toBeNull();
  expect(screen.queryByRole("link", { name: "กราฟแท่งเทียน" })).toBeNull();
  expect(observed.mounts).toEqual([]);
  await waitFor(() => expect(window.location.pathname).toBe("/chart"));
});

it("navigates a plain internal click without reloading and preserves modified clicks", async () => {
  render(<AuthPanel />);
  await screen.findByTestId("module-chart");
  // Chart DOM can appear before the navigation effect installs its popstate listener.
  await waitFor(() => expect(window.location.pathname).toBe("/chart"));
  const client = observed.clients.at(-1);
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
