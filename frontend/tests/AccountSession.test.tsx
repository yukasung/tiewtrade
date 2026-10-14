import { useQuery, useQueryClient } from "@tanstack/react-query";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { AccountSession } from "../src/AccountSession";
import type { Me } from "../src/auth";
const identity = { user_id: "old", totp_enabled: true };
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("cancels pending queries and clears both caches when identity changes", async () => {
  const clients: ReturnType<typeof useQueryClient>[] = [];
  let oldResolve!: (value: string) => void;
  let oldSignal: AbortSignal | undefined;
  function Probe({ identity }: { identity: Me }) {
    const client = useQueryClient();
    if (!clients.includes(client)) clients.push(client);
    const query = useQuery({
      queryKey: ["trading-account", identity.user_id],
      queryFn: ({ signal }) => {
        if (identity.user_id === "old") {
          oldSignal = signal;
          return new Promise<string>((resolve) => {
            oldResolve = resolve;
          });
        }
        return Promise.resolve("NEW ACCOUNT");
      },
    });
    return <p>{query.data ?? "loading"}</p>;
  }
  const view = render(
    <AccountSession identity={identity}>
      <Probe identity={identity} />
    </AccountSession>,
  );
  await waitFor(() => expect(oldResolve).toBeTypeOf("function"));
  const newer = { ...identity, user_id: "new" };
  view.rerender(
    <AccountSession identity={newer}>
      <Probe identity={newer} />
    </AccountSession>,
  );
  await screen.findByText("NEW ACCOUNT");
  expect(oldSignal?.aborted).toBe(true);
  expect(clients[0]?.getQueryCache().getAll()).toHaveLength(0);
  expect(clients[0]?.getMutationCache().getAll()).toHaveLength(0);
  await act(async () => {
    oldResolve("OLD ACCOUNT");
    await Promise.resolve();
  });
  expect(screen.queryByText("OLD ACCOUNT")).toBeNull();
  view.unmount();
  expect(clients[1]?.getQueryCache().getAll()).toHaveLength(0);
});
it("session expired cancels and clears cache and invokes auth boundary", async () => {
  const expired = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify({ detail: "SESSION_INVALID" }), {
          status: 401,
        }),
      ),
    ),
  );
  // Probe uses the shared error class so query-level expiry cannot retain old data.
  const { ApiRequestError } = await import("../src/auth");
  function Probe() {
    useQuery({
      queryKey: ["trading-account", "old"],
      queryFn: () =>
        Promise.reject(new ApiRequestError("SESSION_INVALID", 401)),
    });
    return <p>probe</p>;
  }
  render(
    <AccountSession identity={identity} onExpired={expired}>
      <Probe />
    </AccountSession>,
  );
  await waitFor(() => expect(expired).toHaveBeenCalledOnce());
});
it("keeps the same cache when auth callback changes within one identity", async () => {
  let client: ReturnType<typeof useQueryClient> | undefined;
  function Probe() {
    client = useQueryClient();
    const query = useQuery({
      queryKey: ["trading-account", "old"],
      queryFn: () => Promise.resolve("same user"),
    });
    return <p>{query.data}</p>;
  }
  const view = render(
    <AccountSession identity={identity} onExpired={() => undefined}>
      <Probe />
    </AccountSession>,
  );
  await screen.findByText("same user");
  view.rerender(
    <AccountSession identity={identity} onExpired={() => undefined}>
      <Probe />
    </AccountSession>,
  );
  expect(client?.getQueryData(["trading-account", "old"])).toBe("same user");
});
it("real panels ignore late key and account responses after identity switch", async () => {
  const { ApiKeyPanel } = await import("../src/ApiKeyPanel");
  const { TradingAccountPanel } = await import("../src/TradingAccountPanel");
  const pending: {
    resolve: (value: Response) => void;
    signal: AbortSignal | undefined;
  }[] = [];
  let old = true;
  const key = {
    id: "new-key",
    label: "NEW KEY",
    public_tail: "BBBB",
    status: "ACTIVE",
    created_at: "2026-10-07T00:00:00Z",
    may_retry: false,
  };
  const account = { use: null, key, may_trade: false, may_change_use: false };
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) =>
      old
        ? new Promise<Response>((resolve) =>
            pending.push({ resolve, signal: init?.signal ?? undefined }),
          )
        : Promise.resolve(
            new Response(
              JSON.stringify(url.endsWith("api-keys") ? [key] : account),
              { status: 200 },
            ),
          ),
    ),
  );
  const panels = (who: Me) => (
    <AccountSession identity={who}>
      <ApiKeyPanel identity={who} />
      <TradingAccountPanel identity={who} />
    </AccountSession>
  );
  const view = render(panels(identity));
  await waitFor(() => expect(pending).toHaveLength(2));
  old = false;
  view.rerender(panels({ ...identity, user_id: "new" }));
  await screen.findByText("ยังไม่ได้เลือกประเภทการใช้งาน");
  expect(pending.every((request) => request.signal?.aborted)).toBe(true);
  await act(async () => {
    pending[0]?.resolve(
      new Response(JSON.stringify([{ ...key, label: "OLD KEY" }])),
    );
    pending[1]?.resolve(
      new Response(
        JSON.stringify({ ...account, key: { ...key, label: "OLD KEY" } }),
      ),
    );
    await Promise.resolve();
  });
  expect(screen.queryByText(/OLD KEY/)).toBeNull();
  expect(screen.getAllByText(/NEW KEY/).length).toBeGreaterThan(0);
});
it("account 401 unmounts the authenticated account boundary", async () => {
  window.history.replaceState(null, "", "/trading-account");
  const { AuthPanel } = await import("../src/AuthPanel");
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve(
        new Response(
          JSON.stringify(
            url.endsWith("auth/me")
              ? identity
              : url.endsWith("trading-account")
                ? { detail: "ต้องเข้าสู่ระบบก่อน" }
                : [],
          ),
          { status: url.endsWith("trading-account") ? 401 : 200 },
        ),
      ),
    ),
  );
  render(<AuthPanel />);
  await waitFor(() =>
    expect(
      vi
        .mocked(fetch)
        .mock.calls.some(([url]) => url === "/api/trading-account"),
    ).toBe(true),
  );
  await waitFor(() => expect(screen.getByTestId("signed-out")).toBeTruthy());
  expect(screen.queryByTestId("trading-account-panel")).toBeNull();
  expect(screen.queryByTestId("api-key-panel")).toBeNull();
});
