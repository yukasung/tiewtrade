import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "../src/App";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); });
it.each([false, true])("keeps a single main and no footer when authenticated=%s", async authenticated => {
  window.history.replaceState(null, "", "/account");
  vi.stubEnv("VITE_CHART_ENABLED", "0");
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
