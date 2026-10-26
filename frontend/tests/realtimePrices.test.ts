import { expect, it } from "vitest";
import { decodePrices, acceptPrices } from "../src/realtimePrices";
import { catalog, snapshot } from "./priceFixture";
it("decodes only bounded complete snapshots with string prices and counters", () => {
    expect(decodePrices(snapshot(), catalog()).rows).toHaveLength(2);
    expect(() => decodePrices({ ...snapshot(), rows: [{ ...snapshot().rows[0], amount: 12 }] }, catalog())).toThrow();
    expect(() => decodePrices({ ...snapshot(), schema_version: 2 }, catalog())).toThrow();
});
it("late GET and revisions beyond JS precision cannot roll back a newer stream", () => {
    const newer = decodePrices(snapshot("9007199254740993", "2026-10-07T00:00:02Z"), catalog());
    expect(acceptPrices(newer, decodePrices(snapshot("9007199254740992"), catalog()))).toBe(newer);
    expect(acceptPrices(newer, decodePrices(snapshot("9007199254740994", "2026-10-07T00:00:03Z"), catalog()))).not.toBe(newer);
});
it("a newer reference cannot overwrite a row from an older generation", () => {
    const current = decodePrices(snapshot(), catalog());
    const old = snapshot("99", "2026-10-07T00:00:04Z");
    old.rows[0]!.generation = "0";
    expect(acceptPrices(current, decodePrices(old, catalog()))).toBe(current);
});
it("reference ordering retains microseconds in delayed heartbeat snapshots", () => {
    const newer = decodePrices(snapshot("1", "2026-10-07T00:00:01.000002Z"), catalog());
    expect(acceptPrices(newer, decodePrices(snapshot("1", "2026-10-07T00:00:01.000001Z"), catalog()))).toBe(newer);
});
