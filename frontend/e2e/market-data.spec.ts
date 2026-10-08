import { execFileSync } from "node:child_process";
import { e2eEnvironment } from "./helpers/environment";
import { expect, test } from "./helpers/test";
import { PASSWORD } from "./helpers/totp";
import type { components } from "../src/api-types";

type CandleHistory = components["schemas"]["CandleHistoryView"];

function ingest(start: string, end: string): void {
  execFileSync(
    ".venv/bin/python",
    ["-B", "-c", `
import asyncio, sys
from datetime import UTC, datetime
from tiewtrade.core.market_data import Candle, CandleFinality, CandleWindow, Timeframe, expected_opens
from tiewtrade.core.money import Money, Quantity
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.services.market_data.ingestion import run_round
from tiewtrade.venues import FakeVenue, Symbol
from tiewtrade.venues.candles import CandlePage
async def run():
    now = datetime.now(UTC)
    window = CandleWindow(datetime.fromisoformat(sys.argv[1]), datetime.fromisoformat(sys.argv[2]))
    rows = tuple(Candle('BTC','USDT',Timeframe.M1,opened,opened+Timeframe.M1.span,
        Money.of('123.000000000000000001','USDT'),Money.of('124','USDT'),
        Money.of('122','USDT'),Money.of('123.5','USDT'),Quantity.of('0.000000000000000001','BTC'),
        CandleFinality.UNCONFIRMED,now) for opened in expected_opens(window,Timeframe.M1))
    venue = FakeVenue()
    venue.queue_candle_pages([CandlePage(Symbol('BTC','USDT'),Timeframe.M1,window,rows,now)])
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        summary = await run_round(engine,venue,'e2e-market-worker',now)
        assert summary.stored == len(rows), summary
    finally:
        await engine.dispose()
asyncio.run(run())
`, start, end],
    { cwd: "../backend", stdio: "pipe", env: e2eEnvironment() },
  );
}

// The shared public demand queue survives previous E2E runs, including unconfirmed repairs.
// Reset only these fixtures after the existing isolation guard validates the disposable target.
test.beforeEach(() => {
  execFileSync(".venv/bin/python", ["-B", "-c", `
import asyncio
from sqlalchemy import text
from tiewtrade.infra.db import DatabaseRole, create_engine_for
async def clear():
    engine = create_engine_for(DatabaseRole.MIGRATOR)
    try:
        async with engine.begin() as connection:
            await connection.execute(text('TRUNCATE market_candle_demand, market_candles'))
    finally:
        await engine.dispose()
asyncio.run(clear())
`], { cwd: "../backend", stdio: "pipe", env: e2eEnvironment() });
});

test("market history request → actual worker → exact stored observations", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("switch-mode").click();
  await page.getByLabel("อีเมล").fill(`e2e-candles-${String(Date.now())}@example.com`);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("signed-in")).toBeVisible();

  const end = new Date(Math.floor(Date.now() / 60000) * 60000 - 60000).toISOString();
  const start = new Date(Date.parse(end) - 180000).toISOString();
  const series = { base: "BTC", quote: "USDT", timeframe: "1m", start, end };
  const path = `/api/market-data/candles?${new URLSearchParams(series).toString()}`;
  const first = await page.request.get(path);
  expect(first.status()).toBe(200);
  const missing = await first.json() as CandleHistory;
  expect(missing.coverage).toBe("INCOMPLETE");

  const csrf = (await page.context().cookies()).find((cookie) => cookie.name === "tiewtrade_csrf");
  expect(csrf).toBeDefined();
  const headers = { "X-CSRF-Token": csrf?.value ?? "" };
  const requested = await page.request.post("/api/market-data/candles/requests", { data: series, headers });
  expect(requested.status()).toBe(202);
  const repeated = await page.request.post("/api/market-data/candles/requests", { data: series, headers });
  expect(repeated.status()).toBe(202);

  ingest(start, end);
  const result = await page.request.get(path);
  expect(result.status()).toBe(200);
  const history = await result.json() as CandleHistory;
  expect(history.coverage).toBe("PRESENT");
  expect(history.gaps).toEqual([]);
  expect(history.rows).toHaveLength(3);
  expect(history.rows[0]?.open).toBe("123.000000000000000001");
  expect(history.rows[0]?.volume).toBe("0.000000000000000001");
  expect(history.rows.every((row: { finality: string }) => row.finality === "UNCONFIRMED")).toBe(true);
});
