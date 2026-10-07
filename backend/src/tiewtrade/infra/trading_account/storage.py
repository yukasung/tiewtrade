"""Read and select the owner's initial use in an existing user transaction."""

from tiewtrade.infra.api_keys.records import ApiKeyStatus
from tiewtrade.infra.api_keys.storage import summaries_for
from tiewtrade.infra.db.errors import DuplicateValueError
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.trading_account.records import (
    AccountUse,
    TradingAccountActivityUnknownError,
    TradingAccountKeyUnavailableError,
    TradingAccountSummary,
)


async def get_account(session: UserSession) -> TradingAccountSummary:
    session = require_user_session(session)
    use = (
        await session.execute(
            "SELECT use FROM public.user_trading_preferences WHERE user_id=:owner",
            {"owner": session.user_id},
        )
    ).scalar_one_or_none()
    keys = await summaries_for(session, session.user_id)
    return TradingAccountSummary(
        use=AccountUse(use) if use is not None else None, key=keys[0] if keys else None
    )


async def select_use(session: UserSession, use: AccountUse) -> TradingAccountSummary:
    session = require_user_session(session)
    existing = (
        await session.execute(
            "SELECT use FROM public.user_trading_preferences WHERE user_id=:owner",
            {"owner": session.user_id},
        )
    ).first()
    if existing is not None:
        raise TradingAccountActivityUnknownError("account activity unknown")
    key = (
        await session.execute(
            "SELECT id,status FROM public.user_api_keys WHERE user_id=:owner FOR UPDATE",
            {"owner": session.user_id},
        )
    ).first()
    if key is None or key.status != ApiKeyStatus.ACTIVE.value:
        raise TradingAccountKeyUnavailableError("account key unavailable")
    # Another selection may have committed while this transaction waited for
    # the credential lock. The unique constraint remains the final DB guard.
    existing = (
        await session.execute(
            "SELECT use FROM public.user_trading_preferences WHERE user_id=:owner",
            {"owner": session.user_id},
        )
    ).first()
    if existing is not None:
        raise TradingAccountActivityUnknownError("account activity unknown")
    try:
        await session.execute(
            "INSERT INTO public.user_trading_preferences (user_id,use) VALUES (:owner,:use)",
            {"owner": session.user_id, "use": use.value},
        )
    except DuplicateValueError:
        raise TradingAccountActivityUnknownError("account activity unknown") from None
    return await get_account(session)
