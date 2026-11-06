import { expect, it } from "vitest";
import { isRecord } from "../src/isRecord";

it.each([null, undefined, "value", 1, true, 1n, Symbol("value"), [], () => ({})])(
  "rejects non-record input (%#)", value => {
    expect(isRecord(value)).toBe(false);
  },
);

it("preserves the existing acceptance of objects without inspecting prototypes or normalizing", () => {
  class Intent { amount = "0.123456789012345678"; }
  const nullPrototype: unknown = Object.create(null);
  const values = [{ amount: "0.123456789012345678" }, nullPrototype, new Date(0), new Intent()];
  for (const value of values) {
    if (typeof value !== "object" || value === null) throw new Error("invalid test fixture");
    const prototype: unknown = Object.getPrototypeOf(value);
    const descriptors = Object.getOwnPropertyDescriptors(value);
    Object.freeze(value);
    const frozenDescriptors = Object.getOwnPropertyDescriptors(value);
    expect(isRecord(value)).toBe(true);
    expect(Object.getPrototypeOf(value)).toBe(prototype);
    expect(Object.keys(value)).toEqual(Object.keys(descriptors));
    expect(Object.getOwnPropertyDescriptors(value)).toEqual(frozenDescriptors);
  }
});
