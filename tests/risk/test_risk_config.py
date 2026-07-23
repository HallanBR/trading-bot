"""Testes das configurações e do contexto de risco."""

from decimal import Decimal

import pytest

from trading_bot.risk import RiskConfig, RiskContext


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("risk_per_trade", Decimal(0)),
        ("max_daily_loss", Decimal("1.01")),
        ("max_position_fraction", Decimal(-1)),
    ],
)
def test_risk_config_rejects_invalid_fractions(
    field_name: str,
    value: Decimal,
) -> None:
    with pytest.raises(ValueError, match=field_name):
        RiskConfig(**{field_name: value})


def test_risk_config_requires_fast_limits_to_be_positive_integers() -> None:
    with pytest.raises(ValueError, match="max_trades_per_day"):
        RiskConfig(max_trades_per_day=0)


def test_risk_context_rejects_negative_counts() -> None:
    with pytest.raises(ValueError, match="trades_today"):
        RiskContext(
            account_equity=Decimal(10_000),
            day_start_equity=Decimal(10_000),
            trades_today=-1,
        )
