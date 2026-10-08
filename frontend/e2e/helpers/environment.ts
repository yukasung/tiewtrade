const roles = ["API", "AUTH", "ENGINE", "ENGINE_SCAN", "MIGRATOR", "MARKET_DATA"] as const;

/** Fail before starting servers or connecting to any database. Never echo URLs. */
export function e2eEnvironment(
  source: Record<string, string | undefined> = process.env,
): Record<string, string> {
  const name = source.TIEWTRADE_E2E_DATABASE_NAME;
  if (!name || !/^tiewtrade_e2e(?:_[a-zA-Z0-9]+)*$/.test(name)) {
    throw new Error("E2E_DATABASE_REJECTED");
  }
  let target: string | undefined;
  const configuredRoles = roles;
  for (const role of configuredRoles) {
    try {
      const url = new URL(source[`TIEWTRADE_DATABASE_URL_${role}`] ?? "");
      const address = `${url.hostname}:${url.port || "5432"}`;
      if (
        url.protocol !== "postgresql+asyncpg:" ||
        !["127.0.0.1", "localhost", "[::1]"].includes(url.hostname) ||
        url.pathname !== `/${name}` ||
        url.search ||
        url.hash ||
        url.username !== `tiewtrade_${role.toLowerCase()}` ||
        (target !== undefined && target !== address)
      ) {
        throw new Error("E2E_DATABASE_REJECTED");
      }
      target = address;
    } catch {
      throw new Error("E2E_DATABASE_REJECTED");
    }
  }
  for (const role of ["API", "MARKET_DATA"]) {
    try {
      const redis = new URL(source[`TIEWTRADE_REDIS_URL_${role}`] ?? "");
      if (redis.protocol !== "redis:" || !["127.0.0.1", "localhost", "[::1]"].includes(redis.hostname) || redis.search || redis.hash) {
        throw new Error("E2E_REDIS_REJECTED");
      }
    } catch {
      throw new Error("E2E_REDIS_REJECTED");
    }
  }
  const environment: Record<string, string> = {};
  for (const [key, value] of Object.entries(source)) {
    if (value !== undefined) environment[key] = value;
  }
  return { ...environment, API_URL: "http://127.0.0.1:8000" };
}
