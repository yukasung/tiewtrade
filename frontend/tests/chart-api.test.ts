import { afterEach, expect, it, vi } from "vitest";
import { history } from "../src/chart/api";
import { chartPage, chartSeries } from "./chartFixture";

afterEach(() => vi.unstubAllGlobals());

it("reads a complete streamed response without cancelling its successful body", async () => {
  const cancelled = vi.fn();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) { controller.enqueue(new TextEncoder().encode(JSON.stringify(chartPage()))); controller.close(); },
    cancel: cancelled,
  });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(stream)));
  const page = await history(chartSeries, new AbortController().signal);
  expect(page.display_proof).toBe("test-proof");
  expect(cancelled).not.toHaveBeenCalled();
  expect(stream.locked).toBe(false);
});

it("rejects over-limit bytes before caching and preserves the error if cancellation fails", async () => {
  const cancelled = vi.fn(() => Promise.reject(new Error("already disconnected")));
  const stream = new ReadableStream<Uint8Array>({
    start(controller) { controller.enqueue(new Uint8Array(2 * 1024 * 1024 + 1)); }, cancel: cancelled,
  });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(stream)));
  await expect(history(chartSeries, new AbortController().signal))
    .rejects.toMatchObject({ message: "INDICATOR_RESOURCE_LIMIT", status: 503 });
  expect(cancelled).toHaveBeenCalledOnce();
  expect(stream.locked).toBe(false);
});

it("accepts the exact byte bound and rejects invalid UTF-8 before JSON parsing", async () => {
  const text = JSON.stringify(chartPage());
  const bytes = new TextEncoder().encode(text + " ".repeat(2 * 1024 * 1024 - text.length));
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(new Response(bytes))
    .mockResolvedValueOnce(new Response(new Uint8Array([255]))));
  await expect(history(chartSeries, new AbortController().signal)).resolves.toMatchObject({ dataset_revision: "a" });
  await expect(history(chartSeries, new AbortController().signal))
    .rejects.toMatchObject({ message: "CHART_INVALID_RESPONSE" });
});

it("preserves typed refusals and Retry-After without creating a history page", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
    JSON.stringify({ detail: "INDICATOR_DATA_NOT_READY" }), { status: 503, headers: { "Retry-After": "10" } },
  )));
  await expect(history(chartSeries, new AbortController().signal)).rejects.toMatchObject({
    message: "INDICATOR_DATA_NOT_READY", status: 503, retryAt: expect.any(String) as unknown,
  });
});
