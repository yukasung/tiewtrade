"""Read shared activation gates that authorize Paper opening effects."""

from tiewtrade.infra.db.session import UserSession, require_user_session


async def paper_opening_protocol_enabled(session: UserSession) -> bool:
    """Require every global gate used by Paper intake and financial writers."""
    checked = require_user_session(session)
    return bool(
        (
            await checked.execute(
                "SELECT publication_enabled AND financial_enabled AND admission_enabled "
                "FROM risk_protocol_control"
            )
        ).scalar_one()
    )
