import { openStopSettings } from "./stopSettings";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AccountLayout } from "../src/layout/AccountLayout";
import { visibleAccountPages } from "../src/accountNavigation";
import { accountI18n } from "../src/accountMessages";
import { killSwitchText as t } from "../src/killSwitchMessages";
import { stopKey, type StopStatus } from "../src/killSwitch";

const clients: QueryClient[] = [];
const status = (mode: "PAPER" | "LIVE"): StopStatus => ({
  mode, active_causes: [], stop_id: null, cause: null, generation: null, revision: 0, summary_revision: 0,
  progress: null, target_set_complete: false, target_count: 0, pending_count: 0, failed_count: 0,
  platform_stop_id: null, platform_reason: null, resume_ready: false, reconciliation_revision: null,
  capability: mode === "PAPER" ? "AVAILABLE" : "LIVE_EXECUTION_UNAVAILABLE",
});
function shell() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } });
  clients.push(client);
  return render(<QueryClientProvider client={client}><AccountLayout owner="navigation-fixture" page="account"><label>Draft<input defaultValue="keep me" /></label></AccountLayout></QueryClientProvider>);
}
function resize(width: number) {
  act(() => { vi.stubGlobal("innerWidth", width); window.dispatchEvent(new Event("resize")); });
}
beforeEach(() => {
  vi.stubGlobal("innerWidth", 1440);
  vi.stubEnv("VITE_CHART_ENABLED", "1");
  window.history.replaceState(null, "", "/account");
});
afterEach(async () => {
  cleanup();
  clients.splice(0).forEach(client => client.clear());
  vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.unstubAllEnvs();
  window.localStorage.clear(); document.documentElement.classList.remove("dark");
  delete document.documentElement.dataset.colorScheme;
  await accountI18n.changeLanguage("th");
});
function stopFixture() {
  const fetcher = vi.fn((url: string, init?: RequestInit) => {
    const body = init?.method === "POST" ? { detail: "TRADING_STOP_UNAVAILABLE" }
      : url.includes("/csrf") ? { csrf_token: "fixture-csrf" }
      : url.includes("risk-limit") ? { latched: false }
      : status(url.includes("/live/") ? "LIVE" : "PAPER");
    return Promise.resolve(new Response(JSON.stringify(body), { status: init?.method === "POST" ? 503 : 200 }));
  });
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}
it.each([false, true])("filters shared navigation by chart flag and admin role (%s)", admin => {
  expect(visibleAccountPages("primary", false, admin)).toEqual(["paper/trade", "live/trade"]);
  expect(visibleAccountPages("primary", true, admin)).toEqual(["chart", "paper/trade", "live/trade"]);
  expect(visibleAccountPages("account", true, admin)).toEqual([
    "account", "security", "api-keys", "trading-account", ...(admin ? ["supported-symbols", "system-safety"] : []),
  ]);
});
it("closes account disclosure on outside pointer/focus without moving focus back", () => {
  stopFixture(); shell();
  const trigger = screen.getByRole("button", { name: "เมนูบัญชี" });
  fireEvent.click(trigger);
  const draft = screen.getByLabelText("Draft");
  fireEvent.pointerDown(draft); draft.focus();
  expect(trigger.getAttribute("aria-expanded")).toBe("false");
  expect(document.activeElement).toBe(draft);
  fireEvent.click(trigger);
  act(() => { trigger.focus(); draft.focus(); });
  expect(trigger.getAttribute("aria-expanded")).toBe("false");
});
it("restores existing background/scroll values on close, resize and unmount without clearing forms", () => {
  stopFixture(); resize(375);
  const view = shell();
  const draft = screen.getByLabelText<HTMLInputElement>("Draft");
  fireEvent.change(draft, { target: { value: "unsaved" } });
  const background = draft.closest(".account-content")?.parentElement;
  background?.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "clip";
  fireEvent.click(screen.getByRole("button", { name: "เปิดเมนูบัญชี" }));
  expect(background?.inert).toBe(true);
  expect(document.body.style.overflow).toBe("hidden");
  fireEvent.keyDown(document, { key: "Escape" });
  expect(background?.getAttribute("aria-hidden")).toBe("false");
  expect(document.body.style.overflow).toBe("clip");
  fireEvent.click(screen.getByRole("button", { name: "เปิดเมนูบัญชี" }));
  resize(1280);
  expect(background?.inert).toBe(false);
  expect(draft.value).toBe("unsaved");
  resize(1279);
  fireEvent.click(screen.getByRole("button", { name: "เปิดเมนูบัญชี" }));
  view.unmount();
  expect(document.body.style.overflow).toBe("clip");
  document.body.style.overflow = "";
});
for (const operation of ["accessor", "getItem", "setItem"] as const) {
  it.each(["SecurityError", "QuotaExceededError"])(`keeps real shell and STOP identity when theme storage ${operation} throws %s`, async name => {
    const fetcher = stopFixture();
    const storage = window.localStorage;
    const fail = () => { throw new DOMException("fixture storage unavailable", name); };
    if (operation === "accessor") vi.spyOn(window, "localStorage", "get").mockImplementation(fail);
    else vi.spyOn(Storage.prototype, operation).mockImplementation(fail);
    const event = vi.fn();
    window.addEventListener("tiewtrade-theme-change", event);
    try {
      shell();
      const stop = screen.getByRole("button", { name: t("paperStop"), hidden: true });
      expect(document.documentElement.dataset.colorScheme).toBe("light");
      fireEvent.click(screen.getByRole("button", { name: "เปลี่ยนเป็นโหมดมืด" }));
      expect(document.documentElement.dataset.colorScheme).toBe("dark");
      expect(document.documentElement.classList.contains("dark")).toBe(true);
      expect(event).toHaveBeenCalledTimes(2);
      openStopSettings();
      fireEvent.click(stop);
      openStopSettings();
      await screen.findByRole("button", { name: `${t("paperStop")} — ${t("retry")}` });
      const key = (fetcher.mock.calls.find(([, init]) => init?.method === "POST")?.[1]?.headers as Record<string, string>)["Idempotency-Key"];
      expect(key).toBeTruthy();
      fireEvent.click(screen.getByRole("button", { name: "Paper" }));
      fireEvent.click(screen.getByRole("button", { name: "Live" }));
      fireEvent.keyDown(screen.getByRole("link", { name: "Spot" }), { key: "Escape" });
      resize(1279);
      fireEvent.click(screen.getByRole("button", { name: "เปิดเมนูบัญชี" }));
      fireEvent.keyDown(document, { key: "Escape" });
      resize(1280);
      expect(screen.getByLabelText<HTMLInputElement>("Draft").value).toBe("keep me");
      expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
      openStopSettings();
      fireEvent.click(screen.getByRole("button", { name: `${t("paperStop")} — ${t("retry")}` }));
      await waitFor(() => expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(2));
      const keys = fetcher.mock.calls.filter(([, init]) => init?.method === "POST").map(([, init]) => (init?.headers as Record<string, string>)["Idempotency-Key"]);
      expect(keys).toEqual([key, key]);
      expect(storage.length).toBeLessThanOrEqual(2); // theme and STOP journal only when writes are available
    } finally { window.removeEventListener("tiewtrade-theme-change", event); }
  });
}
it.each([null, "invalid", "light", "dark"])("preserves theme preference semantics (%s)", value => {
  stopFixture();
  if (value !== null) window.localStorage.setItem("theme", value);
  shell();
  expect(document.documentElement.dataset.colorScheme).toBe(value === "dark" ? "dark" : "light");
});
it("moves focus from a hidden desktop dropdown link to the compact trigger", () => {
  stopFixture(); shell();
  fireEvent.click(screen.getByRole("button", { name: "เมนูบัญชี" }));
  act(() => screen.getByRole("link", { name: "API key" }).focus());
  resize(1279);
  expect(document.activeElement).toBe(screen.getByRole("button", { name: "เปิดเมนูบัญชี" }));
  expect(screen.queryByRole("link", { name: "API key" })).toBeNull();
});
it("closes navigation on a same-page click and popstate without sending STOP", () => {
  const fetcher = stopFixture(); shell();
  const trigger = screen.getByRole("button", { name: "เมนูบัญชี" });
  fireEvent.click(trigger);
  fireEvent.click(screen.getByRole("link", { name: "บัญชี", current: "page" }));
  expect(trigger.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(trigger);
  act(() => { window.dispatchEvent(new PopStateEvent("popstate")); });
  expect(trigger.getAttribute("aria-expanded")).toBe("false");
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
});

it("keeps STOP controls, both statuses and warnings inside Settings only", async () => {
  const fetcher = stopFixture();
  fetcher.mockImplementation((url: string) => Promise.resolve(new Response(JSON.stringify(url.includes("/paper/kill-switch")
    ? { ...status("PAPER"), stop_id: "known-stop", progress: "STOPPED" } : url.includes("risk-limit") ? { latched: false } : status("LIVE")))));
  shell();
  await screen.findByText(t("STOPPED"));
  expect(screen.getAllByRole("button", { name: t("settings") })).toHaveLength(1);
  expect(screen.queryByRole("button", { name: t("details") })).toBeNull();
  expect(screen.queryByRole("button", { name: t("paperStop") })).toBeNull();
  expect(screen.queryByRole("button", { name: t("liveStop") })).toBeNull();
  expect(screen.queryByRole("group", { name: t("modeStatus", { mode: "PAPER" }) })).toBeNull();
  expect(screen.queryByRole("group", { name: t("modeStatus", { mode: "LIVE" }) })).toBeNull();
  const trigger = openStopSettings();
  expect(screen.getByRole("group", { name: t("modeStatus", { mode: "PAPER" }) })).toBeTruthy();
  expect(screen.getByRole("group", { name: t("modeStatus", { mode: "LIVE" }) })).toBeTruthy();
  expect(within(screen.getByRole("region", { name: "PAPER" })).getByRole("button", { name: t("details") })).toBeTruthy();
  expect(screen.getByRole("button", { name: t("paperStop") })).toBeTruthy();
  expect(screen.getByRole("button", { name: t("liveStop") })).toBeTruthy();
  fireEvent.keyDown(document, { key: "Escape" });
  expect(trigger.getAttribute("aria-expanded")).toBe("false");
  expect(document.activeElement).toBe(trigger);
  expect(screen.queryByRole("button", { name: t("details") })).toBeNull();
  openStopSettings();
  act(() => { screen.getByLabelText("Draft").focus(); });
  expect(trigger.getAttribute("aria-expanded")).toBe("false");
  expect(document.activeElement).toBe(screen.getByLabelText("Draft"));
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
});
it("closes Settings on scope and breakpoint changes without replacing controls or drafts", () => {
  const fetcher = stopFixture(); const view = shell();
  const stop = screen.getByRole("button", { name: t("paperStop"), hidden: true });
  const draft = screen.getByLabelText<HTMLInputElement>("Draft");
  fireEvent.change(draft, { target: { value: "draft stays" } });
  const trigger = openStopSettings();
  resize(1279);
  expect(trigger.getAttribute("aria-expanded")).toBe("false");
  openStopSettings();
  view.rerender(<QueryClientProvider client={clients.at(-1)!}><AccountLayout owner="navigation-fixture" page="paper/trade"><label>Draft<input defaultValue="keep me" /></label></AccountLayout></QueryClientProvider>);
  expect(trigger.getAttribute("aria-expanded")).toBe("false");
  expect(screen.getByRole("button", { name: t("paperStop"), hidden: true })).toBe(stop);
  expect(draft.value).toBe("draft stays");
  openStopSettings();
  view.rerender(<QueryClientProvider client={clients.at(-1)!}><AccountLayout owner="navigation-other" page="paper/trade"><label>Draft<input defaultValue="keep me" /></label></AccountLayout></QueryClientProvider>);
  expect(trigger.getAttribute("aria-expanded")).toBe("false");
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
});

it("closes Settings after one STOP and reveals the retained unknown outcome on reopening", async () => {
  const fetcher = stopFixture(); shell();
  const trigger = openStopSettings();
  const stop = screen.getByRole<HTMLButtonElement>("button", { name: t("paperStop") });
  fireEvent.click(stop);
  await screen.findByText(t("requestFailed"));
  expect(trigger.getAttribute("aria-expanded")).toBe("false");
  expect(stop.disabled).toBe(true);
  expect(screen.queryByRole("button", { name: `${t("paperStop")} — ${t("retry")}` })).toBeNull();
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
  expect(screen.queryByRole("alert")).toBeNull();
  openStopSettings();
  expect(screen.getByRole("alert").textContent).toContain(t("requestFailed"));
});

it("shows the latest query state after Settings was closed without submitting commands", async () => {
  const fetcher = stopFixture(); shell();
  const client = clients.at(-1)!;
  await waitFor(() => expect(client.getQueryData(stopKey("navigation-fixture", "PAPER"))).toEqual(status("PAPER")));
  openStopSettings(); fireEvent.keyDown(document, { key: "Escape" });
  act(() => {
    client.setQueryData(stopKey("navigation-fixture", "PAPER"), { ...status("PAPER"), stop_id: "updated-stop", progress: "STOPPED" });
  });
  expect(screen.queryByRole("status")).toBeNull();
  openStopSettings();
  expect(within(screen.getByRole("region", { name: "PAPER" })).getByRole("status").textContent).toContain(t("STOPPED"));
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
});
