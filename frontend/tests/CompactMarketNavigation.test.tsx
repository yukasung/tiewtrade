import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AccountLayout } from "../src/layout/AccountLayout";
import { TradingWorkspace } from "../src/TradingWorkspace";
import { accountI18n, accountText as t } from "../src/accountMessages";

beforeEach(() => {
  vi.stubEnv("VITE_CHART_ENABLED", "1");
  vi.stubGlobal("fetch", vi.fn());
});
afterEach(async () => {
  cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs();
  window.localStorage.clear(); document.documentElement.classList.remove("dark");
  delete document.documentElement.dataset.colorScheme;
  await accountI18n.changeLanguage("th");
});
it.each([["th", 1440], ["en", 1440], ["th", 375], ["en", 375]] as const)("groups Spot/Futures under Paper and Live in %s at %i", async (locale, width) => {
  vi.stubGlobal("innerWidth", width);
  await accountI18n.changeLanguage(locale);
  render(<AccountLayout page="paper/trade"><p>workspace</p></AccountLayout>);
  const compact = width < 1280;
  if (compact) fireEvent.click(screen.getByRole("button", { name: t("menu") }));
  for (const [label, path] of [["Paper", "/paper/trade"], ["Live", "/live/trade"]] as const) {
    const trigger = screen.getByRole("button", { name: label });
    fireEvent.click(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    const spot = screen.getByRole("link", { name: "Spot" });
    expect(spot.getAttribute("href")).toBe(path);
    expect(spot.getAttribute("aria-current")).toBe(label === "Paper" ? "page" : null);
    const futures = screen.getByRole<HTMLButtonElement>("button", { name: "Futures" });
    expect(futures.disabled).toBe(true);
    expect(futures.title).toBe(t("futuresUnavailable"));
    expect(futures.hasAttribute("href")).toBe(false);
    const previous = window.location.href;
    fireEvent.click(futures);
    expect(window.location.href).toBe(previous);
    fireEvent.keyDown(spot, { key: "Escape" });
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(trigger);
    if (compact) expect(screen.getByRole("button", { name: t("close") }).getAttribute("aria-expanded")).toBe("true");
  }
  expect(fetch).not.toHaveBeenCalled();
});
it("opens one market group and preserves native modified clicks", () => {
  vi.stubGlobal("innerWidth", 1440);
  render(<AccountLayout page="paper/trade"><label>Draft<input defaultValue="keep"/></label></AccountLayout>);
  const paper = screen.getByRole("button", { name: "Paper" });
  const live = screen.getByRole("button", { name: "Live" });
  fireEvent.click(paper);
  fireEvent.pointerDown(live);
  act(() => live.focus());
  fireEvent.click(live);
  expect(paper.getAttribute("aria-expanded")).toBe("false");
  expect(live.getAttribute("aria-expanded")).toBe("true");
  const before = window.location.href;
  let preventedByNavigation = true;
  window.addEventListener("click", event => {
    preventedByNavigation = event.defaultPrevented;
    event.preventDefault(); // jsdom has no new-tab navigation, after the React handler ran.
  }, { once: true });
  fireEvent.click(screen.getByRole("link", { name: "Spot" }), { ctrlKey: true });
  expect(preventedByNavigation).toBe(false);
  expect(window.location.href).toBe(before);
  expect(live.getAttribute("aria-expanded")).toBe("true");
  const draft = screen.getByLabelText("Draft");
  fireEvent.pointerDown(draft);
  act(() => draft.focus());
  expect(live.getAttribute("aria-expanded")).toBe("true");
  fireEvent.click(draft);
  expect(live.getAttribute("aria-expanded")).toBe("false");
  expect(fetch).not.toHaveBeenCalled();
});
it.each(["PAPER", "LIVE"] as const)("removes the pair badge while preserving the %s header cue and draft", mode => {
  vi.stubGlobal("innerWidth", 375);
  const { container } = render(<AccountLayout page={mode === "PAPER" ? "paper/trade" : "live/trade"}>
    <TradingWorkspace mode={mode} bases={[]} base="" onBase={vi.fn()} chart={<p>chart fixture</p>}
      form={<label>Draft<input defaultValue="keep" /></label>} />
  </AccountLayout>);
  expect(container.querySelector(".account-brand")?.textContent).toBe("TiewTrade");
  expect(container.querySelector(".trade-workspace-bar .rounded-full")).toBeNull();
  const expectedMode = mode === "PAPER" ? t("paperMode") : t("liveMode");
  expect(screen.getByRole("button", { name: t("menu") }).textContent).toContain(expectedMode);
  const draft = screen.getByLabelText<HTMLInputElement>("Draft");
  fireEvent.change(draft, { target: { value: "unsaved" } });
  fireEvent.click(screen.getByRole("button", { name: t("menu") }));
  fireEvent.keyDown(document, { key: "Escape" });
  act(() => { vi.stubGlobal("innerWidth", 1280); window.dispatchEvent(new Event("resize")); });
  expect(screen.getByLabelText("Draft")).toBe(draft);
  expect(draft.value).toBe("unsaved");
  expect(screen.getByRole("button", { name: expectedMode, current: true }).getAttribute("data-active")).toBe("true");
  expect(fetch).not.toHaveBeenCalled();
});
