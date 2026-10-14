import { expect, it } from "vitest";
import { anchoredRange } from "../src/chart/viewport";
const times = (start: number, count: number) => Array.from({ length: count }, (_, i) => start + i);
it("preserves fractional pan/zoom and blank space during live updates", () => {
  const range = { from: -25.75, to: 76.5 };
  expect(anchoredRange(range, times(0, 1000), times(0, 1001))).toEqual(range);
});
it("keeps the same anchor when an older page is loaded without clipping wide zoom", () => {
  const before = { from: -40.5, to: 280.25 };
  const after = anchoredRange(before, times(800, 1000), times(0, 1000));
  expect(after).toEqual({ from: 759.5, to: 1080.25 });
  expect(after.to - after.from).toBe(before.to - before.from);
});
it("preserves location when moving to newer pages or a sliding latest window", () => {
  expect(anchoredRange({ from: 900, to: 1005 }, times(0, 1000), times(800, 1000)))
    .toEqual({ from: 100, to: 205 });
  expect(anchoredRange({ from: 200.3, to: 305.3 }, times(0, 1000), times(1, 1000)))
    .toEqual({ from: 199.3, to: 304.3 });
});
