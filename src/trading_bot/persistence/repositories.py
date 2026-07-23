"""Repositórios para salvar e consultar execuções de backtest."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from trading_bot.backtest import BacktestResult
from trading_bot.domain import ExitReason, PositionSide, Trade
from trading_bot.persistence.database import Database
from trading_bot.persistence.exceptions import (
    BacktestNotFoundError,
    PersistenceError,
)
from trading_bot.persistence.models import BacktestRunModel, TradeModel
from trading_bot.persistence.records import BacktestSummary


class BacktestRepository:
    """Persiste um resultado e todos os seus trades na mesma transação."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def save(
        self,
        result: BacktestResult,
        *,
        strategy: str,
        symbol: str,
        interval: str,
        run_id: str | None = None,
        created_at: datetime | None = None,
    ) -> str:
        """Salva métricas e trades de forma atômica e retorna o ID da execução."""

        identifier = run_id or str(uuid4())
        timestamp = created_at or datetime.now(timezone.utc)
        model = BacktestRunModel(
            run_id=identifier,
            created_at=timestamp,
            strategy=strategy,
            symbol=symbol,
            interval=interval,
            initial_equity=result.initial_equity,
            final_equity=result.final_equity,
            net_profit=result.net_profit,
            return_percent=result.return_percent,
            win_rate_percent=result.win_rate_percent,
            max_drawdown_percent=result.max_drawdown_percent,
            profit_factor=result.profit_factor,
            total_trades=result.total_trades,
            wins=result.wins,
            losses=result.losses,
            rejected_signals=result.rejected_signals,
            trades=[self._trade_model(identifier, trade) for trade in result.trades],
        )
        try:
            with self.database.session() as database_session:
                database_session.add(model)
        except (SQLAlchemyError, ValueError) as exc:
            raise PersistenceError(
                f"Não foi possível salvar o backtest {identifier}."
            ) from exc
        return identifier

    def get_summary(self, run_id: str) -> BacktestSummary:
        """Carrega um resumo ou informa que a execução não existe."""

        try:
            with self.database.session() as database_session:
                model = database_session.get(BacktestRunModel, run_id)
                if model is None:
                    raise BacktestNotFoundError(f"Backtest {run_id} não encontrado.")
                return self._summary(model)
        except BacktestNotFoundError:
            raise
        except SQLAlchemyError as exc:
            raise PersistenceError(
                f"Não foi possível consultar o backtest {run_id}."
            ) from exc

    def list_summaries(self, *, limit: int = 20) -> list[BacktestSummary]:
        """Lista os backtests mais recentes."""

        if limit <= 0:
            raise ValueError("limit deve ser positivo.")
        statement = (
            select(BacktestRunModel)
            .order_by(BacktestRunModel.created_at.desc())
            .limit(limit)
        )
        try:
            with self.database.session() as database_session:
                models = database_session.scalars(statement).all()
                return [self._summary(model) for model in models]
        except SQLAlchemyError as exc:
            raise PersistenceError("Não foi possível listar os backtests.") from exc

    def get_trades(self, run_id: str) -> list[Trade]:
        """Reconstrói os trades de uma execução na ordem original."""

        statement = (
            select(TradeModel)
            .where(TradeModel.backtest_run_id == run_id)
            .order_by(TradeModel.internal_id)
        )
        try:
            with self.database.session() as database_session:
                if database_session.get(BacktestRunModel, run_id) is None:
                    raise BacktestNotFoundError(f"Backtest {run_id} não encontrado.")
                models = database_session.scalars(statement).all()
                return [self._trade(model) for model in models]
        except BacktestNotFoundError:
            raise
        except SQLAlchemyError as exc:
            raise PersistenceError(
                f"Não foi possível consultar trades de {run_id}."
            ) from exc

    @staticmethod
    def _trade_model(run_id: str, trade: Trade) -> TradeModel:
        return TradeModel(
            backtest_run_id=run_id,
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
        )

    @staticmethod
    def _trade(model: TradeModel) -> Trade:
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
        )

    @staticmethod
    def _summary(model: BacktestRunModel) -> BacktestSummary:
        return BacktestSummary(
            run_id=model.run_id,
            created_at=model.created_at,
            strategy=model.strategy,
            symbol=model.symbol,
            interval=model.interval,
            initial_equity=model.initial_equity,
            final_equity=model.final_equity,
            net_profit=model.net_profit,
            return_percent=model.return_percent,
            win_rate_percent=model.win_rate_percent,
            max_drawdown_percent=model.max_drawdown_percent,
            profit_factor=model.profit_factor,
            total_trades=model.total_trades,
            wins=model.wins,
            losses=model.losses,
            rejected_signals=model.rejected_signals,
        )
