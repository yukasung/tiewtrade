import { expect, type Page, type TestInfo } from "@playwright/test";

/** Wait for React navigation to match the viewport before interacting or measuring. */
export async function waitForNavigationBreakpoint(page: Page) {
  const width = page.viewportSize()?.width ?? await page.evaluate(() => window.innerWidth);
  const trigger = page.locator(width < 1280
    ? 'button[aria-controls="compact-navigation"]'
    : 'button[aria-controls="account-dropdown"]');
  // setViewportSize can resolve before the matchMedia listener updates React.
  await expect(trigger).toBeVisible();
  return trigger;
}

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
    if (await page.locator(".account-header").count()) {
      await waitForNavigationBreakpoint(page);
    }
    if (await page.evaluate(() => document.documentElement.scrollWidth) > width) {
      await info.attach("overflow-bounds", { contentType: "application/json", body: JSON.stringify(
        await page.evaluate(() => [...document.querySelectorAll("body *")].map(element => {
          const rect = element.getBoundingClientRect();
          return { tag: element.tagName, class: element.className, x: rect.x, right: rect.right, width: rect.width };
        }).filter(element => element.right > window.innerWidth)),
      ) });
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
  const trigger = await waitForNavigationBreakpoint(page);
  if (width < 1280 && await trigger.getAttribute("aria-expanded") !== "true") await trigger.click();
  const link = page.locator(`.account-header nav a[href="${path}"]`);
  if (!await link.isVisible()) {
    if (path === "/paper/trade" || path === "/live/trade") {
      await page.locator(`.account-market-trigger[data-market-page="${path.slice(1)}"]`).click();
    } else await trigger.click();
  }
  return link;
}
