import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { PaperTradingActivity } from "../src/PaperTradingActivity";
import { protectionText as t } from "../src/protectionMessages";
import type { Protection } from "../src/protections";
const { send, state } = vi.hoisted(() => ({ send: vi.fn(), state: { busy: false, storageError: false } }));
vi.mock("../src/PaperOrderList", async importOriginal => ({
  ...await importOriginal<typeof import("../src/PaperOrderList")>(),
  usePaperOrders: () => ({ rows: [], query: { isSuccess: true, isError: false, isPending: false, hasNextPage: false, isFetchingNextPage: false } }),
}));
vi.mock("../src/useProtections", () => ({ useProtectionAttempt: () => ({
  ...state, send, recovered: true, pending: [], discovery: { isError: false },
  lookup: { isFetching: false }, result: { data: null },
}) }));
const row: Protection = { protection_id: "armed", wallet_id: "wallet", episode_id: "episode", mode: "PAPER",
  base: "BTC", quote: "USDT", quantity: "0.00131868", protected_quantity: "0.00131",
  executable_quantity: "0.00131", step_residual_quantity: "0.00000868", state: "ARMED", revision: 4,
  take_profit_price: "76500", stop_loss_price: "75000", conflicted: false, failure_code: null,
  market_ready: true, entry_order_id: null, snapshot_at: "2026-11-08T04:00:00Z" };
const props = { owner: "owner", base: "BTC", scope: { expected_wallet_id: "wallet", expected_episode_id: "episode" },
  view: "OPEN" as const, onViewChange: vi.fn(), ordersDisabled: false, onCancelOrder: vi.fn(), rows: [row], visible: true, disabled: false, ready: true, error: false, available: "0", enabled: true };
beforeEach(() => { send.mockReset(); state.busy = false; state.storageError = false; });
afterEach(cleanup);
const dataRows = () => screen.getAllByRole("row").slice(1);
it("keeps current, failed, conflicted and unknown rows visible, moving only completed history", () => {
  const states = ["WAITING_ENTRY", "ARMING", "ARMED", "EXITING", "FAILED", "NEW_UNKNOWN", "CLOSED", "CANCELED"];
  const rows = states.map(value => ({ ...row, protection_id: value, state: value }));
  const data = [...rows, { ...row, protection_id: "conflict", state: "CANCELED", conflicted: true }, { ...row, protection_id: "other", episode_id: "other" }];
  const ui = render(<PaperTradingActivity {...props} rows={data}/>);
  expect(dataRows()).toHaveLength(7);
  expect(screen.getByText(t("FAILED"))).toBeTruthy();
  expect(screen.getByText(t("conflict"))).toBeTruthy();
  ui.rerender(<PaperTradingActivity {...props} rows={data} view="HISTORY"/>);
  expect(dataRows()).toHaveLength(2);
  expect(screen.queryByRole("button", { name: t("edit") })).toBeNull();
  expect(screen.queryByRole("button", { name: t("cancel") })).toBeNull();
  expect(send).not.toHaveBeenCalled();
});
it("keeps residual warning visible without opening details", () => {
  render(<PaperTradingActivity {...props}/>);
  expect(screen.getByText(t("noAutoSale"))).toBeTruthy();
  expect(screen.getByText("0.00000868 BTC")).toBeTruthy();
  expect(screen.getByText("0.00131 BTC")).toBeTruthy();
});
it("details reads refreshed data and closes when the selected row disappears", () => {
  const view = render(<PaperTradingActivity {...props}/>);
  fireEvent.click(screen.getByRole("button", { name: t("details") }));
  expect(within(screen.getByRole("dialog")).getByText("0.00131 BTC")).toBeTruthy();
  view.rerender(<PaperTradingActivity {...props} rows={[{ ...row, protected_quantity: "0", step_residual_quantity: null, market_ready: false }]}/>);
  expect(within(screen.getByRole("dialog")).getByText("0 BTC")).toBeTruthy();
  expect(within(screen.getByRole("dialog")).getByText(t("coverageUnknown"))).toBeTruthy();
  expect(within(screen.getByRole("dialog")).getByRole("alert").textContent).toBe(t("unavailable"));
  view.rerender(<PaperTradingActivity {...props} rows={[]}/>);
  expect(screen.queryByRole("dialog")).toBeNull();
  view.rerender(<PaperTradingActivity {...props}/>);
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(send).not.toHaveBeenCalled();
});
it("closes details on owner scope change even if ids are reused", () => {
  const view = render(<PaperTradingActivity {...props}/>);
  fireEvent.click(screen.getByRole("button", { name: t("details") }));
  view.rerender(<PaperTradingActivity {...props} owner="other-owner"/>);
  expect(screen.queryByRole("dialog")).toBeNull();
});
it("restores details trigger focus on Escape", () => {
  render(<PaperTradingActivity {...props}/>);
  const trigger = screen.getByRole("button", { name: t("details") }); trigger.focus(); fireEvent.click(trigger);
  expect(document.activeElement?.textContent).toBe(t("close"));
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.activeElement).toBe(trigger);
});
it("preserves edit and cancellation string payloads and expected revision", () => {
  render(<PaperTradingActivity {...props}/>);
  fireEvent.click(screen.getByRole("button", { name: t("edit") }));
  expect(screen.getByLabelText<HTMLInputElement>(`${t("quantity")} (BTC)`).value).toBe(row.quantity);
  fireEvent.click(screen.getByRole("button", { name: t("save") }));
  expect(send).toHaveBeenLastCalledWith(expect.objectContaining({ action: "REPLACE", target: "armed", payload: { ...props.scope, expected_revision: 4, quantity: row.quantity, take_profit_price: "76500", stop_loss_price: "75000" } }));
  fireEvent.click(screen.getByRole("button", { name: t("cancel") }));
  expect(send).toHaveBeenLastCalledWith(expect.objectContaining({ action: "CANCEL", target: "armed", payload: { ...props.scope, expected_revision: 4 } }));
});
it.each(["disabled", "busy", "storageError"] as const)("keeps mutation blocked by %s while details remain readable", flag => {
  if (flag !== "disabled") state[flag] = true;
  render(<PaperTradingActivity {...props} disabled={flag === "disabled"}/>);
  for (const name of [t("edit"), t("cancel")]) expect(screen.getByRole<HTMLButtonElement>("button", { name }).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: t("details") }));
  expect(screen.getByRole("dialog")).toBeTruthy(); expect(send).not.toHaveBeenCalled();
});
it("shows history even when monitoring is disabled and keeps linked exit facts in details", () => {
  render(<PaperTradingActivity {...props} view="HISTORY" enabled={false} rows={[{ ...row, state: "CLOSED", quantity: "0", protected_quantity: "0", step_residual_quantity: "0", exit_order_id: "exit", exit_order_state: "FILLED", exit_filled_quantity: "0.00131" }]}/>);
  fireEvent.click(screen.getByRole("button", { name: t("details") }));
  expect(within(screen.getByRole("dialog")).getByText(`${t("exit")}: exit`)).toBeTruthy();
  expect(within(screen.getByRole("dialog")).getByText("0.00131 BTC")).toBeTruthy();
});

it("closes local dialogs on history or episode changes without sending a request", () => {
  const ui = render(<PaperTradingActivity {...props}/>);
  fireEvent.click(screen.getByRole("button", { name: t("edit") }));
  ui.rerender(<PaperTradingActivity {...props} scope={{ ...props.scope, expected_episode_id: "new-episode" }}/>);
  expect(screen.queryByRole("dialog")).toBeNull();
  ui.rerender(<PaperTradingActivity {...props}/>);
  expect(screen.queryByRole("dialog")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: t("details") }));
  ui.rerender(<PaperTradingActivity {...props} view="HISTORY"/>);
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(screen.getByText(t("emptyActivityHistory"))).toBeTruthy();
  expect(send).not.toHaveBeenCalled();
});

it("edits a different symbol by its row identity while create retains the chart symbol", () => {
  const eth = { ...row, protection_id: "eth-protection", base: "ETH", quantity: "1.2345", protected_quantity: "1.23", take_profit_price: "5000" };
  const ui = render(<PaperTradingActivity {...props} base="BTC" rows={[eth]}/>);
  expect(screen.getByText("ETH/USDT")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: t("edit") }));
  expect(screen.getByLabelText<HTMLInputElement>(`${t("quantity")} (ETH)`).value).toBe("1.2345");
  ui.rerender(<PaperTradingActivity {...props} base="BNB" rows={[eth]}/>);
  expect(screen.getByLabelText<HTMLInputElement>(`${t("quantity")} (ETH)`).value).toBe("1.2345");
  fireEvent.click(screen.getByRole("button", { name: t("save") }));
  expect(send).toHaveBeenLastCalledWith(expect.objectContaining({ action: "REPLACE", target: "eth-protection", payload: { ...props.scope, expected_revision: 4, quantity: "1.2345", take_profit_price: "5000", stop_loss_price: "75000" } }));
  ui.rerender(<PaperTradingActivity {...props} base="BTC" rows={[eth]}/>);
  fireEvent.click(screen.getByRole("button", { name: t("create") }));
  fireEvent.change(screen.getByLabelText(`${t("quantity")} (BTC)`), { target: { value: "0.001" } });
  fireEvent.change(screen.getByLabelText(t("tp")), { target: { value: "80000" } });
  fireEvent.click(screen.getByRole("button", { name: t("save") }));
  expect(send).toHaveBeenLastCalledWith(expect.objectContaining({ action: "CREATE", payload: { ...props.scope, base: "BTC", quantity: "0.001", take_profit_price: "80000", stop_loss_price: null } }));
});
it("never claims an empty combined activity when protection data is partial or failed", () => {
  const ui = render(<PaperTradingActivity {...props} rows={[]} ready={false}/>);
  expect(screen.queryByText(t("emptyActivity"))).toBeNull();
  ui.rerender(<PaperTradingActivity {...props} rows={[]} error/>);
  expect(screen.queryByText(t("emptyActivity"))).toBeNull();
  ui.rerender(<PaperTradingActivity {...props} rows={[]}/>);
  expect(screen.getByText(t("emptyActivity"))).toBeTruthy();
});
it("filters incompatible wallet/episode/mode records without hiding another symbol", () => {
  render(<PaperTradingActivity {...props} rows={[
    { ...row, protection_id: "eth", base: "ETH" },
    { ...row, protection_id: "wallet-other", wallet_id: "other" },
    { ...row, protection_id: "episode-other", episode_id: "other" },
    { ...row, protection_id: "live", mode: "LIVE" } as unknown as Protection,
  ]}/>);
  expect(screen.getByText("ETH/USDT")).toBeTruthy();
  expect(screen.queryByText("BTC/USDT")).toBeNull();
  expect(dataRows()).toHaveLength(1);
});

it("shows the immutable submitted exit quantity separately from partial fills and current metadata", () => {
  const exiting = { ...row, state: "EXITING", quantity: "0.499", protected_quantity: "0", executable_quantity: "0.4", step_residual_quantity: "0.099", exit_order_id: "exit", exit_order_state: "PARTIALLY_FILLED", exit_quantity: "0.99", exit_filled_quantity: "0.5" };
  const ui = render(<PaperTradingActivity {...props} rows={[exiting]}/>);
  fireEvent.click(screen.getByRole("button", { name: t("details") }));
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByText("0.99 BTC")).toBeTruthy();
  expect(within(dialog).getByText(t("exitQuantity"), { exact: false }).textContent).toContain("0.99 BTC");
  expect(within(dialog).getByText("0.5 BTC")).toBeTruthy();
  ui.rerender(<PaperTradingActivity {...props} rows={[{ ...exiting, quantity: "0.199", executable_quantity: "0.1", exit_filled_quantity: "0.8" }]}/>);
  expect(within(dialog).getByText("0.99 BTC")).toBeTruthy();
  expect(within(dialog).getByText("0.8 BTC")).toBeTruthy();
  expect(within(dialog).getByText("0.199 BTC")).toBeTruthy();
  expect(send).not.toHaveBeenCalled();
});
