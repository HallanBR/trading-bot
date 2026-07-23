"""Testes dos tipos de precisão usados pelo SQLite."""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import StatementError

from trading_bot.persistence import Database
from trading_bot.persistence.models import BacktestRunModel


def test_persistence_rejects_naive_datetime() -> None:
    database = Database("sqlite:///:memory:")
    database.create_schema()
    model = BacktestRunModel(
        run_id="naive",
        created_at=datetime(2026, 1, 1),  # noqa: DTZ001
        strategy="TEST",
        symbol="BTCUSDT",
        interval="5m",
        initial_equity=Decimal(100),
        final_equity=Decimal(100),
        net_profit=Decimal(0),
        return_percent=Decimal(0),
        win_rate_percent=Decimal(0),
        max_drawdown_percent=Decimal(0),
        profit_factor=None,
        total_trades=0,
        wins=0,
        losses=0,
        rejected_signals=0,
    )

    with (
        pytest.raises(StatementError, match="fuso horário"),
        database.session() as database_session,
    ):
        database_session.add(model)
        database_session.flush()

    with database.session() as database_session:
        assert database_session.scalar(select(BacktestRunModel)) is None
    database.dispose()
