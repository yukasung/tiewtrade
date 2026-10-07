import { execFileSync } from "node:child_process";
import { test as base } from "@playwright/test";
import { e2eEnvironment } from "./environment";
export { expect } from "@playwright/test";
/** Matches backend API fixture: isolate test state, keep the real throttle rules active. */
export const test = base.extend<{ throttleIsolation: void }>({
  throttleIsolation: [
    async ({ page }, use) => {
      // Waiting for the browser fixture ensures this is a per-test setup, before any request.
      void page;
      const environment = e2eEnvironment();
      try {
        execFileSync(
          ".venv/bin/python",
          [
            "-B",
            "-c",
            `
import asyncio, os
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import presented_session
async def clear():
    engine = create_engine_for(DatabaseRole.AUTH)
    try:
        async with presented_session(engine, role=DatabaseRole.AUTH) as session:
            actual = (await session.execute("SELECT current_database()")).scalar_one()
            if actual != os.environ["TIEWTRADE_E2E_DATABASE_NAME"]:
                raise RuntimeError("E2E_DATABASE_REJECTED")
            await session.execute("DELETE FROM auth_throttle")
    finally:
        await engine.dispose()
asyncio.run(clear())
`,
          ],
          { cwd: "../backend", stdio: "pipe", env: environment },
        );
      } catch {
        // Child errors can contain connection details; do not forward stderr or URLs.
        throw new Error("E2E_THROTTLE_RESET_FAILED");
      }
      await use();
    },
    { auto: true },
  ],
});
