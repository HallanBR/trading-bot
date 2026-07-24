"""Execução simulada e adaptadores futuros."""

from trading_bot.execution.paper_executor import PaperAccountSnapshot, PaperExecutor
from trading_bot.execution.simulator import FillSimulator

__all__ = ["FillSimulator", "PaperAccountSnapshot", "PaperExecutor"]
