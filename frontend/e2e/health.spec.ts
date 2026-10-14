import { expect, test } from "./helpers/test";
import type { Health } from "../src/api";

test("page has no footer and the health API remains available", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "TiewTrade" })).toBeVisible();
  await expect(page.getByRole("main")).toHaveCount(1);
  await expect(page.locator("footer")).toHaveCount(0);
  const response = await page.request.get("/api/health");
  expect(response.ok()).toBe(true);
  const health = await response.json() as Health;
  expect(health.status).toBe("ok");
  expect(health.version).toMatch(/^\d+\.\d+\.\d+$/);
  expect(Number.isNaN(Date.parse(health.server_time))).toBe(false);
});
