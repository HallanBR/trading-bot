"""Persistência SQLite de backtests e operações."""

from trading_bot.persistence.database import Database
from trading_bot.persistence.exceptions import (
    BacktestNotFoundError,
    PersistenceError,
)
from trading_bot.persistence.records import BacktestSummary
from trading_bot.persistence.repositories import BacktestRepository

__all__ = [
    "BacktestNotFoundError",
    "BacktestRepository",
    "BacktestSummary",
    "Database",
    "PersistenceError",
]
