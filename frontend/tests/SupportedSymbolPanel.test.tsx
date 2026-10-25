import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SupportedSymbolPanel } from "../src/SupportedSymbolPanel";
import { supportedSymbolI18n } from "../src/supportedSymbolMessages";

const catalog = {
  revision: 7,
  active_pairs: [["BTC", "USDT"]],
  mutations_enabled: true,
  entries: [{ base: "BTC", quote: "USDT", status: "ACTIVE", revision: 7,
    updated_at: "2026-10-24T00:00:00Z", cleanup: null }],
};

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><SupportedSymbolPanel /></QueryClientProvider>);
}

beforeEach(() => { document.cookie = "tiewtrade_csrf=csrf-value; path=/"; });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("shows truthful impact and sends a fresh TOTP removal with the current revision", async () => {
  const calls: Array<[string, RequestInit | undefined]> = [];
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    calls.push([url, init]);
    if (url.includes("/impact")) return Promise.resolve(response({ base: "BTC", quote: "USDT", bots: 2,
      open_entry_orders: 3, protective_orders: 1, reduce_risk_orders: 4, positions: 5,
      complete: false, snapshot_at: "2026-10-24T00:00:00Z" }));
    if (init?.method === "DELETE") return Promise.resolve(response({ command_id: globalThis.crypto.randomUUID(), action: "REMOVE",
      base: "BTC", quote: "USDT", state: "SUCCEEDED", revision: 8,
      created_at: "2026-10-24T00:00:00Z", completed_at: "2026-10-24T00:00:00Z" }));
    return Promise.resolve(response(catalog));
  }));
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "ถอนคู่" }));
  expect(await screen.findByText("ข้อมูลผลกระทบยังไม่ครบ ห้ามตีความว่าไม่มีรายการที่ได้รับผล")).toBeTruthy();
  expect(screen.getByText("3")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("รหัส TOTP ใหม่"), { target: { value: "123456" } });
  fireEvent.click(screen.getByRole("button", { name: "ยืนยันถอนคู่" }));
  await waitFor(() => expect(calls.some(([, init]) => init?.method === "DELETE")).toBe(true));
  const [, request] = calls.find(([, init]) => init?.method === "DELETE")!;
  expect((request?.headers as Record<string, string>)["X-TiewTrade-TOTP"]).toBe("123456");
  expect((request?.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
  expect(typeof request?.body).toBe("string");
  expect(JSON.parse(request?.body as string)).toMatchObject({ expected_revision: 7, reason_code: "ADMIN_RISK_REVIEW" });
});

it("renders partial cleanup and disables mutation while the protocol gate is closed", async () => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(response({ ...catalog, mutations_enabled: false,
    entries: [{ ...catalog.entries[0], status: "REMOVED", cleanup: { status: "PARTIAL", attempts: 1,
      bots_stopped: 0, commands_rejected: 1, orders_canceled: 2, orders_unresolved: 1,
      error_code: "DEPENDENCY_UNAVAILABLE", updated_at: "2026-10-24T00:00:00Z" } }] }))));
  mount();
  expect(await screen.findByText("PARTIAL (1 ค้าง)")).toBeTruthy();
  expect(screen.getByRole<HTMLButtonElement>("button", { name: "เพิ่มคู่เทรด" }).disabled).toBe(true);
  expect(screen.getByText("ระบบ mutation ยังไม่ผ่าน deployment protocol gate")).toBeTruthy();
});

it("renders the management workflow in English through the message catalog", async () => {
  await supportedSymbolI18n.changeLanguage("en");
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(response(catalog))));
  try {
    mount();
    expect(await screen.findByRole("heading", { name: "Supported symbols" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Remove pair" }));
    expect(await screen.findByRole("heading", { name: "Remove BTC/USDT" })).toBeTruthy();
    expect(screen.getByLabelText("Fresh TOTP code")).toBeTruthy();
  } finally {
    await supportedSymbolI18n.changeLanguage("th");
  }
});

it("refreshes asynchronous catalog transitions without a page reload", async () => {
  let reads = 0;
  vi.stubGlobal("fetch", vi.fn(() => {
    reads += 1;
    const status = reads === 1 ? "REQUESTED" : "ACTIVE";
    return Promise.resolve(response({
      ...catalog,
      entries: [{ ...catalog.entries[0], status }],
    }));
  }));
  mount();
  expect(await screen.findByText("REQUESTED")).toBeTruthy();
  expect(await screen.findByText("ACTIVE", {}, { timeout: 2_000 })).toBeTruthy();
  expect(reads).toBeGreaterThanOrEqual(2);
});
