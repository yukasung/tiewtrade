import { expect, type Page, type TestInfo } from "@playwright/test";

/** Capture the real UI at both supported sizes, without altering application state. */
export async function captureUi(
  page: Page,
  info: TestInfo,
  name: string,
): Promise<void> {
  for (const width of [1440, 360]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByRole("main")).toHaveCount(1);
    const brand = page.locator(".auth-brand");
    if (await brand.count()) {
      if (width === 1440) await expect(brand).toBeVisible();
      else await expect(brand).toBeHidden();
    }
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(width);
    await page.screenshot({
      path: info.outputPath(`${name}-${width}.png`),
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 1440, height: 900 });
}
