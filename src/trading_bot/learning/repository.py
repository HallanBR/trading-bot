"""Gravação e consulta idempotentes de operações perdedoras."""

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from trading_bot.domain import ExitReason, PositionSide, Trade, TradeResult
from trading_bot.learning.database import LearningDatabase
from trading_bot.learning.exceptions import LearningPersistenceError
from trading_bot.learning.models import LosingTradeModel
from trading_bot.learning.records import LosingTradeCase


class LosingTradeRepository:
    """Mantém um conjunto separado e deduplicado de perdas virtuais."""

    schema_version = 1

    def __init__(self, database: LearningDatabase) -> None:
        self.database = database

    def save_loss(self, trade: Trade) -> bool:
        """Salva somente perdas líquidas e ignora repetições do mesmo caso."""

        if trade.result is not TradeResult.LOSS:
            return False
        case_id = self._case_id(trade)
        try:
            with self.database.session() as database_session:
                if database_session.get(LosingTradeModel, case_id) is not None:
                    return False
                database_session.add(self._model(case_id, trade))
        except (SQLAlchemyError, ValueError, TypeError) as exc:
            raise LearningPersistenceError(
                f"Não foi possível salvar a perda {trade.trade_id}."
            ) from exc
        return True

    def count(self) -> int:
        """Retorna a quantidade total de casos perdedores armazenados."""

        statement = select(func.count()).select_from(LosingTradeModel)
        try:
            with self.database.session() as database_session:
                return int(database_session.scalar(statement) or 0)
        except SQLAlchemyError as exc:
            raise LearningPersistenceError(
                "Não foi possível contar as operações perdedoras."
            ) from exc

    def list_recent(self, *, limit: int = 20) -> list[LosingTradeCase]:
        """Lista os casos mais recentes, do mais novo para o mais antigo."""

        if limit <= 0:
            raise ValueError("limit deve ser positivo.")
        statement = (
            select(LosingTradeModel)
            .order_by(LosingTradeModel.recorded_at.desc())
            .limit(limit)
        )
        try:
            with self.database.session() as database_session:
                models = database_session.scalars(statement).all()
                return [self._record(model) for model in models]
        except (SQLAlchemyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise LearningPersistenceError(
                "Não foi possível consultar as operações perdedoras."
            ) from exc

    @classmethod
    def _model(cls, case_id: str, trade: Trade) -> LosingTradeModel:
        signal = trade.entry_signal
        indicators = {} if signal is None else signal.indicators
        indicators_json = json.dumps(
            {
                name: None if value is None else str(value)
                for name, value in indicators.items()
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return LosingTradeModel(
            case_id=case_id,
            schema_version=cls.schema_version,
            recorded_at=datetime.now(timezone.utc),
            trade_id=trade.trade_id,
            symbol=trade.symbol,
            interval=trade.interval,
            side=trade.side.value,
            quantity=trade.quantity,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            stop_loss=trade.stop_loss,
            take_profit=trade.take_profit,
            fees=trade.fees,
            gross_pnl=trade.gross_pnl,
            net_pnl=trade.net_pnl,
            result=trade.result.value,
            opened_at=trade.opened_at,
            closed_at=trade.closed_at,
            strategy=trade.strategy,
            exit_reason=trade.exit_reason.value,
            signal_generated_at=None if signal is None else signal.generated_at,
            signal_price=None if signal is None else signal.price,
            signal_reason=None if signal is None else signal.reason,
            indicators_json=indicators_json,
        )

    @staticmethod
    def _record(model: LosingTradeModel) -> LosingTradeCase:
        raw_indicators = json.loads(model.indicators_json)
        if not isinstance(raw_indicators, dict):
            raise TypeError("Indicadores persistidos possuem formato inválido.")
        indicators: dict[str, Decimal | None] = {}
        for name, value in raw_indicators.items():
            if not isinstance(name, str):
                raise TypeError("Nome de indicador persistido é inválido.")
            indicators[name] = None if value is None else Decimal(str(value))
        return LosingTradeCase(
            case_id=model.case_id,
            recorded_at=model.recorded_at,
            trade_id=model.trade_id,
            symbol=model.symbol,
            interval=model.interval,
            side=PositionSide(model.side),
            quantity=model.quantity,
            entry_price=model.entry_price,
            exit_price=model.exit_price,
            stop_loss=model.stop_loss,
            take_profit=model.take_profit,
            fees=model.fees,
            gross_pnl=model.gross_pnl,
            net_pnl=model.net_pnl,
            opened_at=model.opened_at,
            closed_at=model.closed_at,
            strategy=model.strategy,
            exit_reason=ExitReason(model.exit_reason),
            signal_generated_at=model.signal_generated_at,
            signal_price=model.signal_price,
            signal_reason=model.signal_reason,
            indicators=indicators,
        )

    @staticmethod
    def _case_id(trade: Trade) -> str:
        """Gera um identificador estável mesmo após reiniciar o paper runner."""

        parts = (
            "losing-trade-v1",
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
