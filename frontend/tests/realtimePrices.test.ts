import { expect, it } from "vitest";
import { decodePrices, acceptPrices } from "../src/realtimePrices";
import { snapshot } from "./priceFixture";
it("decodes only bounded complete snapshots with string prices and counters", () => {
    expect(decodePrices(snapshot()).rows).toHaveLength(2);
    expect(() => decodePrices({ ...snapshot(), rows: [{ ...snapshot().rows[0], amount: 12 }] })).toThrow();
    expect(() => decodePrices({ ...snapshot(), schema_version: 2 })).toThrow();
});
it("late GET and revisions beyond JS precision cannot roll back a newer stream", () => {
    const newer = decodePrices(snapshot("9007199254740993", "2026-10-07T00:00:02Z"));
    expect(acceptPrices(newer, decodePrices(snapshot("9007199254740992")))).toBe(newer);
    expect(acceptPrices(newer, decodePrices(snapshot("9007199254740994", "2026-10-07T00:00:03Z")))).not.toBe(newer);
});
it("a newer reference cannot overwrite a row from an older generation", () => {
    const current = decodePrices(snapshot());
    const old = snapshot("99", "2026-10-07T00:00:04Z");
    old.rows[0]!.generation = "0";
    expect(acceptPrices(current, decodePrices(old))).toBe(current);
});
it("reference ordering retains microseconds in delayed heartbeat snapshots", () => {
    const newer = decodePrices(snapshot("1", "2026-10-07T00:00:01.000002Z"));
    expect(acceptPrices(newer, decodePrices(snapshot("1", "2026-10-07T00:00:01.000001Z")))).toBe(newer);
});
