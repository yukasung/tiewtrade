// @vitest-environment node
import { describe, expect, it } from "vitest";
import { e2eEnvironment } from "../e2e/helpers/environment";

function isolated(): Record<string, string | undefined> {
  const env: Record<string, string | undefined> = { TIEWTRADE_E2E_DATABASE_NAME: "tiewtrade_e2e_review" };
  for (const role of ["API", "AUTH", "ENGINE", "ENGINE_SCAN", "MIGRATOR", "MARKET_DATA"]) {
    env[`TIEWTRADE_DATABASE_URL_${role}`] =
      `postgresql+asyncpg://tiewtrade_${role.toLowerCase()}:synthetic@127.0.0.1:55432/tiewtrade_e2e_review`;
  }
  env.TIEWTRADE_REDIS_URL_API = "redis://127.0.0.1:56379/0";
  env.TIEWTRADE_REDIS_URL_MARKET_DATA = "redis://127.0.0.1:56379/0";
  return env;
}

describe("E2E destructive fixture isolation", () => {
  it.each([undefined, "redis://remote.invalid:6379/0", "redis://localhost:56379/0?host=remote.invalid", "redis://localhost:56379/0#foreign"])(
    "rejects unsafe Redis targets without exposing URLs %s", (url) => {
      const env = isolated();
      env.TIEWTRADE_REDIS_URL_API = url;
      expect(() => e2eEnvironment(env)).toThrow(/^E2E_REDIS_REJECTED$/);
    },
  );
  it("accepts explicit isolated roles and pins the frontend to its own API", () => {
    const env = isolated();
    env.API_URL = "https://unrelated.invalid";
    const result = e2eEnvironment(env);
    expect(result.TIEWTRADE_DATABASE_URL_AUTH).toBe(env.TIEWTRADE_DATABASE_URL_AUTH);
    expect(result.API_URL).toBe("http://127.0.0.1:8000");
    expect(env.API_URL).toBe("https://unrelated.invalid");
  });

  it.each([undefined, "", "tiewtrade", "production", "tiewtrade_e2e/other"])(
    "rejects absent or unsafe database declaration %s",
    (name) => {
      const env = isolated();
      env.TIEWTRADE_E2E_DATABASE_NAME = name;
      expect(() => e2eEnvironment(env)).toThrow("E2E_DATABASE_REJECTED");
    },
  );

  it.each([
    undefined,
    "not-a-url-synthetic-secret",
    "postgresql+asyncpg://tiewtrade_auth:synthetic@127.0.0.1:55432/tiewtrade",
    "postgresql+asyncpg://tiewtrade_auth:synthetic@remote.invalid:55432/tiewtrade_e2e_review",
    "postgresql+asyncpg://tiewtrade_auth:synthetic@127.0.0.1:5432/tiewtrade_e2e_review",
    "postgresql+asyncpg://tiewtrade_auth:synthetic@127.0.0.1:55432/tiewtrade_e2e_review?host=remote.invalid",
    "postgresql+asyncpg://postgres:synthetic@127.0.0.1:55432/tiewtrade_e2e_review",
  ])("rejects missing, foreign or overridden AUTH target without echoing secrets", (url) => {
    const env = isolated();
    env.TIEWTRADE_DATABASE_URL_AUTH = url;
    expect(() => e2eEnvironment(env)).toThrow(/^E2E_DATABASE_REJECTED$/);
  });

  it.each(["API", "ENGINE", "ENGINE_SCAN", "MIGRATOR", "MARKET_DATA"])(
    "rejects a different database for %s",
    (role) => {
      const env = isolated();
      env[`TIEWTRADE_DATABASE_URL_${role}`] =
        `postgresql+asyncpg://tiewtrade_${role.toLowerCase()}:synthetic@127.0.0.1:55432/tiewtrade`;
      expect(() => e2eEnvironment(env)).toThrow(/^E2E_DATABASE_REJECTED$/);
    },
  );
});
