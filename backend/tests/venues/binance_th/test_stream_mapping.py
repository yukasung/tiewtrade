from datetime import UTC, datetime

import pytest

from tiewtrade.core.money import Money
from tiewtrade.venues.binance_th import stream_mapping
from tiewtrade.venues.errors import VenueProtocolError
from tiewtrade.venues.symbols import Symbol

NOW = datetime(2026, 10, 7, tzinfo=UTC)
PAIR = Symbol("BTC", "USDT")


def test_stream_trade_uses_trade_time_and_exact_price() -> None:
    quote = stream_mapping.quote_from_stream(
        payload={
            "stream": "btcusdt@trade",
            "data": {
                "e": "trade",
                "s": "BTCUSDT",
                "p": "123.45000001",
                "t": 7,
                "T": 1791331200000,
                "E": 1,
            },
        },
        symbols=(PAIR,),
        received_at=NOW,
    )
    assert quote.trade_time == NOW
    assert quote.trade_id == 7
    assert quote.amount == Money.of("123.45000001", "USDT")


@pytest.mark.parametrize(
    "field,value",
    [("t", True), ("t", -1), ("p", 1.2), ("T", True), ("s", "BTCBUSD"), ("e", "aggTrade")],
)
def test_stream_rejects_invalid_contract(field: str, value: object) -> None:
    data: dict[str, object] = {"e": "trade", "s": "BTCUSDT", "p": "1", "t": 7, "T": 1791331200000}
    data[field] = value
    with pytest.raises(VenueProtocolError):
        stream_mapping.quote_from_stream(
            payload={"stream": "btcusdt@trade", "data": data}, symbols=(PAIR,), received_at=NOW
        )


def test_ack_requires_exact_success_id() -> None:
    assert stream_mapping.subscription_ack({"result": None, "id": 9}, 9)
    assert not stream_mapping.subscription_ack({"result": None, "id": 8}, 9)
    with pytest.raises(VenueProtocolError):
        stream_mapping.subscription_ack({"result": "error", "id": 9}, 9)


@pytest.mark.parametrize("kind", ["stream", "snapshot"])
@pytest.mark.parametrize("trade_id", [0, 2**63 - 1, 2**63, 10**100])
def test_trade_ids_match_the_persistence_range(kind: str, trade_id: int) -> None:
    def parse() -> object:
        if kind == "stream":
            return stream_mapping.quote_from_stream(
                payload={
                    "stream": "btcusdt@trade",
                    "data": {
                        "e": "trade",
                        "s": "BTCUSDT",
                        "p": "1",
                        "t": trade_id,
                        "T": 1791331200000,
                    },
                },
                symbols=(PAIR,),
                received_at=NOW,
            )
        return stream_mapping.quote_from_trades(
            symbol=PAIR,
            payload=[{"price": "1", "time": 1791331200000, "id": trade_id}],
            received_at=NOW,
        )

    if trade_id >= 2**63:
        with pytest.raises(VenueProtocolError):
            parse()
    else:
        from tiewtrade.core.realtime_prices import QuoteObservation

        result = parse()
        assert isinstance(result, QuoteObservation)
        assert result.trade_id == trade_id


def test_recorded_public_rest_and_stream_contract_covers_supported_pairs() -> None:
    import json
    from pathlib import Path

    fixtures = Path(__file__).parents[4] / "specs/research/2026-10-07-f10-public-contract"
    rest = json.loads((fixtures / "01-rest-and-query-stream.json").read_text())["rest"]
    pairs = tuple(Symbol(base, "USDT") for base in ("BTC", "ETH"))
    for pair in pairs:
        response = rest[f"{pair.base}USDT"]
        quote = stream_mapping.quote_from_trades(
            symbol=pair,
            payload=response["payload"],
            received_at=datetime.fromisoformat(response["received_at"]),
        )
        assert quote.trade_id == response["payload"][-1]["id"]
        assert quote.amount == Money.of(response["payload"][-1]["price"], "USDT")
    frames = json.loads((fixtures / "03-all-pairs.json").read_text())["frames"]
    observed = set()
    supported_symbols = {f"{pair.base}{pair.quote}" for pair in pairs}
    for frame in frames:
        payload = frame["payload"]
        if "stream" not in payload or payload["data"]["s"] not in supported_symbols:
            continue
        quote = stream_mapping.quote_from_stream(
            payload=payload,
            symbols=pairs,
            received_at=datetime.fromisoformat(frame["received_at"]),
        )
        observed.add(quote.base)
        assert quote.amount == Money.of(payload["data"]["p"], "USDT")
        assert quote.trade_id == payload["data"]["t"]
    assert observed == {pair.base for pair in pairs}
