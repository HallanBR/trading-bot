"""Validação walk-forward com treino sempre anterior ao teste."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from trading_bot.backtest.config import BacktestConfig
from trading_bot.backtest.engine import BacktestEngine
from trading_bot.backtest.result import BacktestResult
from trading_bot.domain import Candle
from trading_bot.risk import RiskManager
from trading_bot.strategies import Strategy

StrategyFactory = Callable[[Sequence[Candle]], Strategy]


@dataclass(frozen=True, slots=True)
class WalkForwardConfig:
    """Tamanhos das janelas cronológicas medidos em candles."""

    train_size: int
    test_size: int
    step_size: int | None = None
    warmup_size: int = 300
    anchored_training: bool = False

    def __post_init__(self) -> None:
        values = {
            "train_size": self.train_size,
            "test_size": self.test_size,
            "warmup_size": self.warmup_size,
        }
        if self.step_size is not None:
            values["step_size"] = self.step_size
        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} deve ser inteiro positivo.")

    @property
    def effective_step_size(self) -> int:
        return self.test_size if self.step_size is None else self.step_size


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    """Uma janela de treino e seu período posterior fora da amostra."""

    number: int
    train_start_index: int
    train_end_index: int
    test_start_index: int
    test_end_index: int
    strategy_name: str
    result: BacktestResult


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    """Agregado somente dos períodos de teste de todos os folds."""

    folds: tuple[WalkForwardFold, ...]

    @property
    def total_trades(self) -> int:
        return sum(fold.result.total_trades for fold in self.folds)

    @property
    def wins(self) -> int:
        return sum(fold.result.wins for fold in self.folds)

    @property
    def losses(self) -> int:
        return sum(fold.result.losses for fold in self.folds)

    @property
    def net_profit(self) -> Decimal:
        return sum(
            (fold.result.net_profit for fold in self.folds),
            start=Decimal(0),
        )

    @property
    def win_rate_percent(self) -> Decimal:
        if self.total_trades == 0:
            return Decimal(0)
        return (Decimal(self.wins) / Decimal(self.total_trades)) * Decimal(100)

    @property
    def profitable_folds(self) -> int:
        return sum(fold.result.net_profit > 0 for fold in self.folds)


class WalkForwardEngine:
    """Seleciona no treino e avalia exclusivamente no teste seguinte."""

    def __init__(
        self,
        strategy_factory: StrategyFactory,
        *,
        config: WalkForwardConfig,
        backtest_config: BacktestConfig | None = None,
        risk_manager_factory: Callable[[], RiskManager] | None = None,
    ) -> None:
        self.strategy_factory = strategy_factory
        self.config = config
        self.backtest_config = backtest_config or BacktestConfig()
        self.risk_manager_factory = risk_manager_factory or RiskManager

    def run(self, candles: Sequence[Candle]) -> WalkForwardResult:
        """Executa folds completos; uma sobra menor que o teste é ignorada."""

        BacktestEngine._validate_candles(candles)
        folds: list[WalkForwardFold] = []
        test_start = self.config.train_size
        fold_number = 1
        while test_start + self.config.test_size <= len(candles):
            test_end = test_start + self.config.test_size
            train_start = (
                0
                if self.config.anchored_training
                else test_start - self.config.train_size
            )
            train = candles[train_start:test_start]
            strategy = self.strategy_factory(train)

            warmup_start = max(
                train_start,
                test_start - self.config.warmup_size,
            )
            evaluation = candles[warmup_start:test_end]
            trade_start_index = test_start - warmup_start
            result = BacktestEngine(
                strategy,
                risk_manager=self.risk_manager_factory(),
                config=self.backtest_config,
            ).run(
                evaluation,
                trade_start_index=trade_start_index,
            )
            folds.append(
                WalkForwardFold(
                    number=fold_number,
                    train_start_index=train_start,
                    train_end_index=test_start,
                    test_start_index=test_start,
                    test_end_index=test_end,
                    strategy_name=strategy.name,
                    result=result,
                )
            )
            fold_number += 1
            test_start += self.config.effective_step_size
        return WalkForwardResult(tuple(folds))
