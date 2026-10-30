const SCALE = 18;
const SCALE_FACTOR = 10n ** BigInt(SCALE);
const MAX_WHOLE_DIGITS = 20;

export type ParsedRiskLimitAmount = Readonly<{
  canonical: string;
  coefficient: bigint;
}>;

/** UI-only exact parser. The server remains the authority and constructs Money. */
export function parseRiskLimitAmount(value: string): ParsedRiskLimitAmount | null {
  const text = value.trim();
  const match = /^\+?(?:(\d+)(?:\.(\d*))?|\.(\d+))$/.exec(text);
  if (!match) return null;

  const whole = (match[1] ?? "0").replace(/^0+(?=\d)/, "");
  const fraction = (match[2] ?? match[3] ?? "").replace(/0+$/, "");
  if (whole.length > MAX_WHOLE_DIGITS || fraction.length > SCALE) return null;

  const fractionCoefficient = fraction === "" ? 0n : BigInt(fraction.padEnd(SCALE, "0"));
  const coefficient = BigInt(whole) * SCALE_FACTOR + fractionCoefficient;
  if (coefficient <= 0n || coefficient >= 10n ** BigInt(MAX_WHOLE_DIGITS + SCALE)) {
    return null;
  }

  return {
    canonical: fraction === "" ? whole : `${whole}.${fraction}`,
    coefficient,
  };
}
