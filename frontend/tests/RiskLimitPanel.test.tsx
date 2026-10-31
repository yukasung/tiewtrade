import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { RiskLimitPanel } from "../src/RiskLimitPanel";
import { riskJournal, riskScope, type RiskAttempt } from "../src/riskLimitJournal";
import { riskText as t, riskLimitI18n } from "../src/riskLimitMessages";
import { riskKey, type RiskReceipt, type RiskSnapshot } from "../src/riskLimits";

const key = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";
const stamp = "2026-10-26T00:00:00Z";
const base: RiskSnapshot = {
  mode: "PAPER",
  amount: "100.000000000000000001",
  currency: "USDT",
  revision: 1,
  wallet_id: "w",
  episode_id: "e",
  latched: false,
  stop_alert_due: false,
  pause_alert_due: false,
  loss: "15",
  reason: "READY",
  source_revision: 2,
  evaluated_at: stamp,
  snapshot_at: stamp,
};
const attempt: RiskAttempt = {
  version: 1,
  owner: "owner",
  mode: "PAPER",
  key,
  action: "INCREASE",
  payload: {
    expected_revision: 1,
    expected_wallet_id: "w",
    expected_episode_id: "e",
    amount: "200.000000000000000001",
  },
};
const receipt: RiskReceipt = {
  receipt_id: "r",
  mode: "PAPER",
  action: "INCREASE",
  idempotency_key: key,
  amount: "200.000000000000000001",
  expected_revision: 1,
  expected_wallet_id: "w",
  expected_episode_id: "e",
  state: "REQUEST_PENDING",
  applied_revision: null,
  failure_code: null,
  recorded_at: stamp,
};
const answer = (value: unknown, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(value), { status }));

let client: QueryClient;
function mount(
  custom?: (url: string, init?: RequestInit) => Promise<Response> | undefined,
  mode: "PAPER" | "LIVE" = "PAPER",
) {
  const fetcher = vi.fn((url: string, init?: RequestInit) => custom?.(url, init) ??
    (url.includes("requests")
      ? answer({ detail: "RISK_REQUEST_NOT_FOUND" }, 404)
      : answer(mode === "PAPER" ? base : {
          ...base,
          mode,
          wallet_id: null,
          episode_id: null,
          loss: null,
          reason: "RISK_SOURCE_UNAVAILABLE",
        })));
  vi.stubGlobal("fetch", fetcher);
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return {
    ...render(
      <StrictMode><QueryClientProvider client={client}>
        <RiskLimitPanel owner="owner" mode={mode}/>
      </QueryClientProvider></StrictMode>,
    ),
    fetcher,
  };
}

const amountInput = () => screen.getByLabelText<HTMLInputElement>(t("limit"));
const saveButton = () => screen.getByRole<HTMLButtonElement>("button", { name: t("save") });
const requestBody = (request: RequestInit) =>
  JSON.parse(request.body as string) as Record<string, unknown>;

afterEach(() => {
  cleanup();
  client?.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.sessionStorage.clear();
  void riskLimitI18n.changeLanguage("th");
});

it("renders only the short ready form and disables an unchanged value", async () => {
  mount(url => url.includes("requests") ? undefined : answer({
    ...base,
    current_allowance: "1.25",
    adjusted_realized: "-2",
    baseline_at: stamp,
  }));
  await screen.findByLabelText(t("limit"));
  expect(screen.queryByText(t("READY"))).toBeNull();
  expect(amountInput().value).toBe(base.amount);
  expect(saveButton().disabled).toBe(true);
  expect(screen.queryByText("1.25")).toBeNull();
  expect(screen.queryByText("-2")).toBeNull();
  expect(screen.queryByText("e")).toBeNull();
  expect(screen.queryByRole("button", { name: t("RESET") })).toBeNull();
});

it("sends SET and DECREASE directly with canonical exact amounts and no TOTP", async () => {
  vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(key);
  let snapshot: RiskSnapshot = {
    ...base,
    amount: null,
    revision: 0,
    reason: "RISK_LIMIT_UNSET",
  };
  const posts: Array<[string, RequestInit]> = [];
  const { unmount } = mount((url, init) => {
    if (init?.method === "POST") {
      posts.push([url, init]);
      return answer({ ...receipt, action: "SET", amount: "50", expected_revision: 0 }, 202);
    }
    if (!url.includes("requests")) return answer(snapshot);
  });
  await screen.findByLabelText(t("limit"));
  expect(screen.queryByText("ไม่บังคับ คุณตั้งเพดานภายหลังได้")).toBeNull();
  expect(amountInput().value).toBe("");
  const form = amountInput().closest("form");
  expect(form?.classList.contains("grid")).toBe(true);
  expect(form?.classList.contains("grid-cols-1")).toBe(true);
  expect(form?.classList.contains("sm:grid-cols-[minmax(0,1fr)_7rem]")).toBe(true);
  expect(saveButton().classList.contains("h-11")).toBe(true);
  expect(saveButton().classList.contains("w-full")).toBe(true);
  expect(screen.queryByText(t("RISK_LIMIT_UNSET"))).toBeNull();
  fireEvent.change(amountInput(), { target: { value: "050.000" } });
  fireEvent.click(saveButton());
  await screen.findByText(t("checkingPrevious"));
  expect(requestBody(posts[0]![1]).amount).toBe("50");
  expect((posts[0]![1].headers as Record<string, string>)["X-TiewTrade-TOTP"]).toBeUndefined();
  expect(posts[0]![0]).not.toContain("/increase");

  unmount();
  client.clear();
  riskJournal.clear(riskScope("owner", "PAPER"));
  snapshot = base;
  posts.length = 0;
  mount((url, init) => {
    if (init?.method === "POST") {
      posts.push([url, init]);
      return answer({ ...receipt, action: "DECREASE", amount: "50" }, 202);
    }
    if (!url.includes("requests")) return answer(snapshot);
  });
  await screen.findByLabelText(t("limit"));
  fireEvent.change(amountInput(), { target: { value: "50" } });
  fireEvent.click(saveButton());
  await screen.findByText(t("checkingPrevious"));
  expect(requestBody(posts[0]![1]).amount).toBe("50");
  expect((posts[0]![1].headers as Record<string, string>)["X-TiewTrade-TOTP"]).toBeUndefined();
});

it("saves a Paper increase directly without opening TOTP", async () => {
  vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(key);
  const { fetcher } = mount((url, init) => {
    if (init?.method !== "POST") return;
    expect(riskJournal.read(riskScope("owner", "PAPER"))).toEqual(attempt);
    return answer(receipt, 202);
  });
  await screen.findByLabelText(t("limit"));
  fireEvent.change(amountInput(), { target: { value: "200.000000000000000001" } });
  fireEvent.click(saveButton());
  await screen.findByText(t("checkingPrevious"));
  const posts = fetcher.mock.calls.filter(([, init]) => init?.method === "POST");
  expect(posts).toHaveLength(1);
  expect(posts[0]![0]).toContain("/increase");
  expect((posts[0]![1]!.headers as Record<string, string>)["X-TiewTrade-TOTP"]).toBeUndefined();
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.activeElement).toBe(screen.getByRole("region", { name: t("recovery") }));
});

it("keeps the fresh TOTP modal for a Live increase", async () => {
  const { fetcher } = mount((url, init) => init?.method === "POST"
    ? answer({ ...receipt, mode: "LIVE", expected_wallet_id: null, expected_episode_id: null }, 202)
    : undefined, "LIVE");
  await screen.findAllByText(t("RISK_SOURCE_UNAVAILABLE"));
  fireEvent.change(amountInput(), { target: { value: "200.000000000000000001" } });
  fireEvent.click(saveButton());
  const dialog = screen.getByRole("dialog");
  expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  fireEvent.change(within(dialog).getByLabelText(t("totp")), { target: { value: "654321" } });
  fireEvent.click(within(dialog).getByRole("button", { name: t("confirm") }));
  await waitFor(() => expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1));
  const posted = fetcher.mock.calls.find(([, init]) => init?.method === "POST")![1]!;
  expect((posted.headers as Record<string, string>)["X-TiewTrade-TOTP"]).toBe("654321");
  expect(posted.body).not.toContain("654321");
});

it("does not create an intent for invalid or unchanged input", async () => {
  const { fetcher } = mount();
  await screen.findByLabelText(t("limit"));
  for (const value of ["", "0", "-1", "1e2", "0.0000000000000000001", base.amount!]) {
    fireEvent.change(amountInput(), { target: { value } });
    expect(saveButton().disabled).toBe(true);
    fireEvent.submit(amountInput().closest("form")!);
  }
  expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  expect(riskJournal.read(riskScope("owner", "PAPER"))).toBeNull();
});

it("preserves a dirty draft across polling and requires the latest snapshot identity", async () => {
  let snapshot = base;
  mount(url => url.includes("requests") ? undefined : answer(snapshot));
  await screen.findByLabelText(t("limit"));
  fireEvent.change(amountInput(), { target: { value: "50" } });
  snapshot = { ...base, amount: "80", revision: 2 };
  act(() => {
    client.setQueryData([...riskKey("owner", "PAPER"), "snapshot"], snapshot);
  });
  expect(amountInput().value).toBe("50");
  expect(await screen.findByText(t("draftStale"))).toBeTruthy();
  expect(saveButton().disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: t("useLatest") }));
  await waitFor(() => expect(amountInput().value).toBe("80"));
  expect(saveButton().disabled).toBe(true);
});

it("keeps the form blocked after APPLIED until the matching snapshot revision arrives", async () => {
  vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(key);
  let authoritative = base;
  const applied: RiskReceipt = {
    ...receipt,
    action: "DECREASE",
    amount: "50",
    state: "APPLIED",
    applied_revision: 2,
  };
  mount((url, init) => {
    if (init?.method === "POST" || url.includes("/requests/")) return answer(applied);
    return answer(authoritative);
  });
  await screen.findByLabelText(t("limit"));
  fireEvent.change(amountInput(), { target: { value: "50" } });
  fireEvent.click(saveButton());
  await waitFor(() => expect(saveButton().disabled).toBe(true));

  authoritative = { ...base, amount: "50", revision: 2 };
  act(() => {
    client.setQueryData([...riskKey("owner", "PAPER"), "snapshot"], authoritative);
  });
  await waitFor(() => expect(amountInput().value).toBe("50"));
  await waitFor(() => expect(amountInput().disabled).toBe(false));
  await act(async () => { await Promise.resolve(); });
  fireEvent.change(amountInput(), { target: { value: "40" } });
  await waitFor(() => expect(amountInput().value).toBe("40"));
  await waitFor(() => expect(saveButton().disabled).toBe(false));
});

it("keeps the submitted draft when the engine rejects it", async () => {
  vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(key);
  const rejected: RiskReceipt = {
    ...receipt,
    action: "DECREASE",
    amount: "50",
    state: "REJECTED",
    failure_code: "RISK_INPUT_INVALID",
  };
  mount((url, init) => {
    if (init?.method === "POST" || url.includes("/requests/")) return answer(rejected);
    return answer(base);
  });
  await screen.findByLabelText(t("limit"));
  fireEvent.change(amountInput(), { target: { value: "50" } });
  fireEvent.click(saveButton());
  await screen.findByText(t("saveFailed"));
  expect(amountInput().value).toBe("50");
  expect(saveButton().disabled).toBe(false);
});

it("recovers authorization-only through Save without exposing protocol details", async () => {
  riskJournal.write(attempt);
  const { fetcher, unmount } = mount((url, init) =>
    url.includes("requests/by-key") ? answer({ ...receipt, state: "AUTHORIZATION_ONLY" })
      : init?.method === "POST" ? answer(receipt, 202) : undefined);
  expect((await screen.findByText(t("finishPrevious"))).classList.contains("sr-only")).toBe(true);
  expect(amountInput().value).toBe("amount" in attempt.payload ? attempt.payload.amount : "");
  expect(amountInput().disabled).toBe(true);
  expect(document.body.textContent).not.toContain("AUTHORIZATION_ONLY");
  expect(document.body.textContent).not.toContain(key);
  fireEvent.click(saveButton());
  await waitFor(() => expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1));
  const retried = fetcher.mock.calls.find(([, init]) => init?.method === "POST")![1]!;
  expect((retried.headers as Record<string, string>)["Idempotency-Key"]).toBe(key);
  expect((retried.headers as Record<string, string>)["X-TiewTrade-TOTP"]).toBeUndefined();

  unmount();
  client.clear();
});

it("clears a not-found local attempt only after its authoritative identity is stale", async () => {
  const stale: RiskAttempt = {
    ...attempt,
    payload: { ...attempt.payload, expected_revision: 0 },
  };
  riskJournal.write(stale);
  const uuid = vi.spyOn(globalThis.crypto, "randomUUID");
  const { fetcher } = mount((url) =>
    url.includes("requests/by-key")
      ? answer({ detail: "RISK_REQUEST_NOT_FOUND" }, 404)
      : undefined);
  await waitFor(() => expect(riskJournal.read(riskScope("owner", "PAPER"))).toBeNull());
  const input = await screen.findByLabelText<HTMLInputElement>(t("limit"));
  await waitFor(() => expect(input.disabled).toBe(false));
  expect(input.value).toBe(base.amount);
  expect(saveButton().disabled).toBe(true);
  expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  expect(uuid).not.toHaveBeenCalled();
});

it("clears a not-found local attempt when its exact amount is already authoritative", async () => {
  const fulfilled: RiskAttempt = {
    ...attempt,
    action: "DECREASE",
    payload: { ...attempt.payload, amount: "100.0000000000000000010" },
  };
  riskJournal.write(fulfilled);
  const uuid = vi.spyOn(globalThis.crypto, "randomUUID");
  const { fetcher } = mount((url) => url.includes("requests/by-key")
    ? answer({ detail: "RISK_REQUEST_NOT_FOUND" }, 404)
    : undefined);
  await waitFor(() => expect(riskJournal.read(riskScope("owner", "PAPER"))).toBeNull());
  const input = await screen.findByLabelText<HTMLInputElement>(t("limit"));
  await waitFor(() => expect(input.disabled).toBe(false));
  expect(input.value).toBe(base.amount);
  expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  expect(uuid).not.toHaveBeenCalled();
});

it("does not clear a not-found RESET attempt merely because the limit is unchanged", async () => {
  const reset: RiskAttempt = {
    ...attempt,
    action: "RESET",
    payload: {
      expected_revision: 1,
      expected_wallet_id: "w",
      expected_episode_id: "e",
    },
  };
  riskJournal.write(reset);
  mount((url) => url.includes("requests/by-key")
    ? answer({ detail: "RISK_REQUEST_NOT_FOUND" }, 404)
    : undefined);
  expect((await screen.findByText(t("finishPrevious"))).classList.contains("sr-only")).toBe(true);
  expect(riskJournal.read(riskScope("owner", "PAPER"))).toEqual(reset);
});

it("does not clear a stale local attempt for a non-not-found lookup error", async () => {
  const stale: RiskAttempt = {
    ...attempt,
    payload: { ...attempt.payload, expected_revision: 0 },
  };
  riskJournal.write(stale);
  mount((url) => url.includes("requests/by-key")
    ? answer({ detail: "RISK_REQUEST_FAILED" }, 503)
    : undefined);
  expect((await screen.findByText(t("finishPrevious"))).classList.contains("sr-only")).toBe(true);
  expect(riskJournal.read(riskScope("owner", "PAPER"))).toEqual(stale);
  expect(amountInput().disabled).toBe(true);
});

it("retries an unknown decrease through Save with the exact intent and key", async () => {
  const decrease: RiskAttempt = {
    ...attempt,
    action: "DECREASE",
    payload: { ...attempt.payload, amount: "50" },
  };
  riskJournal.write(decrease);
  const uuid = vi.spyOn(globalThis.crypto, "randomUUID");
  const { fetcher } = mount((url, init) =>
    init?.method === "POST" ? answer({ ...receipt, action: "DECREASE", amount: "50" }, 202)
      : url.includes("requests/by-key") ? answer({ detail: "RISK_REQUEST_NOT_FOUND" }, 404)
      : undefined);
  expect((await screen.findByText(t("finishPrevious"))).classList.contains("sr-only")).toBe(true);
  expect(amountInput().value).toBe("50");
  expect(amountInput().disabled).toBe(true);
  expect(saveButton().disabled).toBe(false);
  expect(document.body.textContent).not.toContain("UNKNOWN");
  expect(document.body.textContent).not.toContain(key);
  fireEvent.click(saveButton());
  await waitFor(() => expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1));
  const retried = fetcher.mock.calls.find(([, init]) => init?.method === "POST")![1]!;
  expect((retried.headers as Record<string, string>)["Idempotency-Key"]).toBe(key);
  expect(requestBody(retried)).toEqual(decrease.payload);
  expect(uuid).not.toHaveBeenCalled();
  expect(riskJournal.read(riskScope("owner", "PAPER"))).toEqual(decrease);
});

it("keeps a pending request compact and disables Save", async () => {
  riskJournal.write(attempt);
  mount(url => url.includes("requests/by-key") ? answer(receipt) : undefined);
  expect((await screen.findByText(t("checkingPrevious"))).classList.contains("sr-only")).toBe(true);
  const input = await screen.findByLabelText<HTMLInputElement>(t("limit"));
  expect(input.value).toBe("amount" in attempt.payload ? attempt.payload.amount : "");
  expect(input.disabled).toBe(true);
  expect(saveButton().disabled).toBe(true);
  expect(document.body.textContent).not.toContain("REQUEST_PENDING");
  expect(document.body.textContent).not.toContain(key);
});

it("retries an unknown Paper increase directly with the same key", async () => {
  riskJournal.write(attempt);
  const uuid = vi.spyOn(globalThis.crypto, "randomUUID");
  const { fetcher } = mount((url, init) =>
    init?.method === "POST" ? answer(receipt, 202)
      : url.includes("requests/by-key") ? answer({ detail: "RISK_REQUEST_NOT_FOUND" }, 404)
      : undefined);
  expect((await screen.findByText(t("finishPrevious"))).classList.contains("sr-only")).toBe(true);
  fireEvent.click(saveButton());
  await waitFor(() => expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1));
  const retried = fetcher.mock.calls.find(([, init]) => init?.method === "POST")![1]!;
  expect((retried.headers as Record<string, string>)["Idempotency-Key"]).toBe(key);
  expect((retried.headers as Record<string, string>)["X-TiewTrade-TOTP"]).toBeUndefined();
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(uuid).not.toHaveBeenCalled();
});

it("storage failure blocks a direct request", async () => {
  const { fetcher } = mount();
  await screen.findByLabelText(t("limit"));
  fireEvent.change(amountInput(), { target: { value: "50" } });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("storage denied"); });
  fireEvent.click(saveButton());
  await screen.findByText(t("storage"));
  expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
});

it("shows reset only when latched and returns keyboard focus", async () => {
  mount(url => url.includes("requests") ? undefined : answer({
    ...base,
    latched: true,
    reason: "RISK_LOSS_LIMIT_REACHED",
    stop_progress: "STOPPED",
    target_set_complete: true,
    pending_count: 0,
  }));
  const trigger = await screen.findByRole<HTMLButtonElement>("button", { name: t("RESET") });
  trigger.focus();
  fireEvent.click(trigger);
  expect(screen.getByText(t("resetWarning"))).toBeTruthy();
  expect(screen.queryByLabelText(t("totp"))).toBeNull();
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.activeElement).toBe(trigger);
});

it("shows per-order stop evidence only for a stop problem", async () => {
  mount(url => url.includes("/stops/")
    ? answer({
        stop_id: "s",
        mode: "PAPER",
        effects_revision: 10,
        snapshot_at: stamp,
        next_cursor: null,
        items: [{
          target_kind: "ORDER",
          target_id: "target",
          order_id: "order",
          state: "FAILED",
          attempt: 1,
          details: {},
          recorded_at: stamp,
        }],
      })
    : answer({
        ...base,
        latched: true,
        reason: "RISK_LOSS_LIMIT_REACHED",
        stop_id: "s",
        effects_revision: 10,
        target_count: 1,
        pending_count: 1,
        failed_count: 1,
        target_set_complete: true,
        stop_progress: "PROBLEMS",
      }));
  await screen.findByText("order");
  expect(screen.getByText(t("FAILED"))).toBeTruthy();
});

it("keeps Live scope separate from a Paper recovery attempt", async () => {
  riskJournal.write(attempt);
  const { fetcher } = mount(undefined, "LIVE");
  await screen.findAllByText(t("RISK_SOURCE_UNAVAILABLE"));
  expect(fetcher.mock.calls.every(([url]) => url.includes("/live/risk-limit"))).toBe(true);
  expect(document.body.textContent).not.toContain("UNKNOWN");
  expect(riskJournal.read(riskScope("owner", "PAPER"))).toEqual(attempt);
});

it("keeps an unset limit optional only for Paper", async () => {
  mount((url) => url.includes("requests") ? undefined : answer({
    ...base,
    mode: "LIVE",
    amount: null,
    wallet_id: null,
    episode_id: null,
    reason: "RISK_LIMIT_UNSET",
  }), "LIVE");
  expect((await screen.findAllByText(t("liveUnset"))).length).toBeGreaterThan(0);
  expect(screen.queryByText("Optional. You can set a loss limit later.")).toBeNull();
});
