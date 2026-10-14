import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import {
  act, cleanup, fireEvent, render, screen, waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { Me } from "../src/auth";
import { AuthPanel } from "../src/AuthPanel";

const captured = vi.hoisted(() => ({ clients: [] as QueryClient[] }));
vi.mock("../src/ApiKeyPanel", async (original) => {
  const module = await original<typeof import("../src/ApiKeyPanel")>();
  return {
    ...module,
    ApiKeyPanel(props: { identity: Me }) {
      const client = useQueryClient();
      if (!captured.clients.includes(client)) captured.clients.push(client);
      return <module.ApiKeyPanel {...props} />;
    },
  };
});
vi.mock("../src/TotpPanel", () => ({
  TotpPanel: ({ onChanged }: { onChanged: () => Promise<void> }) => (
    <button onClick={() => void onChanged()}>TOTP changed</button>
  ),
}));

const identity = { user_id: "logout-owner", totp_enabled: true };
const key = {
  id: "key-one",
  label: "OLD KEY",
  public_tail: "ABCD",
  status: "ACTIVE",
  created_at: "2026-10-07T00:00:00Z",
  may_retry: false,
};
const account = { use: "MANUAL", key, may_trade: false, may_change_use: false };
const endpoints = [
  ["log-out", "/api/auth/logout"],
  ["log-out-everywhere", "/api/auth/logout-all"],
] as const;

async function goTo(page: string): Promise<void> {
  await act(async () => {
    window.history.replaceState(null, "", `/${page}`);
    window.dispatchEvent(new PopStateEvent("popstate"));
    await Promise.resolve();
  });
}

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}
beforeEach(() => {
  captured.clients = [];
  window.history.replaceState(null, "", "/api-keys");
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  document.cookie = "tiewtrade_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
});

it.each(endpoints.flatMap(([button, endpoint]) =>
  ["identity-error", "identity-hang", "csrf-error", "csrf-hang"].map((failure) =>
    ({ button, endpoint, failure }),
  ),
))("$endpoint clears cached account and aborts pending GET despite $failure", async ({ button, endpoint, failure }) => {
  let ended = false;
  let refetch = false;
  let oldSignal: AbortSignal | undefined;
  let resolveOld!: (value: Response) => void;
  const fetcher = vi.fn((url: string, init?: RequestInit): Promise<Response> => {
    if (url === endpoint && init?.method === "POST") {
      ended = true;
      return Promise.resolve(response({ ended: 1 }));
    }
    if (url.endsWith("auth/me")) {
      if (ended && failure === "identity-error") return Promise.resolve(response({}, 500));
      if (ended && failure === "identity-hang") return new Promise(() => undefined);
      return Promise.resolve(response(ended ? {} : identity, ended ? 401 : 200));
    }
    if (url.endsWith("auth/csrf")) {
      if (ended && failure === "csrf-error") return Promise.resolve(response({}, 500));
      if (ended && failure === "csrf-hang") return new Promise(() => undefined);
      return Promise.resolve(response({ csrf_token: "t" }));
    }
    if (url.endsWith("api-keys")) {
      if (refetch) {
        oldSignal = init?.signal ?? undefined;
        return new Promise((resolve) => {
          resolveOld = resolve;
        });
      }
      return Promise.resolve(response([key]));
    }
    if (url.endsWith("trading-account")) return Promise.resolve(response(account));
    throw new Error("Unexpected test request");
  });
  vi.stubGlobal("fetch", fetcher);
  render(<AuthPanel />);
  await screen.findByText("OLD KEY", { exact: true });
  const client = captured.clients[0]!;
  expect(client.getQueryData(["api-keys", identity.user_id])).toEqual([key]);
  client.setQueryData(["trading-account", identity.user_id], account);
  refetch = true;
  fireEvent.click(screen.getByRole("button", { name: "ดึงรายการใหม่" }));
  await waitFor(() => expect(resolveOld).toBeTypeOf("function"));
  await goTo("account");
  fireEvent.click(screen.getByTestId(button));
  await screen.findByTestId("signed-out");
  expect(screen.queryByTestId("signed-in")).toBeNull();
  expect(screen.queryByTestId("trading-account-panel")).toBeNull();
  expect(oldSignal?.aborted).toBe(true);
  expect(client.getQueryCache().getAll()).toHaveLength(0);
  expect(client.getMutationCache().getAll()).toHaveLength(0);
  expect(fetcher.mock.calls.filter(([url]) => url.endsWith("auth/me"))).toHaveLength(1);
  await act(async () => {
    resolveOld(response([key]));
    await Promise.resolve();
  });
  expect(document.body.textContent).not.toContain("OLD KEY");
  expect(client.getQueryCache().getAll()).toHaveLength(0);
});

it.each(endpoints)("%s retains the authenticated boundary when POST %s fails", async (button, endpoint) => {
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    if (url === endpoint && init?.method === "POST") return Promise.resolve(response({ detail: "Logout rejected" }, 403));
    return Promise.resolve(response(url.endsWith("auth/me") ? identity :
      url.endsWith("api-keys") ? [key] : url.endsWith("trading-account") ? account : { csrf_token: "t" }));
  }));
  render(<AuthPanel />);
  await screen.findByText("OLD KEY", { exact: true });
  await goTo("account");
  fireEvent.click(screen.getByTestId(button));
  await screen.findByText("Logout rejected");
  expect(screen.getByTestId("signed-in")).toBeTruthy();
  await goTo("api-keys");
  await screen.findByText("OLD KEY", { exact: true });
  expect(captured.clients).toHaveLength(1);
  expect(captured.clients[0]?.getQueryData(["api-keys", identity.user_id])).toEqual([key]);
});

it("a TOTP identity response started before logout cannot restore the old boundary", async () => {
  let identityReads = 0;
  let resolveIdentity!: (value: Response) => void;
  vi.stubGlobal("fetch", vi.fn((url: string) => {
    if (url.endsWith("auth/me")) {
      if (identityReads++ === 0) return Promise.resolve(response(identity));
      return new Promise<Response>((resolve) => {
        resolveIdentity = resolve;
      });
    }
    return Promise.resolve(response(url.endsWith("api-keys") ? [key] :
      url.endsWith("trading-account") ? account : url.endsWith("auth/logout") ? { ended: 1 } : { csrf_token: "t" }));
  }));
  render(<AuthPanel />);
  await screen.findByText("OLD KEY", { exact: true });
  await goTo("security");
  fireEvent.click(screen.getByRole("button", { name: "TOTP changed" }));
  await waitFor(() => expect(resolveIdentity).toBeTypeOf("function"));
  await goTo("account");
  fireEvent.click(screen.getByTestId("log-out"));
  await screen.findByTestId("signed-out");
  await act(async () => {
    resolveIdentity(response(identity));
    await Promise.resolve();
  });
  expect(screen.queryByTestId("signed-in")).toBeNull();
  expect(screen.getByTestId("signed-out")).toBeTruthy();
});

it.each(endpoints)("%s clears a pending key mutation after POST %s succeeds", async (button, endpoint) => {
  let resolveDeletion!: (value: Response) => void;
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "DELETE") {
      return new Promise<Response>((resolve) => { resolveDeletion = resolve; });
    }
    if (url === endpoint && init?.method === "POST") {
      return Promise.resolve(response({ ended: 1 }));
    }
    return Promise.resolve(response(url.endsWith("auth/me") ? identity :
      url.endsWith("api-keys") ? [key] : url.endsWith("trading-account") ? account : { csrf_token: "t" }));
  }));
  render(<AuthPanel />);
  await screen.findByText("OLD KEY", { exact: true });
  const client = captured.clients[0]!;
  fireEvent.click(screen.getByRole("button", { name: "ลบ key" }));
  fireEvent.click(screen.getByRole("button", { name: "ยืนยันลบ" }));
  await waitFor(() => expect(resolveDeletion).toBeTypeOf("function"));
  expect(client.getMutationCache().getAll()).toHaveLength(1);
  await goTo("account");
  fireEvent.click(screen.getByTestId(button));
  await screen.findByTestId("signed-out");
  expect(client.getMutationCache().getAll()).toHaveLength(0);
  expect(client.getQueryCache().getAll()).toHaveLength(0);
  await act(async () => {
    resolveDeletion(new Response(null, { status: 204 }));
    await Promise.resolve();
  });
  expect(screen.queryByTestId("signed-in")).toBeNull();
  expect(client.getMutationCache().getAll()).toHaveLength(0);
  expect(client.getQueryCache().getAll()).toHaveLength(0);
});
