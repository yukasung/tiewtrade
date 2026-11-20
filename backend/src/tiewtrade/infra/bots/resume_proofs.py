"""Read the current proof without clearing any stop authority."""

from uuid import UUID

from tiewtrade.infra.db.session import UserSession


async def has_fresh_strategy_proof(session: UserSession, stop_id: UUID) -> bool:
    result = await session.execute(
        """SELECT EXISTS (
          SELECT 1 FROM bot_resume_proofs p
          JOIN bot_runs b ON b.id=p.run_id AND b.user_id=p.user_id AND b.mode=p.mode
          JOIN trading_stop_requests s ON s.id=p.stop_id AND s.user_id=p.user_id
          JOIN paper_wallet_state w ON w.user_id=p.user_id
          JOIN risk_limit_settings rs ON rs.user_id=p.user_id AND rs.mode=p.mode
          CROSS JOIN risk_price_publication t
          CROSS JOIN risk_protocol_control rc
          CROSS JOIN supported_symbol_catalog_control c
          WHERE p.stop_id=:stop AND p.user_id=:owner AND p.mode='PAPER'
            AND s.cause='SYSTEM' AND s.action='STOP' AND s.mode='PAPER'
            AND s.reason_code IN ('STRATEGY_VERSION_UNAVAILABLE','STRATEGY_EVALUATION_FAILED')
            AND p.expires_at>clock_timestamp() AND b.status='STOPPED'
            AND b.revision=p.run_revision AND w.revision=p.wallet_revision
            AND rs.revision=p.risk_revision AND NOT rs.latched
            AND t.watermark=p.watermark AND c.current_revision=p.catalog_revision
            AND rc.publication_enabled AND rc.financial_enabled AND rc.admission_enabled
        )""",
        {"stop": stop_id, "owner": session.user_id},
    )
    return bool(result.scalar_one())
