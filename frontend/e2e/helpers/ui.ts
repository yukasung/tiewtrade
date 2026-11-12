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

/** Reveal a shell link through the responsive navigation, preserving real clicks. */
export async function navigationLink(page: Page, path: string) {
  const width = page.viewportSize()?.width ?? await page.evaluate(() => window.innerWidth);
  const trigger = page.locator(width < 1280
    ? 'button[aria-controls="compact-navigation"]'
    : 'button[aria-controls="account-dropdown"]');
  // ResizeObserver/media-query updates can settle after setViewportSize resolves.
  // Wait for the expected breakpoint rather than inspecting the previous layout.
  await expect(trigger).toBeVisible();
  if (width < 1280 && await trigger.getAttribute("aria-expanded") !== "true") await trigger.click();
  const link = page.locator(`.account-header nav a[href="${path}"]`);
  if (!await link.isVisible()) {
    if (path === "/paper/trade" || path === "/live/trade") {
      await page.locator(`.account-market-trigger[data-market-page="${path.slice(1)}"]`).click();
    } else await trigger.click();
  }
  return link;
}
