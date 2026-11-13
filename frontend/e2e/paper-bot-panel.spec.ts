import { expect, test } from "./helpers/test";
import { navigationLink } from "./helpers/ui";
test("Paper bot panel has no mutation across 16 responsive language/theme combinations", async ({ page }, info) => {
  let expandedProtections = false;
  await page.route(/\/api\/paper\/trade(?:\?|$)/, route => route.fulfill({ json: {
    mode: "PAPER", base: new URL(route.request().url()).searchParams.get("base"), quote: "USDT", account_use: "MANUAL",
    snapshot_at: new Date().toISOString(), admission_ready: false, admission_reasons: ["ORDER_SAFETY_UNAVAILABLE"],
    wallet: { wallet_id: "bot-ui-wallet", episode_id: "bot-ui-episode", available_quote: "9800.000000000000000001",
      balance: "9800.000000000000000001", reserved_quote: "0", source_availability: "READY", base_balances: [], revision: 1 },
  } }));
  await page.route(/\/api\/paper\/(?:orders|order-requests|protections|protection-requests)\?/, route => route.fulfill({ json: {
    orders: [], requests: [], protections: expandedProtections && new URL(route.request().url()).pathname.endsWith("/protections")
      ? Array.from({ length: 10 }, (_, index) => ({ protection_id: `scroll-${index}`, wallet_id: "bot-ui-wallet", episode_id: "bot-ui-episode",
        mode: "PAPER", base: "BTC", quote: "USDT", quantity: "0.1", protected_quantity: "0.1", executable_quantity: "0.1", step_residual_quantity: "0",
        state: "ARMED", revision: 1, take_profit_price: "110", stop_loss_price: "90", conflicted: false, failure_code: null,
        market_ready: true, entry_order_id: null, snapshot_at: new Date().toISOString() })) : [],
    next_cursor: null, snapshot_at: new Date().toISOString(),
  } }));
  await page.route("**/api/paper/risk-limit", route => route.fulfill({ json: { latched: false, amount: null } }));
  await page.goto("/account"); await page.getByTestId("switch-mode").click();
  await page.getByLabel("อีเมล").fill(`bot-ui-${Date.now()}@example.com`);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill("bot-panel-fixture-password-long");
  await page.getByTestId("submit").click(); await expect(page.getByTestId("log-out")).toBeVisible();
  await (await navigationLink(page, "/paper/trade")).click();
  await page.getByLabel("คู่เทรด", { exact: true }).selectOption("BTC");
  const panel = page.locator('[aria-labelledby="paper-bot-title"]');
  await expect(panel.locator(".market-value")).toContainText("9,800.000000000000000001");
  const writes: string[] = [];
  page.on("request", request => { if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method())) writes.push(new URL(request.url()).pathname); });
  await panel.locator("input").fill("123.450000000000000001");
  for (const width of [375, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    const menu = page.locator(width < 1280 ? 'button[aria-controls="compact-navigation"]' : 'button[aria-controls="account-dropdown"]');
    await expect(menu).toBeVisible();
    await menu.click(); await page.keyboard.press("Escape");
    const settings = page.locator(".kill-switch-settings > button");
    await settings.click(); await page.keyboard.press("Escape");
    await expect(panel.locator("input")).toHaveValue("123.450000000000000001");
    const reduce = page.getByRole("button", { name: /ลด\/ปิดสถานะ|Reduce \/ close holdings/ });
    await reduce.click(); await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByRole("dialog").getByRole("tab", { name: "BUY", exact: true })).toHaveCount(0);
    await page.keyboard.press("Escape"); await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(reduce).toBeFocused();
    for (const locale of ["th", "en"]) {
      await page.evaluate(async language => {
        const path = "/src/manualOrderMessages.ts";
        const module = await import(/* @vite-ignore */ path) as { manualOrderI18n: { changeLanguage: (language: string) => Promise<unknown> } };
        await module.manualOrderI18n.changeLanguage(language);
      }, locale);
      // Existing messages translate at render time; force an actual local draft change.
      await panel.locator("input").fill("123"); await panel.locator("input").fill("123.450000000000000001");
      for (const theme of ["light", "dark"]) {
        await page.evaluate(value => { document.documentElement.classList.toggle("dark", value === "dark"); }, theme);
        await expect(panel.getByRole("heading", { level: 2 })).toHaveText("Paper Spot");
        await expect(panel.getByRole("button")).toBeDisabled(); await expect(panel.locator("form")).toHaveCount(0);
        await expect(panel.getByRole("tab")).toHaveCount(0);
        await panel.locator("input").focus(); await page.keyboard.press("Enter");
        await expect(panel.locator("input")).toHaveValue("123.450000000000000001");
        await page.keyboard.press("Shift+Tab"); await expect(panel.getByRole("combobox")).toBeFocused();
        await page.keyboard.press("Tab"); await expect(panel.locator("input")).toBeFocused();
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
        await panel.screenshot({ path: info.outputPath(`bot-${width}-${locale}-${theme}.png`) });
      }
    }
  }
  expandedProtections = true;
  await page.reload();
  await page.getByLabel("คู่เทรด", { exact: true }).selectOption("BTC");
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 480 });
    const reduce = page.getByRole("button", { name: /ลด\/ปิดสถานะ|Reduce \/ close holdings/ });
    await reduce.click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.locator('[id^="release-"]')).toHaveCount(10);
    const bounds = await dialog.boundingBox();
    expect(bounds!.y).toBeGreaterThanOrEqual(0);
    expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(480);
    for (const control of [dialog.locator("#manual-amount"), dialog.locator("#release-scroll-0"), dialog.locator("#release-scroll-9"), dialog.locator('button[type="submit"]')]) {
      await control.evaluate(element => element.scrollIntoView({ block: "center", inline: "nearest" }));
      const box = await control.boundingBox();
      expect(box!.y).toBeGreaterThanOrEqual(bounds!.y);
      expect(box!.y + box!.height).toBeLessThanOrEqual(bounds!.y + bounds!.height);
    }
    await dialog.evaluate(element => { element.scrollTop = 0; });
    expect((await dialog.getByRole("heading").boundingBox())!.y).toBeGreaterThanOrEqual(0);
    await page.keyboard.press("Escape");
    await expect(reduce).toBeFocused();
    expect(await page.evaluate(() => document.body.style.overflow)).not.toBe("hidden");
  }
  expect(writes).toEqual([]);
});
