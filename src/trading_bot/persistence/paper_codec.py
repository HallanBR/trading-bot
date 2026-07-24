"""Serialização explícita e versionada dos checkpoints paper."""

import json
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal

from trading_bot.domain import (
    Candle,
    Position,
    PositionSide,
    Signal,
    SignalAction,
)
from trading_bot.execution import PaperExecutorState
from trading_bot.trading.paper_state import PaperTradingState

SCHEMA_VERSION = 1


def dump_paper_state(state: PaperTradingState) -> str:
    """Serializa o estado sem converter valores financeiros para float."""

    payload = {
        "schema_version": SCHEMA_VERSION,
        "strategy_name": state.strategy_name,
        "max_history": state.max_history,
        "initialized": state.initialized,
        "history": [_encode_candle(candle) for candle in state.history],
        "last_processed_open_time": _optional_datetime(state.last_processed_open_time),
        "executor": _encode_executor(state.executor),
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def load_paper_state(payload: str) -> PaperTradingState:
    """Valida e reconstrói um checkpoint previamente serializado."""

    raw = _object(json.loads(payload), "checkpoint")
    version = _integer(raw.get("schema_version"), "schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(f"Versão de checkpoint não suportada: {version}.")
    history_raw = _list(raw.get("history"), "history")
    return PaperTradingState(
        strategy_name=_text(raw.get("strategy_name"), "strategy_name"),
        max_history=_integer(raw.get("max_history"), "max_history"),
        initialized=_boolean(raw.get("initialized"), "initialized"),
        history=tuple(_decode_candle(_object(item, "candle")) for item in history_raw),
        last_processed_open_time=_decode_optional_datetime(
            raw.get("last_processed_open_time"),
            "last_processed_open_time",
        ),
        executor=_decode_executor(_object(raw.get("executor"), "executor")),
    )


def dump_signal(signal: Signal | None) -> str | None:
    """Serializa um sinal opcional para acompanhar o histórico do trade."""

    if signal is None:
        return None
    return json.dumps(
        _encode_signal(signal),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def load_signal(payload: str | None) -> Signal | None:
    """Reconstrói um sinal opcional persistido junto de um trade."""

    if payload is None:
        return None
    return _decode_signal(_object(json.loads(payload), "entry_signal"))


def _encode_executor(state: PaperExecutorState) -> dict[str, object]:
    return {
        "equity": str(state.equity),
        "pending_signal": (
            None
            if state.pending_signal is None
            else _encode_signal(state.pending_signal)
        ),
        "open_position": (
            None
            if state.open_position is None
            else _encode_position(state.open_position)
        ),
        "current_day": None
        if state.current_day is None
        else state.current_day.isoformat(),
        "day_start_equity": str(state.day_start_equity),
        "daily_net_pnl": str(state.daily_net_pnl),
        "trades_today": state.trades_today,
        "consecutive_losses": state.consecutive_losses,
        "rejected_signals": state.rejected_signals,
        "position_number": state.position_number,
    }


def _decode_executor(raw: Mapping[str, object]) -> PaperExecutorState:
    current_day_raw = raw.get("current_day")
    if current_day_raw is not None and not isinstance(current_day_raw, str):
        raise TypeError("current_day deve ser texto ou nulo.")
    return PaperExecutorState(
        equity=_decimal(raw.get("equity"), "equity"),
        pending_signal=(
            None
            if raw.get("pending_signal") is None
            else _decode_signal(_object(raw.get("pending_signal"), "pending_signal"))
        ),
        open_position=(
            None
            if raw.get("open_position") is None
            else _decode_position(_object(raw.get("open_position"), "open_position"))
        ),
        current_day=(
            None if current_day_raw is None else date.fromisoformat(current_day_raw)
        ),
        day_start_equity=_decimal(
            raw.get("day_start_equity"),
            "day_start_equity",
        ),
        daily_net_pnl=_decimal(raw.get("daily_net_pnl"), "daily_net_pnl"),
        trades_today=_integer(raw.get("trades_today"), "trades_today"),
        consecutive_losses=_integer(
            raw.get("consecutive_losses"),
            "consecutive_losses",
        ),
        rejected_signals=_integer(
            raw.get("rejected_signals"),
            "rejected_signals",
        ),
        position_number=_integer(raw.get("position_number"), "position_number"),
    )


def _encode_candle(candle: Candle) -> dict[str, object]:
    return {
        "symbol": candle.symbol,
        "interval": candle.interval,
        "open_time": candle.open_time.isoformat(),
        "close_time": candle.close_time.isoformat(),
        "open": str(candle.open),
        "high": str(candle.high),
        "low": str(candle.low),
        "close": str(candle.close),
        "volume": str(candle.volume),
    }


def _decode_candle(raw: Mapping[str, object]) -> Candle:
    return Candle(
        symbol=_text(raw.get("symbol"), "symbol"),
        interval=_text(raw.get("interval"), "interval"),
        open_time=_aware_datetime(raw.get("open_time"), "open_time"),
        close_time=_aware_datetime(raw.get("close_time"), "close_time"),
        open=_decimal(raw.get("open"), "open"),
        high=_decimal(raw.get("high"), "high"),
        low=_decimal(raw.get("low"), "low"),
        close=_decimal(raw.get("close"), "close"),
        volume=_decimal(raw.get("volume"), "volume"),
    )


def _encode_signal(signal: Signal) -> dict[str, object]:
    return {
        "symbol": signal.symbol,
        "interval": signal.interval,
        "action": signal.action.value,
        "generated_at": signal.generated_at.isoformat(),
        "price": str(signal.price),
        "strategy": signal.strategy,
        "reason": signal.reason,
        "stop_loss": (None if signal.stop_loss is None else str(signal.stop_loss)),
        "take_profit": (
            None if signal.take_profit is None else str(signal.take_profit)
        ),
        "indicators": {
            name: None if value is None else str(value)
            for name, value in signal.indicators.items()
        },
    }


def _decode_signal(raw: Mapping[str, object]) -> Signal:
    indicators_raw = _object(raw.get("indicators"), "indicators")
    indicators: dict[str, Decimal | None] = {}
    for name, value in indicators_raw.items():
        indicators[name] = (
            None if value is None else _decimal(value, f"indicators.{name}")
        )
    return Signal(
        symbol=_text(raw.get("symbol"), "symbol"),
        interval=_text(raw.get("interval"), "interval"),
        action=SignalAction(_text(raw.get("action"), "action")),
        generated_at=_aware_datetime(raw.get("generated_at"), "generated_at"),
        price=_decimal(raw.get("price"), "price"),
        strategy=_text(raw.get("strategy"), "strategy"),
        reason=_text(raw.get("reason"), "reason"),
        stop_loss=_optional_decimal(raw.get("stop_loss"), "stop_loss"),
        take_profit=_optional_decimal(raw.get("take_profit"), "take_profit"),
        indicators=indicators,
    )


def _encode_position(position: Position) -> dict[str, object]:
    return {
        "position_id": position.position_id,
        "symbol": position.symbol,
        "interval": position.interval,
        "side": position.side.value,
        "quantity": str(position.quantity),
        "entry_price": str(position.entry_price),
        "stop_loss": str(position.stop_loss),
        "take_profit": str(position.take_profit),
        "opened_at": position.opened_at.isoformat(),
        "strategy": position.strategy,
        "entry_signal": (
            None
            if position.entry_signal is None
            else _encode_signal(position.entry_signal)
        ),
    }


def _decode_position(raw: Mapping[str, object]) -> Position:
    return Position(
        position_id=_text(raw.get("position_id"), "position_id"),
        symbol=_text(raw.get("symbol"), "symbol"),
        interval=_text(raw.get("interval"), "interval"),
        side=PositionSide(_text(raw.get("side"), "side")),
        quantity=_decimal(raw.get("quantity"), "quantity"),
        entry_price=_decimal(raw.get("entry_price"), "entry_price"),
        stop_loss=_decimal(raw.get("stop_loss"), "stop_loss"),
        take_profit=_decimal(raw.get("take_profit"), "take_profit"),
        opened_at=_aware_datetime(raw.get("opened_at"), "opened_at"),
        strategy=_text(raw.get("strategy"), "strategy"),
        entry_signal=(
            None
            if raw.get("entry_signal") is None
            else _decode_signal(_object(raw.get("entry_signal"), "entry_signal"))
        ),
    )


def _object(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError(f"{name} deve ser um objeto JSON.")
    return dict(value)


def _list(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"{name} deve ser uma lista JSON.")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError(f"{name} deve ser texto não vazio.")
    return value


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} deve ser inteiro.")
    return value


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{name} deve ser booleano.")
    return value


def _decimal(value: object, name: str) -> Decimal:
    if not isinstance(value, str):
        raise TypeError(f"{name} deve ser decimal serializado como texto.")
    try:
        return Decimal(value)
    except ArithmeticError as exc:
        raise ValueError(f"{name} não contém um decimal válido.") from exc


def _optional_decimal(value: object, name: str) -> Decimal | None:
    return None if value is None else _decimal(value, name)


def _aware_datetime(value: object, name: str) -> datetime:
    text = _text(value, name)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{name} não contém uma data válida.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} deve incluir fuso horário.")
    return parsed


def _optional_datetime(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _decode_optional_datetime(value: object, name: str) -> datetime | None:
    return None if value is None else _aware_datetime(value, name)
