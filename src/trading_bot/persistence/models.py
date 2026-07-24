"""Mapeamentos relacionais usados pela persistência SQLite."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from trading_bot.persistence.types import AwareDateTimeText, DecimalText


class Base(DeclarativeBase):
    """Base dos modelos SQLAlchemy."""


class BacktestRunModel(Base):
    """Uma execução completa de backtest e suas métricas."""

    __tablename__ = "backtest_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTimeText())
    strategy: Mapped[str] = mapped_column(String(100))
    symbol: Mapped[str] = mapped_column(String(40))
    interval: Mapped[str] = mapped_column(String(10))
    initial_equity: Mapped[Decimal] = mapped_column(DecimalText())
    final_equity: Mapped[Decimal] = mapped_column(DecimalText())
    net_profit: Mapped[Decimal] = mapped_column(DecimalText())
    return_percent: Mapped[Decimal] = mapped_column(DecimalText())
    win_rate_percent: Mapped[Decimal] = mapped_column(DecimalText())
    max_drawdown_percent: Mapped[Decimal] = mapped_column(DecimalText())
    profit_factor: Mapped[Decimal | None] = mapped_column(
        DecimalText(),
        nullable=True,
    )
    total_trades: Mapped[int] = mapped_column(Integer)
    wins: Mapped[int] = mapped_column(Integer)
    losses: Mapped[int] = mapped_column(Integer)
    rejected_signals: Mapped[int] = mapped_column(Integer)
    trades: Mapped[list["TradeModel"]] = relationship(
        back_populates="backtest_run",
        cascade="all, delete-orphan",
        order_by="TradeModel.internal_id",
    )


class TradeModel(Base):
    """Operação encerrada pertencente a uma execução de backtest."""

    __tablename__ = "trades"
    __table_args__ = (
        UniqueConstraint(
            "backtest_run_id",
            "trade_id",
            name="uq_trade_run_identifier",
        ),
    )

    internal_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    backtest_run_id: Mapped[str] = mapped_column(
        ForeignKey("backtest_runs.run_id", ondelete="CASCADE"),
        index=True,
    )
    trade_id: Mapped[str] = mapped_column(String(100))
    symbol: Mapped[str] = mapped_column(String(40))
    interval: Mapped[str] = mapped_column(String(10))
    side: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[Decimal] = mapped_column(DecimalText())
    entry_price: Mapped[Decimal] = mapped_column(DecimalText())
    exit_price: Mapped[Decimal] = mapped_column(DecimalText())
    stop_loss: Mapped[Decimal] = mapped_column(DecimalText())
    take_profit: Mapped[Decimal] = mapped_column(DecimalText())
    fees: Mapped[Decimal] = mapped_column(DecimalText())
    gross_pnl: Mapped[Decimal] = mapped_column(DecimalText())
    net_pnl: Mapped[Decimal] = mapped_column(DecimalText())
    result: Mapped[str] = mapped_column(String(20))
    opened_at: Mapped[datetime] = mapped_column(AwareDateTimeText())
    closed_at: Mapped[datetime] = mapped_column(AwareDateTimeText())
    strategy: Mapped[str] = mapped_column(String(100))
    exit_reason: Mapped[str] = mapped_column(String(30))
    backtest_run: Mapped[BacktestRunModel] = relationship(
        back_populates="trades",
    )


class PaperSessionModel(Base):
    """Checkpoint mais recente de uma sessão paper identificável."""

    __tablename__ = "paper_sessions"

    session_id: Mapped[str] = mapped_column(String(180), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    interval: Mapped[str] = mapped_column(String(10))
    strategy: Mapped[str] = mapped_column(String(100))
    updated_at: Mapped[datetime] = mapped_column(AwareDateTimeText())
    schema_version: Mapped[int] = mapped_column(Integer)
    state_json: Mapped[str] = mapped_column(Text)


class PaperTradeModel(Base):
    """Histórico completo e deduplicado das operações paper encerradas."""

    __tablename__ = "paper_trades"

    case_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("paper_sessions.session_id", ondelete="CASCADE"),
        index=True,
    )
    recorded_at: Mapped[datetime] = mapped_column(AwareDateTimeText())
    trade_id: Mapped[str] = mapped_column(String(100), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    interval: Mapped[str] = mapped_column(String(10))
    side: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[Decimal] = mapped_column(DecimalText())
    entry_price: Mapped[Decimal] = mapped_column(DecimalText())
    exit_price: Mapped[Decimal] = mapped_column(DecimalText())
    stop_loss: Mapped[Decimal] = mapped_column(DecimalText())
    take_profit: Mapped[Decimal] = mapped_column(DecimalText())
    fees: Mapped[Decimal] = mapped_column(DecimalText())
    gross_pnl: Mapped[Decimal] = mapped_column(DecimalText())
    net_pnl: Mapped[Decimal] = mapped_column(DecimalText())
    result: Mapped[str] = mapped_column(String(20), index=True)
    opened_at: Mapped[datetime] = mapped_column(AwareDateTimeText())
    closed_at: Mapped[datetime] = mapped_column(AwareDateTimeText())
    strategy: Mapped[str] = mapped_column(String(100), index=True)
    exit_reason: Mapped[str] = mapped_column(String(30))
    entry_signal_json: Mapped[str | None] = mapped_column(Text, nullable=True)
