"""Checkpoints e histórico completo das sessões de paper trading."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from trading_bot.domain import ExitReason, PositionSide, Trade, TradeResult
from trading_bot.persistence.database import Database
from trading_bot.persistence.exceptions import PersistenceError
from trading_bot.persistence.models import PaperSessionModel, PaperTradeModel
from trading_bot.persistence.paper_codec import (
    SCHEMA_VERSION,
    dump_paper_state,
    dump_signal,
    load_paper_state,
    load_signal,
)
from trading_bot.persistence.trade_identity import closed_trade_case_id
from trading_bot.trading.paper_state import PaperTradingState


@dataclass(frozen=True, slots=True)
class PaperTradeCounts:
    """Contagem observável das operações paper já encerradas."""

    total: int
    wins: int
    losses: int
    break_even: int


def build_paper_session_id(symbol: str, interval: str, strategy: str) -> str:
    """Gera uma identidade estável e legível por mercado e estratégia."""

    if not symbol or not interval or not strategy:
        raise ValueError("Símbolo, intervalo e estratégia são obrigatórios.")
    return f"paper:{symbol.upper()}:{interval}:{strategy}"


class PaperSessionRepository:
    """Salva estado e trades novos na mesma transação SQLite."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def load_state(self, session_id: str) -> PaperTradingState | None:
        """Carrega o último checkpoint ou retorna ``None`` para uma sessão nova."""

        try:
            with self.database.session() as database_session:
                model = database_session.get(PaperSessionModel, session_id)
                if model is None:
                    return None
                if model.schema_version != SCHEMA_VERSION:
                    raise ValueError(
                        f"Versão de sessão não suportada: {model.schema_version}."
                    )
                state = load_paper_state(model.state_json)
                self._validate_identity(model, state)
                return state
        except (SQLAlchemyError, TypeError, ValueError) as exc:
            raise PersistenceError(
                f"Não foi possível restaurar a sessão paper {session_id}."
            ) from exc

    def save_checkpoint(
        self,
        session_id: str,
        state: PaperTradingState,
        trades: Sequence[Trade] = (),
    ) -> int:
        """Persiste estado e operações deduplicadas de forma atômica."""

        symbol, interval = self._state_market(state)
        now = datetime.now(timezone.utc)
        state_json = dump_paper_state(state)
        inserted_trades = 0
        try:
            with self.database.session() as database_session:
                model = database_session.get(PaperSessionModel, session_id)
                if model is None:
                    model = PaperSessionModel(
                        session_id=session_id,
                        symbol=symbol,
                        interval=interval,
                        strategy=state.strategy_name,
                        updated_at=now,
                        schema_version=SCHEMA_VERSION,
                        state_json=state_json,
                    )
                    database_session.add(model)
                else:
                    self._validate_identity(model, state)
                    model.updated_at = now
                    model.schema_version = SCHEMA_VERSION
                    model.state_json = state_json

                for trade in trades:
                    if (
                        trade.symbol != symbol
                        or trade.interval != interval
                        or trade.strategy != state.strategy_name
                    ):
                        raise ValueError("O trade não pertence à sessão do checkpoint.")
                    case_id = closed_trade_case_id(trade)
                    if database_session.get(PaperTradeModel, case_id) is not None:
                        continue
                    database_session.add(
                        self._trade_model(
                            session_id,
                            case_id,
                            now,
                            trade,
                        )
                    )
                    inserted_trades += 1
        except (SQLAlchemyError, TypeError, ValueError) as exc:
            raise PersistenceError(
                f"Não foi possível salvar a sessão paper {session_id}."
            ) from exc
        return inserted_trades

    def list_trades(
        self,
        session_id: str,
        *,
        limit: int = 100,
    ) -> list[Trade]:
        """Lista as operações mais recentes da sessão."""

        if limit <= 0:
            raise ValueError("limit deve ser positivo.")
        statement = (
            select(PaperTradeModel)
            .where(PaperTradeModel.session_id == session_id)
            .order_by(PaperTradeModel.closed_at.desc())
            .limit(limit)
        )
        try:
            with self.database.session() as database_session:
                models = database_session.scalars(statement).all()
                return [self._trade(model) for model in models]
        except (SQLAlchemyError, TypeError, ValueError) as exc:
            raise PersistenceError(
                f"Não foi possível listar os trades paper de {session_id}."
            ) from exc

    def trade_counts(self, session_id: str) -> PaperTradeCounts:
        """Conta resultados sem carregar todas as operações na memória."""

        statement = (
            select(PaperTradeModel.result, func.count())
            .where(PaperTradeModel.session_id == session_id)
            .group_by(PaperTradeModel.result)
        )
        try:
            with self.database.session() as database_session:
                rows = database_session.execute(statement).all()
        except SQLAlchemyError as exc:
            raise PersistenceError(
                f"Não foi possível contar os trades paper de {session_id}."
            ) from exc
        counts = {str(result): int(count) for result, count in rows}
        wins = counts.get(TradeResult.WIN.value, 0)
        losses = counts.get(TradeResult.LOSS.value, 0)
        break_even = counts.get(TradeResult.BREAK_EVEN.value, 0)
        return PaperTradeCounts(
            total=wins + losses + break_even,
            wins=wins,
            losses=losses,
            break_even=break_even,
        )

    @staticmethod
    def _state_market(state: PaperTradingState) -> tuple[str, str]:
        if state.history:
            return state.history[-1].symbol, state.history[-1].interval
        executor = state.executor
        if executor.open_position is not None:
            return executor.open_position.symbol, executor.open_position.interval
        if executor.pending_signal is not None:
            return executor.pending_signal.symbol, executor.pending_signal.interval
        raise ValueError("O checkpoint não possui mercado identificável.")

    @classmethod
    def _validate_identity(
        cls,
        model: PaperSessionModel,
        state: PaperTradingState,
    ) -> None:
        symbol, interval = cls._state_market(state)
        if (
            model.symbol != symbol
            or model.interval != interval
            or model.strategy != state.strategy_name
        ):
            raise ValueError("O checkpoint não pertence à sessão solicitada.")

    @staticmethod
    def _trade_model(
        session_id: str,
        case_id: str,
        recorded_at: datetime,
        trade: Trade,
    ) -> PaperTradeModel:
        return PaperTradeModel(
            case_id=case_id,
            session_id=session_id,
            recorded_at=recorded_at,
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
            entry_signal_json=dump_signal(trade.entry_signal),
        )

    @staticmethod
    def _trade(model: PaperTradeModel) -> Trade:
        return Trade(
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
            opened_at=model.opened_at,
            closed_at=model.closed_at,
            strategy=model.strategy,
            exit_reason=ExitReason(model.exit_reason),
            entry_signal=load_signal(model.entry_signal_json),
        )
