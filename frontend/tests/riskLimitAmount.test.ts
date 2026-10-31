import { describe, expect, it } from "vitest";
import { parseRiskLimitAmount } from "../src/riskLimitAmount";

describe("parseRiskLimitAmount", () => {
  it.each([
    ["0.000000000000000001", "0.000000000000000001", 1n],
    ["1", "1", 1_000_000_000_000_000_000n],
    ["001.2300", "1.23", 1_230_000_000_000_000_000n],
    [".5", "0.5", 500_000_000_000_000_000n],
    ["+5", "5", 5_000_000_000_000_000_000n],
    [" 2.50 ", "2.5", 2_500_000_000_000_000_000n],
  ])("parses %s exactly", (text, canonical, coefficient) => {
    expect(parseRiskLimitAmount(text)).toEqual({ canonical, coefficient });
  });

  it("accepts the largest representable positive value below the boundary", () => {
    expect(parseRiskLimitAmount("99999999999999999999.999999999999999999")).not.toBeNull();
  });

  it.each([
    "", "   ", "0", "0.000", "-1", "value", "1,000", "1e2", "NaN", "Infinity",
    "0.0000000000000000001", "100000000000000000000",
  ])("rejects %s", text => {
    expect(parseRiskLimitAmount(text)).toBeNull();
  });

  it("compares equivalent and long values without Number", () => {
    expect(parseRiskLimitAmount("1")?.coefficient).toBe(parseRiskLimitAmount("1.0000")?.coefficient);
    expect(
      parseRiskLimitAmount("99999999999999999999.999999999999999999")!.coefficient,
    ).toBeGreaterThan(parseRiskLimitAmount("99999999999999999999.999999999999999998")!.coefficient);
  });
});
