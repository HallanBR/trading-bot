"""Identidade estável de operações encerradas."""

import hashlib
from datetime import timezone

from trading_bot.domain import Trade


def closed_trade_case_id(trade: Trade) -> str:
    """Deduplica um trade mesmo quando o contador reinicia no processo."""

    parts = (
        "closed-trade-v1",
        trade.trade_id,
        trade.symbol,
        trade.interval,
        trade.side.value,
        trade.opened_at.astimezone(timezone.utc).isoformat(),
        trade.closed_at.astimezone(timezone.utc).isoformat(),
        str(trade.entry_price),
        str(trade.exit_price),
        str(trade.quantity),
        str(trade.fees),
        trade.strategy,
    )
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()
