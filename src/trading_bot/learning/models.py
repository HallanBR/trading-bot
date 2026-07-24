"""Mapeamentos do banco exclusivo de operações perdedoras."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from trading_bot.persistence.types import AwareDateTimeText, DecimalText


class LearningBase(DeclarativeBase):
    """Base independente do banco operacional e de backtests."""


class LosingTradeModel(LearningBase):
    """Cenário de uma operação virtual encerrada com prejuízo líquido."""

    __tablename__ = "losing_trades"
    __table_args__ = (
        CheckConstraint("result = 'LOSS'", name="ck_losing_trade_result"),
    )

    case_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    schema_version: Mapped[int] = mapped_column(Integer)
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
    result: Mapped[str] = mapped_column(String(20))
    opened_at: Mapped[datetime] = mapped_column(AwareDateTimeText())
    closed_at: Mapped[datetime] = mapped_column(AwareDateTimeText())
    strategy: Mapped[str] = mapped_column(String(100), index=True)
    exit_reason: Mapped[str] = mapped_column(String(30))
    signal_generated_at: Mapped[datetime | None] = mapped_column(
        AwareDateTimeText(),
        nullable=True,
    )
    signal_price: Mapped[Decimal | None] = mapped_column(
        DecimalText(),
        nullable=True,
    )
    signal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    indicators_json: Mapped[str] = mapped_column(Text)
