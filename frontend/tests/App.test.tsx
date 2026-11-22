import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "../src/App";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); });
it.each([false, true])("keeps a single main and no footer when authenticated=%s", async authenticated => {
  window.history.replaceState(null, "", "/account");
  const fetcher = vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(
    url.endsWith("auth/me") ? (authenticated ? { user_id: "footer-owner", totp_enabled: false } : {}) : {},
  ), { status: url.endsWith("auth/me") && !authenticated ? 401 : 200 })));
  vi.stubGlobal("fetch", fetcher);
  const { container } = render(<App />);
  await screen.findByTestId(authenticated ? "signed-in" : "signed-out");
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(container.querySelector("footer")).toBeNull();
  expect(fetcher.mock.calls.some(([url]) => url === "/api/health")).toBe(false);
});


it.each([false, true])("keeps login hidden during the initial session check (authenticated=%s)", async authenticated => {
  window.history.replaceState(null, "", "/account");
  let resolveIdentity: ((response: Response) => void) | undefined;
  vi.stubGlobal("fetch", vi.fn((url: string) => url.endsWith("auth/me")
    ? new Promise<Response>(resolve => { resolveIdentity = resolve; })
    : Promise.resolve(new Response(JSON.stringify({})))));
  render(<App/>);
  expect(screen.queryByTestId("signed-out")).toBeNull();
  expect(screen.queryByTestId("submit")).toBeNull();
  await screen.findByRole("status");
  await waitFor(() => expect(resolveIdentity).toBeTypeOf("function"));
  await act(async () => {
    await Promise.resolve();
    resolveIdentity!(new Response(JSON.stringify(authenticated ? { user_id: "reload-owner", totp_enabled: false } : {}),
      { status: authenticated ? 200 : 401 }));
  });
  await screen.findByTestId(authenticated ? "signed-in" : "signed-out");
  if (authenticated) expect(screen.queryByTestId("submit")).toBeNull();
});
