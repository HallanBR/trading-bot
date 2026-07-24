"""Seleção de parâmetros limitada ao passado de cada fold."""

from collections.abc import Callable, Sequence
from decimal import Decimal

from trading_bot.backtest import BacktestConfig, BacktestEngine, BacktestResult
from trading_bot.domain import Candle
from trading_bot.optimization.models import (
    OptimizationConfig,
    OptimizationResult,
    OptimizationTrial,
    StrategyCandidate,
)
from trading_bot.risk import RiskManager


class ControlledOptimizer:
    """Rejeita candidatos frágeis em vez de sempre escolher o menos ruim."""

    def __init__(
        self,
        candidates: Sequence[StrategyCandidate],
        *,
        config: OptimizationConfig | None = None,
        backtest_config: BacktestConfig | None = None,
        risk_manager_factory: Callable[[], RiskManager] | None = None,
    ) -> None:
        self.candidates = tuple(candidates)
        self.config = config or OptimizationConfig()
        self.backtest_config = backtest_config or BacktestConfig()
        self.risk_manager_factory = risk_manager_factory or RiskManager
        if not self.candidates:
            raise ValueError("Ao menos um candidato é necessário.")
        if len(self.candidates) > self.config.maximum_candidates:
            raise ValueError(
                "A grade excede maximum_candidates; reduza a busca para "
                "limitar overfitting e tempo de execução."
            )
        names = [candidate.name for candidate in self.candidates]
        if len(names) != len(set(names)):
            raise ValueError("Os nomes dos candidatos devem ser únicos.")

    def optimize(self, training_candles: Sequence[Candle]) -> OptimizationResult:
        """Usa somente a cauda de validação interna do treino recebido."""

        BacktestEngine._validate_candles(training_candles)
        required = self.config.warmup_size + self.config.validation_size
        if len(training_candles) < required:
            raise ValueError(
                f"Treino insuficiente: recebido {len(training_candles)}, "
                f"necessário {required}."
            )

        validation_start = len(training_candles) - self.config.validation_size
        evaluation_start = validation_start - self.config.warmup_size
        evaluation = training_candles[evaluation_start:]
        trials = tuple(
            self._evaluate(candidate, evaluation) for candidate in self.candidates
        )
        eligible = [trial for trial in trials if trial.eligible]
        best = max(
            eligible,
            key=lambda trial: (
                trial.score,
                self._sortable_profit_factor(trial),
                trial.result.total_trades,
            ),
            default=None,
        )
        return OptimizationResult(
            trials=trials,
            best_trial=best,
            validation_start_index=validation_start,
        )

    def _evaluate(
        self,
        candidate: StrategyCandidate,
        evaluation: Sequence[Candle],
    ) -> OptimizationTrial:
        result = BacktestEngine(
            candidate.build(),
            risk_manager=self.risk_manager_factory(),
            config=self.backtest_config,
        ).run(
            evaluation,
            trade_start_index=self.config.warmup_size,
        )
        rejection = self._rejection_reason(result)
        score = result.return_percent - (
            result.max_drawdown_percent * self.config.drawdown_penalty
        )
        return OptimizationTrial(
            candidate=candidate,
            result=result,
            eligible=rejection is None,
            score=score,
            rejection_reason=rejection,
        )

    def _rejection_reason(self, result: BacktestResult) -> str | None:
        if result.total_trades < self.config.minimum_trades:
            return (
                f"Amostra insuficiente: {result.total_trades} trades; "
                f"mínimo {self.config.minimum_trades}."
            )
        if result.net_profit <= 0:
            return "Lucro líquido não positivo."
        factor = result.profit_factor
        if factor is not None and factor < self.config.minimum_profit_factor:
            return (
                f"Profit factor {factor:.4f} abaixo de "
                f"{self.config.minimum_profit_factor}."
            )
        if result.max_drawdown_percent > self.config.maximum_drawdown_percent:
            return (
                f"Drawdown {result.max_drawdown_percent:.4f}% acima de "
                f"{self.config.maximum_drawdown_percent}%."
            )
        return None

    @staticmethod
    def _sortable_profit_factor(trial: OptimizationTrial) -> Decimal:
        return (
            Decimal("Infinity")
            if trial.result.profit_factor is None
            else trial.result.profit_factor
        )
