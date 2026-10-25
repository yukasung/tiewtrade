import { StrictMode } from "react";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { AccountSession } from "../src/AccountSession";
import { readAttempt, writeAttempt } from "../src/manualOrderJournal";
afterEach(() => { cleanup(); window.sessionStorage.clear(); });
function attempt(owner: string) { writeAttempt({ version: 1, owner, mode: "PAPER", action: "CANCEL", key: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee", orderId: "order", payload: { expected_wallet_id: "w", expected_episode_id: "e" } }); }
it("preserves recovery under StrictMode effect replay and clears it on actual session exit", async () => {
  attempt("owner");
  const view = render(<StrictMode><AccountSession identity={{ user_id: "owner", totp_enabled: false }}><p>session</p></AccountSession></StrictMode>);
  await Promise.resolve(); expect(readAttempt("owner")).not.toBeNull();
  view.unmount(); await waitFor(() => expect(readAttempt("owner")).toBeNull());
});
it("clears the old identity on owner switch without touching the new owner's recovery", async () => {
  attempt("first"); attempt("second");
  const view = render(<AccountSession identity={{ user_id: "first", totp_enabled: false }}><p>first</p></AccountSession>);
  view.rerender(<AccountSession identity={{ user_id: "second", totp_enabled: false }}><p>second</p></AccountSession>);
  await waitFor(() => expect(readAttempt("first")).toBeNull()); expect(readAttempt("second")).not.toBeNull();
});
