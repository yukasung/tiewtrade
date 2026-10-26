import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { AccountSession } from "../src/AccountSession";
import { PaperWalletPanel } from "../src/PaperWalletPanel";
import { paperWalletText as t } from "../src/paperWalletMessages";

const identity = { user_id: "paper-user", totp_enabled: false };

function answer(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function mount(handler: (url: string, init?: RequestInit) => Promise<Response>) {
  document.cookie = "tiewtrade_csrf=paper-csrf";
  const fetcher = vi.fn(handler);
  vi.stubGlobal("fetch", fetcher);
  render(
    <AccountSession identity={identity}>
      <PaperWalletPanel identity={identity} />
    </AccountSession>,
  );
  return fetcher;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it("shows a recoverable error when the first wallet read fails", async () => {
  mount(() => Promise.reject(new Error("RAW-NETWORK-DETAIL")));

  expect((await screen.findByRole("alert")).textContent).toBe(t("loadError"));
  expect(document.body.textContent).not.toContain("RAW-NETWORK-DETAIL");
  expect(screen.getByRole("button", { name: t("refresh") })).toBeTruthy();
});

it("renders exact server amounts and keeps reset fail-closed", async () => {
  mount(() => Promise.resolve(answer({
    wallet: {
      mode: "PAPER",
      wallet_id: "wallet-one",
      episode_id: "episode-one",
      sequence: 1,
      initial_capital: { amount: "1000.000000000000000001", currency: "USDT" },
      balance: { amount: "1000.000000000000000009", currency: "USDT" },
      started_at: "2026-10-15T00:00:00Z",
      snapshot_at: "2026-10-15T00:00:01Z",
      revision: 1,
      reset_available: false,
      reset_reason: "ACTIVITY_UNKNOWN",
    },
  })));
  await screen.findByText("1,000.000000000000000009 USDT");
  expect(screen.getByText("1,000.000000000000000001 USDT")).toBeTruthy();
  expect(screen.getByRole<HTMLButtonElement>("button", { name: t("reset") }).disabled).toBe(true);
  expect(screen.getByText(t("resetUnavailable"))).toBeTruthy();
});

it("confirms reset and retries the exact episode request with the same key", async () => {
  const key = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";
  vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(key);
  let posts = 0;
  let resetDone = false;
  const fetcher = mount((url, init) => {
    if (url.endsWith("/reset") && init?.method === "POST") {
      posts += 1;
      if (posts === 1) return Promise.reject(new Error("uncertain"));
      return Promise.resolve(answer({
        command_id: "reset-command",
        state: "PENDING",
        failure_code: null,
        snapshot: null,
        status_url: "/paper-wallet/commands/reset-command",
      }, 202));
    }
    if (url.includes("/commands/reset-command")) {
      resetDone = true;
      return Promise.resolve(answer({
        command_id: "reset-command",
        state: "SUCCEEDED",
        failure_code: null,
        snapshot: null,
        status_url: "/paper-wallet/commands/reset-command",
      }));
    }
    return Promise.resolve(answer({
      wallet: {
        mode: "PAPER",
        wallet_id: "wallet-one",
        episode_id: resetDone ? "episode-two" : "episode-one",
        sequence: resetDone ? 2 : 1,
        initial_capital: { amount: resetDone ? "2500.125" : "1500", currency: "USDT" },
        balance: { amount: resetDone ? "2500.125" : "1500", currency: "USDT" },
        started_at: "2026-10-18T00:00:00Z",
        snapshot_at: "2026-10-18T00:00:01Z",
        revision: resetDone ? 4 : 2,
        reset_available: true,
        reset_reason: null,
      },
    }));
  });

  fireEvent.click(await screen.findByRole("button", { name: t("reset") }));
  expect(screen.getByRole("dialog", { name: t("resetTitle") })).toBeTruthy();
  expect(screen.getByText(t("resetDescription", { episode: 1 }))).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: t("resetCancel") }));
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);

  fireEvent.click(screen.getByRole("button", { name: t("reset") }));
  fireEvent.change(screen.getByLabelText(t("resetCapital")), {
    target: { value: "2500.125" },
  });
  fireEvent.click(screen.getByRole("button", { name: t("resetConfirm") }));
  fireEvent.click(await screen.findByRole("button", { name: t("retry") }));
  expect(await screen.findAllByText("2,500.125 USDT")).toHaveLength(2);

  const requests = fetcher.mock.calls.filter(([, init]) => init?.method === "POST");
  expect(requests).toHaveLength(2);
  for (const [url, init] of requests) {
    expect(url).toContain("/paper-wallet/reset");
    expect(init?.headers).toMatchObject({ "Idempotency-Key": key });
    expect(init?.body).toBe(JSON.stringify({
      initial_capital: "2500.125",
      expected_episode_id: "episode-one",
    }));
  }
});

it.each([false, true])("keeps reset bound to the confirmed episode across refetch (changed=%s)", async changed => {
  let reads = 0;
  const fetcher = mount(() => {
    reads += 1;
    const newEpisode = changed && reads > 1;
    return Promise.resolve(answer({ wallet: {
      mode: "PAPER",
      wallet_id: "wallet-one",
      episode_id: newEpisode ? "episode-two" : "episode-one",
      sequence: newEpisode ? 2 : 1,
      initial_capital: { amount: "1500", currency: "USDT" },
      balance: { amount: "1500", currency: "USDT" },
      started_at: "2026-10-18T00:00:00Z",
      snapshot_at: "2026-10-18T00:00:01Z",
      revision: reads,
      reset_available: true,
      reset_reason: null,
    } }));
  });
  fireEvent.click(await screen.findByRole("button", { name: t("reset") }));
  fireEvent.change(screen.getByLabelText(t("resetCapital")), { target: { value: "2500" } });
  fireEvent.click(screen.getByRole("button", { name: t("refresh") }));
  await waitFor(() => expect(reads).toBe(2));
  await waitFor(() => expect(screen.getByRole<HTMLButtonElement>("button", { name: t("refresh") }).disabled).toBe(false));
  if (changed) {
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect((await screen.findByRole("alert")).textContent).toBe(t("resetConflict"));
    fireEvent.click(screen.getByRole("button", { name: t("reset") }));
    expect(screen.getByText(t("resetDescription", { episode: 2 }))).toBeTruthy();
  } else {
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByText(t("resetDescription", { episode: 1 }))).toBeTruthy();
  }
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
});

it("closes reset with Escape and refetches after an episode conflict", async () => {
  vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(
    "ffffffff-ffff-4fff-8fff-ffffffffffff",
  );
  let walletReads = 0;
  let posts = 0;
  mount((url, init) => {
    if (url.endsWith("/reset") && init?.method === "POST") {
      posts += 1;
      return Promise.resolve(answer({
        command_id: "conflicted-reset",
        state: "PENDING",
        failure_code: null,
        snapshot: null,
        status_url: "/paper-wallet/commands/conflicted-reset",
      }, 202));
    }
    if (url.includes("/commands/conflicted-reset")) return Promise.resolve(answer({
      command_id: "conflicted-reset",
      state: "REJECTED",
      failure_code: "EPISODE_CONFLICT",
      snapshot: null,
      status_url: "/paper-wallet/commands/conflicted-reset",
    }));
    walletReads += 1;
    return Promise.resolve(answer({ wallet: {
      mode: "PAPER",
      wallet_id: "wallet-one",
      episode_id: walletReads > 1 ? "episode-two" : "episode-one",
      sequence: walletReads > 1 ? 2 : 1,
      initial_capital: { amount: "1500", currency: "USDT" },
      balance: { amount: "1500", currency: "USDT" },
      started_at: "2026-10-18T00:00:00Z",
      snapshot_at: "2026-10-18T00:00:01Z",
      revision: walletReads > 1 ? 3 : 2,
      reset_available: true,
      reset_reason: null,
    } }));
  });

  const reset = await screen.findByRole("button", { name: t("reset") });
  reset.focus();
  fireEvent.click(reset);
  const resetCapital = screen.getByLabelText(t("resetCapital"));
  expect(document.activeElement).toBe(resetCapital);
  fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
  expect(document.activeElement).toBe(
    screen.getByRole("button", { name: t("resetCancel") }),
  );
  fireEvent.keyDown(document, { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  await waitFor(() => expect(document.activeElement).toBe(reset));

  fireEvent.click(reset);
  fireEvent.change(screen.getByLabelText(t("resetCapital")), { target: { value: "2500" } });
  fireEvent.click(screen.getByRole("button", { name: t("resetConfirm") }));
  expect((await screen.findByRole("alert")).textContent).toBe(t("resetConflict"));
  await waitFor(() => expect(screen.getByText("2")).toBeTruthy());
  expect(posts).toBe(1);
});

it("retries an uncertain create with the same key and exact payload", async () => {
  const key = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(key);
  let posts = 0;
  let walletReady = false;
  const fetcher = mount((url, init) => {
    if (init?.method === "POST") {
      posts += 1;
      if (posts === 1) return Promise.reject(new Error("RAW-NETWORK-DETAIL"));
      return Promise.resolve(answer({
        command_id: "command-one",
        state: "PENDING",
        failure_code: null,
        status_url: "/paper-wallet/commands/command-one",
      }, 202));
    }
    if (url.includes("/commands/")) {
      walletReady = true;
      return Promise.resolve(answer({
        command_id: "command-one",
        state: "SUCCEEDED",
        failure_code: null,
        status_url: "/paper-wallet/commands/command-one",
      }));
    }
    return Promise.resolve(answer({ wallet: walletReady ? {
      mode: "PAPER",
      wallet_id: "wallet-one",
      episode_id: "episode-one",
      sequence: 1,
      initial_capital: { amount: "1234.567890123456789012", currency: "USDT" },
      balance: { amount: "1234.567890123456789012", currency: "USDT" },
      started_at: "2026-10-15T00:00:00Z",
      snapshot_at: "2026-10-15T00:00:01Z",
      revision: 1,
      reset_available: false,
      reset_reason: "ACTIVITY_UNKNOWN",
    } : null }));
  });

  await screen.findByLabelText(t("initialCapital"));
  fireEvent.change(screen.getByLabelText(t("initialCapital")), {
    target: { value: "1234.567890123456789012" },
  });
  fireEvent.click(screen.getByRole("button", { name: t("create") }));
  await screen.findByRole("button", { name: t("retry") });
  expect(document.body.textContent).not.toContain("RAW-NETWORK-DETAIL");
  fireEvent.click(screen.getByRole("button", { name: t("retry") }));
  expect(await screen.findAllByText("1,234.567890123456789012 USDT")).toHaveLength(2);

  const requests = fetcher.mock.calls.filter(([, init]) => init?.method === "POST");
  expect(requests).toHaveLength(2);
  for (const [, init] of requests) {
    expect(init?.headers).toMatchObject({
      "Idempotency-Key": key,
      "X-CSRF-Token": "paper-csrf",
    });
    expect(init?.body).toBe(JSON.stringify({ initial_capital: "1234.567890123456789012" }));
  }
  await waitFor(() => expect(posts).toBe(2));
});

it("keeps the same request after an uncertain server response", async () => {
  const key = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
  vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(key);
  let posts = 0;
  const fetcher = mount((url, init) => {
    if (init?.method === "POST") {
      posts += 1;
      if (posts === 1) return Promise.resolve(answer({ detail: "hidden" }, 503));
      return Promise.resolve(answer({
        command_id: "command-server-error",
        state: "PENDING",
        failure_code: null,
        status_url: "/paper-wallet/commands/command-server-error",
      }, 202));
    }
    if (url.includes("/commands/")) return Promise.resolve(answer({
      command_id: "command-server-error",
      state: "SUCCEEDED",
      failure_code: null,
      status_url: "/paper-wallet/commands/command-server-error",
    }));
    return Promise.resolve(answer({ wallet: null }));
  });

  const input = await screen.findByLabelText<HTMLInputElement>(t("initialCapital"));
  fireEvent.change(input, { target: { value: "1700" } });
  fireEvent.click(screen.getByRole("button", { name: t("create") }));
  await screen.findByRole("button", { name: t("retry") });
  expect(input.disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: t("retry") }));
  await waitFor(() => expect(posts).toBe(2));
  const requests = fetcher.mock.calls.filter(([, init]) => init?.method === "POST");
  expect(requests[0]?.[1]?.headers).toMatchObject({ "Idempotency-Key": key });
  expect(requests[1]?.[1]?.headers).toMatchObject({ "Idempotency-Key": key });
});

it("continues a command-status read after a temporary failure", async () => {
  vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(
    "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
  );
  let statusReads = 0;
  mount((url, init) => {
    if (init?.method === "POST") return Promise.resolve(answer({
      command_id: "command-status-retry",
      state: "PENDING",
      failure_code: null,
      status_url: "/paper-wallet/commands/command-status-retry",
    }, 202));
    if (url.includes("/commands/")) {
      statusReads += 1;
      if (statusReads === 1) return Promise.resolve(answer({ detail: "temporary" }, 503));
      return Promise.resolve(answer({
        command_id: "command-status-retry",
        state: "SUCCEEDED",
        failure_code: null,
        status_url: "/paper-wallet/commands/command-status-retry",
      }));
    }
    return Promise.resolve(answer({ wallet: null }));
  });

  const input = await screen.findByLabelText<HTMLInputElement>(t("initialCapital"));
  fireEvent.change(input, { target: { value: "1800" } });
  fireEvent.click(screen.getByRole("button", { name: t("create") }));
  const retry = await screen.findByRole("button", { name: t("retry") });
  expect(input.disabled).toBe(true);
  fireEvent.click(retry);
  await waitFor(() => expect(statusReads).toBe(2));
  await waitFor(() => expect(input.disabled).toBe(false));
});

it("drops an old identity mutation before rendering the next account", async () => {
  let releaseOld: ((response: Response) => void) | undefined;
  const oldPost = new Promise<Response>(resolve => {
    releaseOld = resolve;
  });
  let walletReads = 0;
  const fetcher = vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "POST") return oldPost;
    if (url.includes("/commands/")) {
      throw new Error("old command must not be polled after identity changes");
    }
    walletReads += 1;
    return Promise.resolve(answer({
      wallet: walletReads === 1 ? null : {
        mode: "PAPER",
        wallet_id: "wallet-new",
        episode_id: "episode-new",
        sequence: 1,
        initial_capital: { amount: "2222", currency: "USDT" },
        balance: { amount: "2222", currency: "USDT" },
        started_at: "2026-10-15T00:00:00Z",
        snapshot_at: "2026-10-15T00:00:01Z",
        revision: 1,
        reset_available: false,
        reset_reason: "ACTIVITY_UNKNOWN",
      },
    }));
  });
  vi.stubGlobal("fetch", fetcher);
  vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(
    "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  );
  document.cookie = "tiewtrade_csrf=paper-csrf";
  const panel = (who: typeof identity) => (
    <AccountSession identity={who}>
      <PaperWalletPanel identity={who} />
    </AccountSession>
  );
  const view = render(panel(identity));
  await screen.findByLabelText(t("initialCapital"));
  fireEvent.change(screen.getByLabelText(t("initialCapital")), {
    target: { value: "1500" },
  });
  fireEvent.click(screen.getByRole("button", { name: t("create") }));

  view.rerender(panel({ ...identity, user_id: "paper-user-two" }));
  await screen.findAllByText("2,222 USDT");
  releaseOld?.(answer({
    command_id: "old-command",
    state: "PENDING",
    failure_code: null,
    status_url: "/paper-wallet/commands/old-command",
  }, 202));

  await waitFor(() => expect(document.body.textContent).not.toContain(t("pending")));
  expect(fetcher.mock.calls.some(([url]) => String(url).includes("old-command"))).toBe(false);
});
