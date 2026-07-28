# Binance Market Data HTTP Errors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ทำให้ Public Binance Market Data Runtime แยก retryable, rate-limited และ fatal source failures พร้อมเคารพ `Retry-After` โดยไม่เสี่ยง retry ถี่จน IP ถูกระงับ

**Architecture:** `market_data` เป็นเจ้าของ source-error contract และ runtime policy ส่วน `integrations/binance` แปล HTTP, transport และ payload semantics เป็น contract นั้น Runtime เพิ่ม `RATE_LIMITED` state, ใช้ scheduler คำนวณ delay แบบ deterministic และ fail closed ทันทีเมื่อ fatal

**Tech Stack:** Python 3.12+, `asyncio`, `aiohttp`, stdlib `datetime`/`email.utils`, pytest, Ruff, mypy strict

## Global Constraints

- ห้ามเรียก Binance จริง ใช้ fake response, fake session, fake source และ fake scheduler เท่านั้น
- ห้ามแตะ credentials, Private API, strategy, execution, persistence หรือ Session policy
- `418` และ `429` ต้องใช้ `Retry-After` หรือ fallback `60.0` วินาที ห้ามใช้ `1.0`, `2.0`, `4.0`
- `5xx`, timeout และ connection failure ใช้ bounded backoff `(1.0, 2.0, 4.0)`
- `4xx` อื่นและ payload ผิดรูปแบบต้อง fail closed โดยไม่ retry
- รองรับ `Retry-After` ทั้ง delta-seconds และ HTTP-date
- ใช้ TDD ทุก behavior: test ใหม่ต้อง fail ด้วยเหตุผลที่คาดไว้ก่อนแก้ production code

---

## File Structure

- Create: `src/tiewtrade/market_data/source_errors.py` — consumer-owned source failure contract และ retry directive
- Create: `tests/unit/market_data/test_source_errors.py` — contract/immutability/UTC validation tests
- Modify: `src/tiewtrade/market_data/runtime_state.py` — เพิ่ม rate-limit state และ diagnostic reasons
- Modify: `tests/unit/market_data/test_runtime_state.py` — ยืนยัน enum contract ใหม่
- Modify: `src/tiewtrade/integrations/binance/public_market_data.py` — จำแนก HTTP/transport/payload และ parse `Retry-After`
- Modify: `tests/unit/integrations/binance/test_public_market_data.py` — fake HTTP classification matrix
- Modify: `src/tiewtrade/market_data/runtime.py` — bounded retry, rate-limit delay, fatal fail-closed และ stop semantics
- Modify: `tests/unit/market_data/test_runtime.py` — runtime policy/state tests

### Task 1: Define the consumer-owned source error contract

**Files:**
- Create: `src/tiewtrade/market_data/source_errors.py`
- Create: `tests/unit/market_data/test_source_errors.py`
- Modify: `src/tiewtrade/market_data/runtime_state.py`
- Modify: `tests/unit/market_data/test_runtime_state.py`

**Interfaces:**
- Produces: `RetryAfter = timedelta | datetime`
- Produces: `MarketDataRetryableError(message: str)`
- Produces: `MarketDataTimeoutError(message: str)` ซึ่งเป็น retryable subtype ที่รักษา
  public timeout semantics โดยไม่ผูก Runtime กับ Binance
- Produces: `MarketDataRateLimitError(message: str, *, retry_after: RetryAfter | None)` พร้อม read-only `retry_after`
- Produces: `MarketDataFatalError(message: str)`
- Produces: `MarketDataRuntimeState.RATE_LIMITED`
- Produces: `MarketDataRuntimeReason.RATE_LIMITED`, `RATE_LIMIT_EXHAUSTED`, `SOURCE_FATAL`

- [ ] **Step 1: Write failing source-error and state tests**

สร้าง `tests/unit/market_data/test_source_errors.py`:

```python
from datetime import UTC, datetime, timedelta

import pytest

from tiewtrade.market_data.source_errors import (
    MarketDataFatalError,
    MarketDataRateLimitError,
    MarketDataRetryableError,
    MarketDataTimeoutError,
)


def test_source_error_types_have_distinct_actions() -> None:
    assert not issubclass(MarketDataFatalError, MarketDataRetryableError)
    assert not issubclass(MarketDataRateLimitError, MarketDataRetryableError)


@pytest.mark.parametrize(
    "retry_after",
    [timedelta(seconds=30), datetime(2026, 1, 1, tzinfo=UTC), None],
)
def test_rate_limit_error_preserves_retry_directive(
    retry_after: timedelta | datetime | None,
) -> None:
    error = MarketDataRateLimitError("rate limited", retry_after=retry_after)

    assert error.retry_after == retry_after


def test_rate_limit_error_rejects_naive_http_date() -> None:
    with pytest.raises(ValueError, match="retry_after datetime must use UTC"):
        MarketDataRateLimitError(
            "rate limited",
            retry_after=datetime(2026, 1, 1),
        )
```

เพิ่มใน `tests/unit/market_data/test_runtime_state.py`:

```python
def test_runtime_state_exposes_rate_limit_diagnostics() -> None:
    assert MarketDataRuntimeState.RATE_LIMITED == "rate_limited"
    assert MarketDataRuntimeReason.RATE_LIMITED == "rate_limited"
    assert MarketDataRuntimeReason.RATE_LIMIT_EXHAUSTED == "rate_limit_exhausted"
    assert MarketDataRuntimeReason.SOURCE_FATAL == "source_fatal"
```

- [ ] **Step 2: Run tests to verify RED**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/market_data/test_source_errors.py \
  tests/unit/market_data/test_runtime_state.py -q
```

Expected: collection FAIL เพราะ `market_data.source_errors` และ enum values ยังไม่มี

- [ ] **Step 3: Implement the minimal source-error contract**

สร้าง `src/tiewtrade/market_data/source_errors.py`:

```python
from datetime import datetime, timedelta

RetryAfter = timedelta | datetime


class MarketDataSourceError(Exception):
    """Base failure exposed by a market-data source adapter."""


class MarketDataRetryableError(MarketDataSourceError):
    """A transient source failure eligible for bounded retry."""


class MarketDataFatalError(MarketDataSourceError):
    """A source failure that cannot succeed through retry."""


class MarketDataRateLimitError(MarketDataSourceError):
    """A source refusal that requires a provider-directed pause."""

    def __init__(
        self,
        message: str,
        *,
        retry_after: RetryAfter | None,
    ) -> None:
        if isinstance(retry_after, datetime) and (
            retry_after.tzinfo is None or retry_after.utcoffset() != timedelta(0)
        ):
            raise ValueError("retry_after datetime must use UTC")
        super().__init__(message)
        self._retry_after = retry_after

    @property
    def retry_after(self) -> RetryAfter | None:
        return self._retry_after
```

เพิ่มใน enum ของ `src/tiewtrade/market_data/runtime_state.py`:

```python
class MarketDataRuntimeState(StrEnum):
    # existing values remain unchanged
    RATE_LIMITED = "rate_limited"


class MarketDataRuntimeReason(StrEnum):
    # existing values remain unchanged
    RATE_LIMITED = "rate_limited"
    RATE_LIMIT_EXHAUSTED = "rate_limit_exhausted"
    SOURCE_FATAL = "source_fatal"
```

- [ ] **Step 4: Run focused tests to verify GREEN**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/market_data/test_source_errors.py \
  tests/unit/market_data/test_runtime_state.py -q
```

Expected: tests ทั้งหมด PASS

- [ ] **Step 5: Run focused static checks**

```bash
../../.venv/bin/python -m ruff check \
  src/tiewtrade/market_data/source_errors.py \
  src/tiewtrade/market_data/runtime_state.py \
  tests/unit/market_data/test_source_errors.py \
  tests/unit/market_data/test_runtime_state.py
../../.venv/bin/python -m mypy src
```

Expected: ทุกคำสั่ง exit `0`

- [ ] **Step 6: Commit the tested contract**

```bash
git add \
  src/tiewtrade/market_data/source_errors.py \
  src/tiewtrade/market_data/runtime_state.py \
  tests/unit/market_data/test_source_errors.py \
  tests/unit/market_data/test_runtime_state.py
git commit -m "feat: define market-data source failures"
```

### Task 2: Classify Binance HTTP and transport failures

**Files:**
- Modify: `tests/unit/integrations/binance/test_public_market_data.py`
- Modify: `src/tiewtrade/integrations/binance/public_market_data.py`

**Interfaces:**
- Consumes: source-error classes และ `RetryAfter` จาก Task 1
- Produces: `_parse_retry_after(value: str | None) -> RetryAfter | None`
- Produces: `BinancePublicMarketData` ที่ไม่ส่ง HTTP status code ดิบข้าม adapter boundary

- [ ] **Step 1: Extend the fake response with headers**

แก้ `FakeResponse` ใน `tests/unit/integrations/binance/test_public_market_data.py`:

```python
class FakeResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        payload: object = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self._payload = payload
        self.headers = headers or {}
```

และ import domain errors:

```python
from datetime import UTC, datetime, timedelta

from tiewtrade.market_data.source_errors import (
    MarketDataFatalError,
    MarketDataRateLimitError,
    MarketDataRetryableError,
    MarketDataTimeoutError,
)
```

- [ ] **Step 2: Write failing HTTP classification tests**

แทน `test_rest_failures_raise_stable_payload_error` ด้วย tests ต่อไปนี้:

```python
def load_one(source: BinancePublicMarketData) -> None:
    asyncio.run(
        source.load_recent(
            config(),
            count=1,
            completed_before=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )


def test_429_preserves_delta_seconds_retry_after() -> None:
    source, _ = source_with(
        rest_pages=[
            FakeResponse(
                status=429,
                headers={"Retry-After": "45"},
            )
        ]
    )

    with pytest.raises(MarketDataRateLimitError) as captured:
        load_one(source)

    assert captured.value.retry_after == timedelta(seconds=45)


def test_429_preserves_http_date_retry_after() -> None:
    source, _ = source_with(
        rest_pages=[
            FakeResponse(
                status=429,
                headers={"Retry-After": "Thu, 01 Jan 2026 00:01:00 GMT"},
            )
        ]
    )

    with pytest.raises(MarketDataRateLimitError) as captured:
        load_one(source)

    assert captured.value.retry_after == datetime(
        2026, 1, 1, 0, 1, tzinfo=UTC
    )


@pytest.mark.parametrize("header", [None, "", "not-a-date"])
def test_429_without_valid_retry_after_uses_no_directive(
    header: str | None,
) -> None:
    headers = {} if header is None else {"Retry-After": header}
    source, _ = source_with(
        rest_pages=[FakeResponse(status=429, headers=headers)]
    )

    with pytest.raises(MarketDataRateLimitError) as captured:
        load_one(source)

    assert captured.value.retry_after is None


@pytest.mark.parametrize("status", [418, 429])
def test_rate_limit_statuses_raise_rate_limit_error(status: int) -> None:
    source, _ = source_with(rest_pages=[FakeResponse(status=status)])

    with pytest.raises(MarketDataRateLimitError):
        load_one(source)


def test_400_raises_fatal_error() -> None:
    source, _ = source_with(rest_pages=[FakeResponse(status=400)])

    with pytest.raises(MarketDataFatalError):
        load_one(source)


def test_503_raises_retryable_error() -> None:
    source, _ = source_with(rest_pages=[FakeResponse(status=503)])

    with pytest.raises(MarketDataRetryableError):
        load_one(source)


def test_transport_failure_raises_retryable_error() -> None:
    source, _ = source_with(
        rest_pages=[
            FakeResponse(payload=aiohttp.ClientConnectionError("offline"))
        ]
    )

    with pytest.raises(MarketDataRetryableError):
        load_one(source)


@pytest.mark.parametrize(
    "payload",
    [{"code": -1121, "msg": "invalid symbol"}, ValueError("bad JSON")],
)
def test_invalid_rest_payload_raises_fatal_error(payload: object) -> None:
    source, _ = source_with(rest_pages=[FakeResponse(payload=payload)])

    with pytest.raises(MarketDataFatalError):
        load_one(source)
```

- [ ] **Step 3: Run tests to verify RED**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/binance/test_public_market_data.py -q
```

Expected: FAIL เพราะ adapter ยังยุบ failures เป็น `BinanceMarketDataPayloadError`

- [ ] **Step 4: Implement Retry-After parsing and REST classification**

เพิ่ม imports และ helper ใน `src/tiewtrade/integrations/binance/public_market_data.py`:

```python
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

from tiewtrade.market_data.source_errors import (
    MarketDataFatalError,
    MarketDataRateLimitError,
    MarketDataRetryableError,
    RetryAfter,
)


def _parse_retry_after(value: str | None) -> RetryAfter | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    try:
        seconds = int(normalized)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(normalized)
        except (TypeError, ValueError, OverflowError):
            return None
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(UTC)
    if seconds < 0:
        return None
    return timedelta(seconds=seconds)
```

แยก status ก่อนอ่าน JSON ใน `_load_rest_page`:

```python
if response.status in {418, 429}:
    raise MarketDataRateLimitError(
        "Binance market data is rate limited",
        retry_after=_parse_retry_after(response.headers.get("Retry-After")),
    )
if 500 <= response.status < 600:
    raise MarketDataRetryableError(
        "Binance market-data service is unavailable"
    )
if not 200 <= response.status < 300:
    raise MarketDataFatalError(
        "Binance rejected the market-data request"
    )
```

จัด exception mapping ของ `_load_rest_page` และ `_stream_completed`:

```python
except (MarketDataRetryableError, MarketDataRateLimitError, MarketDataFatalError):
    raise
except (aiohttp.ClientError, TimeoutError) as error:
    raise MarketDataRetryableError(
        "Binance market-data transport failed"
    ) from error
except (
    BinanceMarketDataPayloadError,
    json.JSONDecodeError,
    TypeError,
    ValueError,
) as error:
    raise MarketDataFatalError(_INVALID_RESPONSE_MESSAGE) from error
```

คง `BinanceMarketDataPayloadError` ไว้ภายใน endpoint/kline parsing แต่ห้ามปล่อยข้าม
`BinancePublicMarketData` boundary

- [ ] **Step 5: Run focused tests to verify GREEN**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/binance/test_public_market_data.py \
  tests/unit/integrations/binance/test_kline_parser.py \
  tests/unit/integrations/binance/test_public_endpoints.py -q
```

Expected: tests ทั้งหมด PASS

- [ ] **Step 6: Run focused static checks and commit**

```bash
../../.venv/bin/python -m ruff check \
  src/tiewtrade/integrations/binance/public_market_data.py \
  tests/unit/integrations/binance/test_public_market_data.py
../../.venv/bin/python -m mypy src
git add \
  src/tiewtrade/integrations/binance/public_market_data.py \
  tests/unit/integrations/binance/test_public_market_data.py
git commit -m "fix: classify Binance market-data failures"
```

Expected: checks exit `0` และ commit สำเร็จ

### Task 3: Apply bounded runtime policies by error action

> **User-approved resolution (2026-07-28):** หลัง provider delay ต้อง transition
> `RATE_LIMITED -> RECONNECTING`; timeout ระหว่าง warm-up ทั้ง source attempts และ
> pipeline deadline ต้องคง public reason `WARM_UP_TIMEOUT`; และ Stop Session ต้อง
> ยกเลิกการรอ `Retry-After` ได้โดยรักษา close-once กับ `STOPPED` semantics

**Files:**
- Modify: `tests/unit/market_data/test_runtime.py`
- Modify: `src/tiewtrade/market_data/runtime.py`

**Interfaces:**
- Consumes: source errors จาก Task 1 และ adapter behavior จาก Task 2
- Produces: `_retry_after_seconds(error: MarketDataRateLimitError) -> float`
- Produces: source-operation retry ที่ใช้ scheduler และคง cancellation semantics
- Produces: fatal → `FAILED_CLOSED/SOURCE_FATAL`; exhausted rate limit → `FAILED_CLOSED/RATE_LIMIT_EXHAUSTED`

- [ ] **Step 1: Add controllable failing sources**

เพิ่มใน `tests/unit/market_data/test_runtime.py`:

```python
from tiewtrade.market_data.source_errors import (
    MarketDataFatalError,
    MarketDataRateLimitError,
    MarketDataRetryableError,
)


class WarmUpFailureSource(FakeSource):
    def __init__(self, failures: Iterable[Exception]) -> None:
        super().__init__(recent=warm_up_candles(), live=[candle_at(15)])
        self._failures = iter(failures)
        self.load_count = 0

    async def load_recent(
        self,
        config: MarketDataConfig,
        *,
        count: int,
        completed_before: datetime,
    ) -> tuple[Candle, ...]:
        self.load_count += 1
        try:
            error = next(self._failures)
        except StopIteration:
            return await super().load_recent(
                config,
                count=count,
                completed_before=completed_before,
            )
        raise error


class StreamFailureSource(FakeSource):
    def __init__(self, failures: Iterable[Exception]) -> None:
        super().__init__(recent=warm_up_candles())
        self._failures = iter(failures)
        self.stream_count = 0

    def stream_completed(self, config: MarketDataConfig) -> AsyncIterator[Candle]:
        self.stream_count += 1
        try:
            error = next(self._failures)
        except StopIteration:
            return self._stream_completed()
        raise error


class BackfillFailureSource(FakeSource):
    def __init__(self, failures: Iterable[Exception]) -> None:
        super().__init__(
            recent=warm_up_candles(),
            live=[candle_at(20)],
            ranges={
                (candle_at(15).open_time, candle_at(25).open_time): (
                    candle_at(15),
                    candle_at(20),
                )
            },
        )
        self._failures = iter(failures)

    async def load_range(
        self,
        config: MarketDataConfig,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]:
        try:
            error = next(self._failures)
        except StopIteration:
            return await super().load_range(config, start=start, end=end)
        raise error
```

- [ ] **Step 2: Write failing fatal and retryable tests**

```python
def test_fatal_warm_up_failure_fails_closed_without_retry() -> None:
    source = WarmUpFailureSource([MarketDataFatalError("bad symbol")])
    scheduler = FakeScheduler()
    runtime = runtime_for(source, RecordingSink(), scheduler=scheduler)

    asyncio.run(runtime.run())

    assert source.load_count == 1
    assert scheduler.sleeps == []
    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_FATAL


def test_retryable_warm_up_failure_uses_bounded_backoff_then_recovers() -> None:
    source = WarmUpFailureSource([MarketDataRetryableError("503")])
    scheduler = FakeScheduler()
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(run_until_sink_receives(runtime, sink, count=1))

    assert source.load_count == 2
    assert scheduler.sleeps == [1.0]
```

Expected final runtime may fail later after the fake live stream ends; assertions focus on warm-up retry policy

- [ ] **Step 3: Write failing rate-limit tests**

```python
def test_rate_limit_uses_delta_seconds_not_reconnect_backoff() -> None:
    source = WarmUpFailureSource(
        [
            MarketDataRateLimitError(
                "429",
                retry_after=timedelta(seconds=45),
            )
        ]
    )
    scheduler = FakeScheduler()
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(run_until_sink_receives(runtime, sink, count=1))

    assert scheduler.sleeps[0] == 45.0
    assert MarketDataRuntimeState.RATE_LIMITED in runtime.visited_states


def test_rate_limit_http_date_uses_scheduler_clock() -> None:
    scheduler = FakeScheduler(now=_NOW)
    source = WarmUpFailureSource(
        [
            MarketDataRateLimitError(
                "429",
                retry_after=_NOW + timedelta(seconds=90),
            )
        ]
    )
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(run_until_sink_receives(runtime, sink, count=1))

    assert scheduler.sleeps[0] == 90.0


def test_rate_limit_without_directive_uses_sixty_second_fallback() -> None:
    source = WarmUpFailureSource(
        [MarketDataRateLimitError("429", retry_after=None)]
    )
    scheduler = FakeScheduler()
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(run_until_sink_receives(runtime, sink, count=1))

    assert scheduler.sleeps[0] == 60.0


def test_repeated_rate_limit_fails_closed_without_one_two_four_backoff() -> None:
    source = WarmUpFailureSource(
        [MarketDataRateLimitError("429", retry_after=None)] * 4
    )
    scheduler = FakeScheduler()
    runtime = runtime_for(source, RecordingSink(), scheduler=scheduler)

    asyncio.run(runtime.run())

    assert scheduler.sleeps == [60.0, 60.0, 60.0]
    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.RATE_LIMIT_EXHAUSTED


def test_rate_limited_backfill_uses_provider_delay_then_recovers() -> None:
    source = BackfillFailureSource(
        [MarketDataRateLimitError("429", retry_after=None)]
    )
    scheduler = FakeScheduler(now=datetime(2026, 1, 1, 0, 25, tzinfo=UTC))
    sink = RecordingSink()
    runtime = runtime_for(source, sink, scheduler=scheduler)

    asyncio.run(
        run_until_sink_receives_or_runtime_stops(runtime, sink, count=2)
    )

    assert scheduler.sleeps == [60.0]
    assert MarketDataRuntimeState.RATE_LIMITED in runtime.visited_states
    assert sink.live_candles == [candle_at(15), candle_at(20)]


def test_fatal_stream_failure_does_not_reconnect() -> None:
    source = StreamFailureSource([MarketDataFatalError("bad request")])
    scheduler = FakeScheduler()
    runtime = runtime_for(source, RecordingSink(), scheduler=scheduler)

    asyncio.run(runtime.run())

    assert scheduler.sleeps == []
    assert runtime.snapshot.reason is MarketDataRuntimeReason.SOURCE_FATAL


def test_rate_limited_stream_exhausts_only_provider_delays() -> None:
    source = StreamFailureSource(
        [MarketDataRateLimitError("429", retry_after=None)] * 4
    )
    scheduler = FakeScheduler()
    runtime = runtime_for(source, RecordingSink(), scheduler=scheduler)

    asyncio.run(runtime.run())

    assert scheduler.sleeps == [60.0, 60.0, 60.0]
    assert runtime.snapshot.reason is MarketDataRuntimeReason.RATE_LIMIT_EXHAUSTED
```

- [ ] **Step 4: Run new runtime tests to verify RED**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/market_data/test_runtime.py \
  -k "fatal_warm_up or retryable_warm_up or rate_limit" -q
```

Expected: FAIL เพราะ Runtime ยังยุบ source failures เป็น `SOURCE_ERROR`

- [ ] **Step 5: Implement scheduler-owned source retry policy**

เพิ่ม imports/constants ใน `src/tiewtrade/market_data/runtime.py`:

```python
from collections.abc import AsyncIterator, Awaitable, Callable

from tiewtrade.market_data.source_errors import (
    MarketDataFatalError,
    MarketDataRateLimitError,
    MarketDataRetryableError,
    MarketDataTimeoutError,
)

_RATE_LIMIT_FALLBACK_SECONDS = 60.0
```

เพิ่ม helpers ใน `MarketDataRuntime`:

```python
def _retry_after_seconds(self, error: MarketDataRateLimitError) -> float:
    retry_after = error.retry_after
    if isinstance(retry_after, timedelta):
        return max(0.0, retry_after.total_seconds())
    if isinstance(retry_after, datetime):
        return max(
            0.0,
            (retry_after - self._scheduler.now()).total_seconds(),
        )
    return _RATE_LIMIT_FALLBACK_SECONDS

async def _run_source_operation(
    self,
    operation: Callable[[], Awaitable[_T]],
    *,
    timeout: float,
) -> _T:
    last_error: Exception | None = None
    for attempt in range(len(_RECONNECT_DELAYS_SECONDS) + 1):
        try:
            return await self._scheduler.wait_for(operation(), timeout)
        except MarketDataFatalError:
            raise
        except MarketDataRateLimitError as error:
            last_error = error
            self._transition(
                MarketDataRuntimeState.RATE_LIMITED,
                MarketDataRuntimeReason.RATE_LIMITED,
            )
            if attempt == len(_RECONNECT_DELAYS_SECONDS):
                raise
            await self._scheduler.sleep(self._retry_after_seconds(error))
            self._transition(
                MarketDataRuntimeState.RECONNECTING,
                MarketDataRuntimeReason.RATE_LIMITED,
            )
        except (MarketDataRetryableError, TimeoutError) as error:
            last_error = error
            if attempt == len(_RECONNECT_DELAYS_SECONDS):
                raise
            await self._scheduler.sleep(_RECONNECT_DELAYS_SECONDS[attempt])
    if last_error is None:
        raise RuntimeError("source retry loop did not execute")
    raise last_error
```

ให้ warm-up และ backfill สร้าง awaitable ใหม่ทุก attempt ผ่าน lambda เช่น:

```python
candles = await self._run_source_operation(
    lambda: self._source.load_recent(
        self._config,
        count=self._warm_up_count,
        completed_before=completed_before,
    ),
    timeout=_WARM_UP_TIMEOUT_SECONDS,
)
```

แทน outer timeout ที่ครอบ warm-up ทั้งก้อนด้วย `_run_source_operation` ซึ่งกำหนด
timeout `30.0` ต่อ network attempt เพื่อไม่ให้ safe fallback `60.0` ถูกตัดก่อนครบเวลา
และยังคงครอบ `self._pipeline.warm_up(...)` ด้วย `_WARM_UP_TIMEOUT_SECONDS` แยกต่างหาก
ใน `_perform_warm_up` ต้องปล่อย `MarketDataFatalError`,
`MarketDataRateLimitError`, `MarketDataRetryableError`, `MarketDataTimeoutError` และ
`TimeoutError` ผ่านโดยไม่ห่อ
เป็น `_WarmUpSourceError`; ห่อเฉพาะ unexpected source/pipeline validation failure เดิม

จับ exhausted errors ใน caller ตามชนิด:

```python
except MarketDataFatalError:
    self._fail_closed(MarketDataRuntimeReason.SOURCE_FATAL)
    return False
except MarketDataRateLimitError:
    self._fail_closed(MarketDataRuntimeReason.RATE_LIMIT_EXHAUSTED)
    return False
except (MarketDataTimeoutError, TimeoutError):
    self._fail_closed(MarketDataRuntimeReason.WARM_UP_TIMEOUT)
    return False
except (MarketDataRetryableError, _WarmUpSourceError):
    self._fail_closed(MarketDataRuntimeReason.SOURCE_ERROR)
    return False
```

คง sink/pipeline errors เป็น `SINK_ERROR` หรือ `SOURCE_ERROR` ตาม behavior เดิม
สำหรับ `_backfill_to_boundary` ให้ใช้ `_run_source_operation` และจับสาม error types
ด้วย reason ชุดเดียวกันก่อน generic `Exception` branch เดิม หลัง rate-limit delay
ทั้ง warm-up และ backfill ต้องผ่าน `RATE_LIMITED -> RECONNECTING` ก่อนทำ source
attempt ถัดไป ห้าม transition กลับ `WARMING_UP` หรือ `BACKFILLING` โดยตรง

- [ ] **Step 6: Add stream recovery classification**

แก้ `_consume_live` และ `_recover_stream` ให้:

```python
except MarketDataFatalError:
    self._fail_closed(MarketDataRuntimeReason.SOURCE_FATAL)
    return
except MarketDataRateLimitError as error:
    recovered_stream = await self._recover_stream(
        MarketDataRuntimeReason.RATE_LIMITED,
        pending_rate_limit=error,
    )
```

และให้ `_recover_stream` รับ `pending_rate_limit`:

```python
async def _recover_stream(
    self,
    reason: MarketDataRuntimeReason,
    *,
    pending_rate_limit: MarketDataRateLimitError | None = None,
) -> AsyncIterator[Candle] | None:
    if pending_rate_limit is None:
        self._transition(MarketDataRuntimeState.STALE, reason)
    for reconnect_delay in _RECONNECT_DELAYS_SECONDS:
        if pending_rate_limit is None:
            await self._scheduler.sleep(reconnect_delay)
            self._transition(MarketDataRuntimeState.RECONNECTING, reason)
        else:
            if self._status.snapshot.state is not MarketDataRuntimeState.RATE_LIMITED:
                self._transition(
                    MarketDataRuntimeState.RATE_LIMITED,
                    MarketDataRuntimeReason.RATE_LIMITED,
                )
            await self._scheduler.sleep(
                self._retry_after_seconds(pending_rate_limit)
            )
            self._transition(
                MarketDataRuntimeState.RECONNECTING,
                MarketDataRuntimeReason.RATE_LIMITED,
            )
        if self._stop_requested:
            return None
        try:
            stream = self._source.stream_completed(self._config)
            observed = await self._next_reconnect_candle(stream)
        except MarketDataFatalError:
            self._fail_closed(MarketDataRuntimeReason.SOURCE_FATAL)
            return None
        except MarketDataRateLimitError as error:
            pending_rate_limit = error
            self._transition(
                MarketDataRuntimeState.RATE_LIMITED,
                MarketDataRuntimeReason.RATE_LIMITED,
            )
            continue
        except Exception:
            pending_rate_limit = None
            continue

        received_at = self._scheduler.now()
        latest_boundary = _latest_completed_boundary(
            received_at,
            interval=self._config.interval,
        )
        end = max(
            observed.open_time + self._config.interval,
            latest_boundary,
        )
        if not await self._backfill_to_boundary(
            end,
            received_at=received_at,
            observed=observed,
        ):
            return None
        return stream

    exhausted_reason = (
        MarketDataRuntimeReason.RATE_LIMIT_EXHAUSTED
        if pending_rate_limit is not None
        else MarketDataRuntimeReason.RECONNECT_EXHAUSTED
    )
    self._fail_closed(exhausted_reason)
    return None
```

- [ ] **Step 7: Run runtime tests to verify GREEN and regressions**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/market_data/test_runtime.py \
  tests/unit/market_data/test_runtime_state.py \
  tests/acceptance/test_public_market_data_runtime.py -q
```

Expected: tests ทั้งหมด PASS รวม existing reconnect `1/2/4`, stale, backfill,
shutdown และ source-close tests

- [ ] **Step 8: Run focused static checks and commit**

```bash
../../.venv/bin/python -m ruff check \
  src/tiewtrade/market_data/runtime.py \
  tests/unit/market_data/test_runtime.py
../../.venv/bin/python -m ruff format --check \
  src/tiewtrade/market_data/runtime.py \
  tests/unit/market_data/test_runtime.py
../../.venv/bin/python -m mypy src
git add \
  src/tiewtrade/market_data/runtime.py \
  tests/unit/market_data/test_runtime.py
git commit -m "fix: honor market-data rate limits"
```

Expected: checks exit `0` และ commit สำเร็จ

### Task 4: Verify, review and hand off DEV-119

**Files:**
- Verify: `src/tiewtrade/market_data/source_errors.py`
- Verify: `src/tiewtrade/market_data/runtime.py`
- Verify: `src/tiewtrade/market_data/runtime_state.py`
- Verify: `src/tiewtrade/integrations/binance/public_market_data.py`
- Verify: focused tests และ DEV-119 design/plan documents

**Interfaces:**
- Consumes: tested error contract, Binance classification และ Runtime policies จาก Tasks 1–3
- Produces: verification evidence, reviewed Issue branch และ Linear summary โดยยังไม่ push/merge

- [ ] **Step 1: Run the full Python gate**

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen \
  ../../.venv/bin/python -m pytest -q
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
../../.venv/bin/python -m mypy src
```

Expected: Python tests ทั้งหมด PASS และ static checks exit `0`

- [ ] **Step 2: Run documentation and whitespace gates**

```bash
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check main..HEAD
```

Expected: documentation checks และ whitespace check exit `0`

- [ ] **Step 3: Inspect scope and safety**

```bash
git diff --stat main..HEAD
git status --short
git log --oneline main..HEAD
```

Expected: diff จำกัดอยู่ใน source-error contract, Binance public adapter,
MarketDataRuntime, tests และ DEV-119 documents ไม่มี credentials, Private API,
execution, strategy, persistence หรือ user-owned files

- [ ] **Step 4: Review the complete branch**

ใช้ `requesting-code-review` ตรวจ `main..HEAD` สองแกน:

- Standards: DEV-119 acceptance criteria, approved design, repository dependency rules,
  Trading Safety และ TDD evidence
- Code Quality: typed error boundary, deterministic Retry-After parsing, bounded attempts,
  cancellable sleeps, no raw HTTP policy leak และไม่มี abstraction เกินจำเป็น

แก้ Critical/Important findings และรัน focused/full verification ที่เกี่ยวข้องซ้ำ

- [ ] **Step 5: Update Linear after final implementation commit**

เพิ่ม comment ภาษาไทยใน DEV-119 สรุป files, behavior, RED/GREEN evidence,
verification และ remaining risks ย้าย DEV-119 เป็น `Done` หลัง review ไม่มี
Critical/Important findings และ implementation/verification เสร็จจริง บันทึก commit
range ของ design, plan และ implementation ทั้งหมดใน comment

ห้าม push ไป GitHub หรือ merge เข้า `main` จนกว่าจะได้รับคำยืนยันแยกจากผู้ใช้
