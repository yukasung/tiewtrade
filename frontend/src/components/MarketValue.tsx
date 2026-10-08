/** Decimal text remains exact; no money arithmetic or conversion to Number. */
export function MarketValue({ amount, unit }: {
    amount: string;
    unit: string;
}) { return <span className="market-value">{amount} {unit}</span>; }
export function MarketTime({ value, locale = "th" }: {
    value: string;
    locale?: string;
}) { return <time dateTime={value}>{new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "long", timeZone: "Asia/Bangkok" }).format(new Date(value))}</time>; }
