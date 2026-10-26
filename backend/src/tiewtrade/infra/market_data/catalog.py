"""Market-data catalog reads; static aliases remain rollout compatibility only."""

from tiewtrade.core.market_catalog import PAIRS as PAIRS
from tiewtrade.core.market_catalog import SOURCE as SOURCE
from tiewtrade.infra.db.session import MarketDataSession, require_market_data_session
from tiewtrade.infra.platform import RuntimeSymbol, runtime_symbols


async def runtime_catalog(session: MarketDataSession) -> tuple[RuntimeSymbol, ...]:
    return await runtime_symbols(require_market_data_session(session))


async def runtime_symbol_map(
    session: MarketDataSession, *, modes: frozenset[str] | None = None
) -> dict[tuple[str, str], RuntimeSymbol]:
    rows = await runtime_catalog(session)
    return {(row.base, row.quote): row for row in rows if modes is None or row.mode in modes}


async def runtime_pairs(
    session: MarketDataSession, *, modes: frozenset[str] | None = None
) -> frozenset[tuple[str, str]]:
    return frozenset(await runtime_symbol_map(session, modes=modes))
