/** Translate viewport indices using a candle shared by both bounded pages.
 * Unlike visible time ranges, logical ranges retain fractional offsets and empty space.
 */
export function anchoredRange(
  range: { from: number; to: number }, previous: readonly number[], next: readonly number[],
): { from: number; to: number } {
  const indices = new Map(next.map((time, index) => [time, index]));
  const center = Math.max(0, Math.min(previous.length - 1, Math.floor((range.from + range.to) / 2)));
  for (let offset = 0; offset < previous.length; offset += 1) {
    for (const index of offset ? [center - offset, center + offset] : [center]) {
      const time = previous[index];
      const nextIndex = time === undefined ? undefined : indices.get(time);
      if (nextIndex !== undefined) {
        const shift = nextIndex - index;
        return { from: range.from + shift, to: range.to + shift };
      }
    }
  }
  return range;
}
