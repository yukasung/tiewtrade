"""Feature checks for failure-only E2E fixture evidence."""

import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

import browser_fixture as fixture
from seed_observer import SeedObserver
from sqlalchemy.ext.asyncio import AsyncEngine
from tiewtrade.core.market_data import Timeframe
from tiewtrade.services.market_data.ingestion import RoundSummary


class SeedEvidenceTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.output = Path(tmp.name) / "failure.json"
        self.obs = SeedObserver(self.output)
        self.engine = MagicMock(spec=AsyncEngine)
        self.complete = {("BTC", "1h"): 1000, ("ETH", "1h"): 1000}

    async def run_seed(self) -> None:
        await fixture.seed_rounds(
            self.engine, self.engine, datetime.now(UTC), (Timeframe.H1,), self.obs
        )

    async def test_success_stops_after_one_round(self) -> None:
        with (
            patch("seed_observer.read_counts", AsyncMock(return_value={})),
            patch.object(fixture, "read_counts", AsyncMock(return_value=self.complete)),
            patch.object(fixture, "run_round", AsyncMock(return_value=RoundSummary(2, 2))) as run,
        ):
            await self.run_seed()
        self.assertEqual(run.await_count, 1)
        self.assertFalse(self.output.exists())

    async def test_four_rounds_include_missing_and_extra_series(self) -> None:
        actual = {("BTC", "1h"): 999, ("ETH", "3m"): 1}
        with (
            patch("seed_observer.read_counts", AsyncMock(return_value={})),
            patch.object(fixture, "read_counts", AsyncMock(return_value=actual)),
            patch.object(
                fixture, "run_round", AsyncMock(return_value=RoundSummary(4, 1, 2))
            ) as run,
            self.assertRaisesRegex(RuntimeError, "F12_FIXTURE_REJECTED") as caught,
        ):
            await self.run_seed()
        self.obs.publish(caught.exception)
        report = json.loads(self.output.read_text())
        self.assertEqual(report["initial"], {})
        self.assertEqual(run.await_count, 4)
        self.assertEqual([r["round"] for r in report["rounds"]], [1, 2, 3, 4])
        last = report["rounds"][-1]
        self.assertEqual((last["attempts"], last["stored"], last["stale"]), (4, 1, 2))
        self.assertEqual(last["counts"], {"BTC/1h": 999, "ETH/3m": 1})
        self.assertEqual(report["expected"]["ETH/1h"], 1000)

    async def test_diagnostic_errors_preserve_early_failure(self) -> None:
        self.engine.connect.side_effect = OSError("private")
        await self.obs.sample(self.engine)
        failure = ValueError("original")
        with (
            patch.object(fixture, "run_round", AsyncMock(side_effect=failure)) as run,
            self.assertRaises(ValueError) as caught,
        ):
            try:
                await self.run_seed()
            except ValueError as exc:
                with patch.object(Path, "write_text", side_effect=OSError):
                    self.obs.publish(exc)
                raise
        self.assertIs(caught.exception, failure)
        self.assertEqual(run.await_count, 1)
        self.assertEqual(self.obs.gaps, ["locks:OSError", "baseline:OSError"])
