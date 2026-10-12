import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiRequestError } from "../src/auth";
import { readEpisode } from "../src/chart/readEpisode";
import { chartPage as page, chartSeries as input } from "./chartFixture";
afterEach(() => vi.useRealTimers());
describe("finite chart reads", () => {
  it("allows exactly twelve readiness requests with no reset", async () => {
    vi.useFakeTimers();
    const reader = vi.fn().mockRejectedValue(new ApiRequestError("INDICATOR_DATA_NOT_READY", 503, "10"));
    const work = readEpisode(input, new AbortController().signal, reader);
    const rejected = expect(work).rejects.toMatchObject({ message: "CHART_READ_BUDGET_EXHAUSTED" });
    await vi.runAllTimersAsync();
    await rejected;
    expect(reader).toHaveBeenCalledTimes(12);
  });
  it("discards all pages on 409 and spends only one restart", async () => {
    const reader = vi.fn().mockResolvedValueOnce(page("a", "cursor1"))
      .mockRejectedValueOnce(new ApiRequestError("INDICATOR_DATASET_CHANGED", 409))
      .mockResolvedValueOnce(page("b", "cursor2")).mockResolvedValueOnce(page("b"));
    const result = await readEpisode(input, new AbortController().signal, reader);
    expect(result.pages.map(p => p.dataset_revision)).toEqual(["b", "b"]);
    expect(reader.mock.calls[2]?.[0]).toEqual(input);
    reader.mockReset().mockRejectedValue(new ApiRequestError("INDICATOR_DATASET_CHANGED", 409));
    await expect(readEpisode(input, new AbortController().signal, reader)).rejects.toMatchObject({ status: 409 });
    expect(reader).toHaveBeenCalledTimes(2);
  });
  it.each([[422, "INDICATOR_NUMERIC_ERROR"], [429, "RATE_LIMITED"], [504, "INDICATOR_DEADLINE_EXCEEDED"],
    [503, "CHART_ADMISSION_UNAVAILABLE"], [503, "INDICATOR_DATA_UNAVAILABLE"]])(
    "stops on %s %s without retry", async (status, message) => {
      const reader = vi.fn().mockRejectedValue(new ApiRequestError(message, status));
      await expect(readEpisode(input, new AbortController().signal, reader)).rejects.toMatchObject({ message });
      expect(reader).toHaveBeenCalledTimes(1);
    });
  it("rejects revision mixing even if the server incorrectly returns 200", async () => {
    const reader = vi.fn().mockResolvedValueOnce(page("a", "cursor")).mockResolvedValueOnce(page("b"));
    await expect(readEpisode(input, new AbortController().signal, reader)).rejects.toMatchObject({ message: "CHART_INVALID_RESPONSE" });
  });
  it("rejects a first page for a different series", async () => {
    const reader = vi.fn().mockResolvedValue({ ...page(), base: "ETH" });
    await expect(readEpisode(input, new AbortController().signal, reader))
      .rejects.toMatchObject({ message: "CHART_INVALID_RESPONSE" });
  });
  it("cancels waiting without sending another readiness request", async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    const reader = vi.fn().mockRejectedValue(new ApiRequestError("INDICATOR_DATA_NOT_READY", 503));
    const work = readEpisode(input, controller.signal, reader);
    const rejected = expect(work).rejects.toMatchObject({ name: "AbortError" });
    await vi.advanceTimersByTimeAsync(1);
    controller.abort();
    await rejected;
    await vi.advanceTimersByTimeAsync(60_000);
    expect(reader).toHaveBeenCalledTimes(1);
  });
  it("rejects completion at the total elapsed deadline even if a reader ignores abort", async () => {
    let elapsed = 0;
    const reader = vi.fn(() => { elapsed = 300_000; return Promise.resolve(page()); });
    await expect(readEpisode(input, new AbortController().signal, reader, () => elapsed))
      .rejects.toMatchObject({ message: "CHART_READ_BUDGET_EXHAUSTED" });
    expect(reader).toHaveBeenCalledTimes(1);
  });
  it("rejects a late completion after cancellation", async () => {
    const controller = new AbortController();
    const reader = vi.fn(() => { controller.abort(); return Promise.resolve(page()); });
    await expect(readEpisode(input, controller.signal, reader)).rejects.toMatchObject({ name: "AbortError" });
  });
  it("reduces request deadlines to the remaining total budget", async () => {
    let elapsed = 0;
    const timeout = vi.spyOn(AbortSignal, "timeout");
    const reader = vi.fn().mockImplementationOnce(() => {
      elapsed = 299_500; return Promise.resolve(page("a", "next"));
    }).mockResolvedValueOnce(page());
    await readEpisode(input, new AbortController().signal, reader, () => elapsed);
    expect(timeout.mock.calls.map(call => call[0])).toEqual([30_000, 500]);
    timeout.mockRestore();
  });
});
