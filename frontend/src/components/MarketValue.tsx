/** Decimal text remains exact; grouping only inserts separators into the integer text. */
export function MarketValue({ amount, unit, grouped = false }: {
    amount: string;
    unit: string;
    grouped?: boolean;
}) {
    const integer = /^(-?)(\d+)(\.\d+)?$/.exec(amount);
    const displayed = grouped && integer
        ? `${integer[1]}${integer[2]!.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}${integer[3] ?? ""}`
        : amount;
    return <span className="market-value">{displayed}{unit && ` ${unit}`}</span>;
}
export function MarketTime({ value, locale = "th" }: {
    value: string;
    locale?: string;
}) { return <time dateTime={value}>{new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "long", timeZone: "Asia/Bangkok" }).format(new Date(value))}</time>; }
