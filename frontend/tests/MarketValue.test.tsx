import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { MarketTime } from "../src/components/MarketValue";

afterEach(cleanup);

it.each([
    { locale: undefined, expected: "8 ต.ค. 2569 3 นาฬิกา 30 นาที 00 วินาที GMT+7" },
    { locale: "en-GB", expected: "8 Oct 2026, 03:30:00 GMT+7" },
])("displays Bangkok time across the UTC date boundary ($locale)", ({ locale, expected }) => {
    const instant = "2026-10-07T20:30:00Z";
    render(locale === undefined
        ? <MarketTime value={instant} />
        : <MarketTime value={instant} locale={locale} />);
    expect(screen.getByText(expected).getAttribute("datetime")).toBe(instant);
});
