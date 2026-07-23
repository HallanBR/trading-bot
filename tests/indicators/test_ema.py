"""Testes da média móvel exponencial."""

from decimal import Decimal

import pytest

from trading_bot.indicators import ema


def decimals(*values: int | str) -> list[Decimal]:
    return [Decimal(value) for value in values]


def test_ema_uses_sma_as_initial_value() -> None:
    result = ema(decimals(1, 2, 3, 4, 5), period=3)

    assert result == [None, None, Decimal(2), Decimal(3), Decimal(4)]


def test_ema_preserves_alignment_when_history_is_too_short() -> None:
    assert ema(decimals(10, 11), period=3) == [None, None]


@pytest.mark.parametrize("period", [0, -1, 1.5, True])
def test_ema_rejects_invalid_period(period: object) -> None:
    with pytest.raises(ValueError):
        ema(decimals(1, 2, 3), period=period)  # type: ignore[arg-type]
