import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { PaperBotPanel } from "../src/PaperBotPanel";
import { paperBotText as bt } from "../src/paperBotMessages";
import { manualOrderText as t } from "../src/manualOrderMessages";
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it("keeps the budget as a local string, never submits and keeps start disabled", () => {
  const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
  const view = render(<PaperBotPanel available="10000.000000000000000001" loading={false}/>);
  expect(screen.getByRole<HTMLOptionElement>("option").selected).toBe(true);
  const input = screen.getByLabelText(bt("budget"));
  fireEvent.change(input, { target: { value: "123.450000000000000001" } });
  fireEvent.keyDown(input, { key: "Enter" }); fireEvent.click(screen.getByRole("button", { name: bt("start") }));
  fireEvent(window, new Event("resize"));
  view.rerender(<PaperBotPanel available={null} loading/>);
  expect((input as HTMLInputElement).value).toBe("123.450000000000000001");
  expect(screen.getByRole<HTMLButtonElement>("button", { name: bt("start") }).disabled).toBe(true);
  expect(view.container.querySelector("form")).toBeNull(); expect(fetcher).not.toHaveBeenCalled();
  expect(screen.queryByText(/10,000/)).toBeNull(); expect(screen.getByText(bt("loading"))).toBeTruthy();
  view.rerender(<PaperBotPanel available={null} loading={false}/>);
  expect(screen.getByText(t("unavailable"))).toBeTruthy();
});
it("clears only on scope remount and preserves exact balance display", () => {
  const view = render(<PaperBotPanel key="w:e:BTC" available="0.000000000000000001" loading={false}/>);
  expect(screen.getByText("0.000000000000000001 USDT")).toBeTruthy();
  fireEvent.change(screen.getByLabelText(bt("budget")), { target: { value: "20" } });
  view.rerender(<PaperBotPanel key="w:e:ETH" available={null} loading={false}/>);
  expect(screen.getByLabelText<HTMLInputElement>(bt("budget")).value).toBe("");
});
