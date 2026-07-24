"""Modelos imutáveis do otimizador controlado."""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from trading_bot.backtest import BacktestResult
from trading_bot.strategies import Strategy


@dataclass(frozen=True, slots=True)
class StrategyCandidate:
    """Um conjunto nomeado de parâmetros capaz de construir uma estratégia."""

    name: str
    build: Callable[[], Strategy]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("O candidato deve possuir nome.")


@dataclass(frozen=True, slots=True)
class OptimizationTrial:
    """Resultado de validação de um candidato dentro do período de treino."""

    candidate: StrategyCandidate
    result: BacktestResult
    eligible: bool
    score: Decimal
    rejection_reason: str | None = None


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    """Todos os testes e o melhor candidato que cumpriu os critérios."""

    trials: tuple[OptimizationTrial, ...]
    best_trial: OptimizationTrial | None
    validation_start_index: int


@dataclass(frozen=True, slots=True)
class OptimizationConfig:
    """Limites que impedem escolher um candidato apenas por lucro aparente."""

    validation_size: int = 3_000
    warmup_size: int = 100
    minimum_trades: int = 12
    minimum_profit_factor: Decimal = Decimal("1.10")
    maximum_drawdown_percent: Decimal = Decimal(10)
    drawdown_penalty: Decimal = Decimal("0.50")
    maximum_candidates: int = 24

    def __post_init__(self) -> None:
        integers = {
            "validation_size": self.validation_size,
            "warmup_size": self.warmup_size,
            "minimum_trades": self.minimum_trades,
            "maximum_candidates": self.maximum_candidates,
        }
        for name, value in integers.items():
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} deve ser inteiro positivo.")
        if self.minimum_profit_factor <= 0:
            raise ValueError("minimum_profit_factor deve ser positivo.")
        if self.maximum_drawdown_percent <= 0:
            raise ValueError("maximum_drawdown_percent deve ser positivo.")
        if self.drawdown_penalty < 0:
            raise ValueError("drawdown_penalty não pode ser negativo.")
