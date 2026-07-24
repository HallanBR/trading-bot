"""Estado persistível e contrato de checkpoints do paper trading."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from trading_bot.domain import Candle, Trade
from trading_bot.execution import PaperExecutorState


@dataclass(frozen=True, slots=True)
class PaperTradingState:
    """Checkpoint completo do motor e de sua conta virtual."""

    strategy_name: str
    max_history: int
    initialized: bool
    history: tuple[Candle, ...]
    last_processed_open_time: datetime | None
    executor: PaperExecutorState

    def __post_init__(self) -> None:
        if not self.strategy_name:
            raise ValueError("strategy_name é obrigatório.")
        if self.max_history <= 1:
            raise ValueError("max_history deve ser maior que um.")
        if len(self.history) > self.max_history:
            raise ValueError("O histórico excede o limite do checkpoint.")
        if self.initialized and (
            not self.history or self.last_processed_open_time is None
        ):
            raise ValueError("Uma sessão inicializada exige histórico e cursor.")
        if not self.initialized and (
            self.history or self.last_processed_open_time is not None
        ):
            raise ValueError("Uma sessão não inicializada não pode ter histórico.")


class PaperCheckpointStore(Protocol):
    """Destino transacional para estado e operações recém-encerradas."""

    def save_checkpoint(
        self,
        session_id: str,
        state: PaperTradingState,
        trades: Sequence[Trade] = (),
    ) -> int:
        """Salva o estado e retorna quantos trades novos foram registrados."""
