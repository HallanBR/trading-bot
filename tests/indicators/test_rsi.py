"""Testes do índice de força relativa."""

from decimal import Decimal

import pytest

from trading_bot.indicators import rsi


def decimals(*values: int | str) -> list[Decimal]:
    return [Decimal(value) for value in values]


def test_rsi_returns_hundred_for_continuous_gains() -> None:
    result = rsi(decimals(1, 2, 3, 4, 5), period=3)

    assert result == [None, None, None, Decimal(100), Decimal(100)]


def test_rsi_returns_zero_for_continuous_losses() -> None:
    result = rsi(decimals(5, 4, 3, 2, 1), period=3)

    assert result == [None, None, None, Decimal(0), Decimal(0)]


def test_rsi_returns_neutral_value_when_prices_do_not_change() -> None:
    result = rsi(decimals(5, 5, 5, 5), period=3)

    assert result == [None, None, None, Decimal(50)]


@pytest.mark.parametrize("period", [0, -1, 1.5, True])
def test_rsi_rejects_invalid_period(period: object) -> None:
    with pytest.raises(ValueError):
        rsi(decimals(1, 2, 3), period=period)  # type: ignore[arg-type]
