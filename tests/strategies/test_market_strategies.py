"""Testes das estratégias candidatas e seus filtros."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from trading_bot.domain import Candle, SignalAction
from trading_bot.strategies import (
    BreakoutConfig,
    BreakoutVolumeStrategy,
    EmaRsiAtrConfig,
    FilteredTrendConfig,
    FilteredTrendStrategy,
    MeanReversionConfig,
    MeanReversionStrategy,
    create_strategy,
)


def candles_from_closes(
    *closes: int,
    volumes: tuple[int, ...] | None = None,
) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    selected_volumes = volumes or tuple(10 for _ in closes)
    candles: list[Candle] = []
    for index, (close_value, volume) in enumerate(
        zip(closes, selected_volumes, strict=True)
    ):
        close = Decimal(close_value)
        opened = start + timedelta(minutes=index)
        candles.append(
            Candle(
                symbol="BTCUSDT",
                interval="1m",
                open_time=opened,
                close_time=opened + timedelta(seconds=59),
                open=close,
                high=close + Decimal(1),
                low=close - Decimal(1),
                close=close,
                volume=Decimal(volume),
            )
        )
    return candles


def base_config() -> EmaRsiAtrConfig:
    return EmaRsiAtrConfig(
        fast_ema_period=2,
        slow_ema_period=3,
        rsi_period=2,
        atr_period=2,
        buy_rsi_min=Decimal(50),
        buy_rsi_max=Decimal(80),
        sell_rsi_min=Decimal(20),
        sell_rsi_max=Decimal(50),
        stop_atr_multiple=Decimal(1),
        take_atr_multiple=Decimal(2),
    )


def filtered_config(*, projected_cost: str = "0") -> FilteredTrendConfig:
    return FilteredTrendConfig(
        base=base_config(),
        trend_ema_period=2,
        trend_slope_lookback=1,
        vwap_period=2,
        volume_period=2,
        minimum_relative_volume=Decimal("0.5"),
        minimum_atr_percent=Decimal(0),
        maximum_atr_percent=Decimal(100),
        projected_round_trip_cost_rate=Decimal(projected_cost),
        minimum_target_cost_multiple=Decimal(1),
    )


def test_filtered_trend_confirms_base_buy() -> None:
    signal = FilteredTrendStrategy(filtered_config()).generate_signal(
        candles_from_closes(13, 12, 11, 14)
    )

    assert signal.action is SignalAction.BUY
    assert signal.strategy == "EMA_RSI_ATR_FILTERED"
    assert signal.indicators["vwap"] is not None


def test_filtered_trend_blocks_target_that_does_not_cover_costs() -> None:
    signal = FilteredTrendStrategy(
        filtered_config(projected_cost="0.50")
    ).generate_signal(candles_from_closes(13, 12, 11, 14))

    assert signal.action is SignalAction.HOLD
    assert "custos" in signal.reason


def test_breakout_requires_trend_and_relative_volume() -> None:
    strategy = BreakoutVolumeStrategy(
        BreakoutConfig(
            range_period=2,
            trend_ema_period=2,
            volume_period=2,
            atr_period=2,
            minimum_relative_volume=Decimal(2),
            stop_atr_multiple=Decimal(1),
            take_atr_multiple=Decimal(2),
            projected_round_trip_cost_rate=Decimal(0),
        )
    )

    signal = strategy.generate_signal(
        candles_from_closes(10, 10, 13, volumes=(10, 10, 30))
    )

    assert signal.action is SignalAction.BUY
    assert signal.indicators["relative_volume"] == Decimal(3)


def test_mean_reversion_detects_lower_band_extreme() -> None:
    strategy = MeanReversionStrategy(
        MeanReversionConfig(
            band_period=3,
            standard_deviations=Decimal(1),
            rsi_period=2,
            atr_period=2,
            regime_ema_period=2,
            maximum_trend_gap_percent=Decimal(100),
            buy_rsi_maximum=Decimal(99),
            sell_rsi_minimum=Decimal(100),
            stop_atr_multiple=Decimal(1),
            take_atr_multiple=Decimal(2),
            projected_round_trip_cost_rate=Decimal(0),
        )
    )

    signal = strategy.generate_signal(candles_from_closes(10, 10, 8))

    assert signal.action is SignalAction.BUY
    assert signal.strategy == "MEAN_REVERSION_BOLLINGER"


def test_strategy_registry_rejects_unknown_name() -> None:
    assert create_strategy("filtered").name == "EMA_RSI_ATR_FILTERED"
