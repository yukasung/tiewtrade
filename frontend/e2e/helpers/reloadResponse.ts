import type { Page, Request, Response } from "@playwright/test";

/** Await a response from the reload, excluding in-flight requests from the old document. */
export async function reloadResponse(
  page: Page,
  matches: (response: Response) => boolean,
  afterReload: () => Promise<void>,
): Promise<Response> {
  let navigating = false;
  const requests = new Set<Request>();
  const observe = (request: Request) => {
    if (request.isNavigationRequest() && request.frame() === page.mainFrame()) navigating = true;
    if (navigating) requests.add(request);
  };
  page.on("request", observe);
  const response = page.waitForResponse(value => requests.has(value.request()) && matches(value));
  // Handle rejection immediately if navigation or selection fails before awaiting response.
  void response.catch(() => undefined);
  try {
    await page.reload();
    await afterReload();
    return await response;
  } finally {
    page.off("request", observe);
  }
}
