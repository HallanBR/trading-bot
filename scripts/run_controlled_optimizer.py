"""Executa a prioridade 7 em BTCUSDT 5m sem promover parâmetros frágeis."""

import argparse
import json
import sys
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from trading_bot.backtest import (
    BacktestConfig,
    WalkForwardConfig,
    WalkForwardEngine,
)
from trading_bot.domain import Candle
from trading_bot.market_data import CandleCsvStore
from trading_bot.optimization import (
    ControlledOptimizer,
    NoTradeStrategy,
    OptimizationConfig,
    OptimizationResult,
    ema_rsi_atr_candidates,
)
from trading_bot.strategies import Strategy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=(
            PROJECT_ROOT / "data" / "history" / "BTCUSDT_5m_20260101_20260701.csv"
        ),
    )
    parser.add_argument("--train-size", type=int, default=20_000)
    parser.add_argument("--test-size", type=int, default=5_000)
    parser.add_argument("--validation-size", type=int, default=3_000)
    parser.add_argument("--warmup-size", type=int, default=100)
    parser.add_argument("--minimum-trades", type=int, default=12)
    parser.add_argument("--max-candles", type=int)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "research" / "optimizer_5m.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candles = CandleCsvStore().read(args.csv)
    if not candles or candles[0].interval != "5m":
        raise SystemExit("Este experimento aceita somente candles de 5m.")
    if args.max_candles is not None:
        if args.max_candles <= 0:
            raise SystemExit("--max-candles deve ser positivo.")
        candles = candles[: args.max_candles]

    backtest_config = BacktestConfig(
        initial_equity=Decimal(10_000),
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.0005"),
        strategy_history_limit=max(args.warmup_size, 100),
    )
    optimizer = ControlledOptimizer(
        ema_rsi_atr_candidates(),
        config=OptimizationConfig(
            validation_size=args.validation_size,
            warmup_size=args.warmup_size,
            minimum_trades=args.minimum_trades,
        ),
        backtest_config=backtest_config,
    )
    selections: list[OptimizationResult] = []

    def select_from_training(training: Sequence[Candle]) -> Strategy:
        selection = optimizer.optimize(training)
        selections.append(selection)
        if selection.best_trial is None:
            return NoTradeStrategy()
        return selection.best_trial.candidate.build()

    walk_result = WalkForwardEngine(
        select_from_training,
        config=WalkForwardConfig(
            train_size=args.train_size,
            test_size=args.test_size,
            warmup_size=args.warmup_size,
        ),
        backtest_config=backtest_config,
    ).run(candles)
    if not walk_result.folds:
        raise SystemExit("Histórico insuficiente para formar um fold completo.")

    print(
        f"Otimizador controlado: {len(optimizer.candidates)} candidatos, "
        f"{len(walk_result.folds)} folds externos.\n"
    )
    for fold, selection in zip(walk_result.folds, selections, strict=True):
        best = selection.best_trial
        if best is None:
            chosen = "NENHUM — capital preservado"
            validation = "nenhum candidato elegível"
        else:
            chosen = best.candidate.name
            validation = (
                f"validação {best.result.net_profit:+.2f} USDT, "
                f"{best.result.total_trades} trades"
            )
        print(
            f"Fold {fold.number}: {chosen} | {validation} | "
            f"teste {fold.result.net_profit:+.2f} USDT, "
            f"{fold.result.total_trades} trades"
        )

    print("\nResultado agregado exclusivamente fora da amostra:")
    print(f"Trades: {walk_result.total_trades}")
    print(f"Acerto: {walk_result.win_rate_percent:.2f}%")
    print(f"Lucro líquido: {walk_result.net_profit:+.2f} USDT")
    print(f"Folds positivos: {walk_result.profitable_folds}/{len(walk_result.folds)}")

    report = {
        "source": str(args.csv),
        "interval": "5m",
        "candles": len(candles),
        "costs": {
            "fee_rate": str(backtest_config.fee_rate),
            "slippage_rate": str(backtest_config.slippage_rate),
        },
        "walk_forward": {
            "train_size": args.train_size,
            "test_size": args.test_size,
            "validation_size": args.validation_size,
            "warmup_size": args.warmup_size,
        },
        "folds": [
            _fold_report(fold.number, fold.result.net_profit, selection)
            for fold, selection in zip(
                walk_result.folds,
                selections,
                strict=True,
            )
        ],
        "out_of_sample": {
            "total_trades": walk_result.total_trades,
            "wins": walk_result.wins,
            "losses": walk_result.losses,
            "win_rate_percent": str(walk_result.win_rate_percent),
            "net_profit": str(walk_result.net_profit),
            "profitable_folds": walk_result.profitable_folds,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nRelatório detalhado salvo em: {args.output}")
    return 0


def _fold_report(
    number: int,
    test_net_profit: Decimal,
    selection: OptimizationResult,
) -> dict[str, object]:
    best = selection.best_trial
    return {
        "number": number,
        "selected_candidate": (None if best is None else best.candidate.name),
        "test_net_profit": str(test_net_profit),
        "trials": [
            {
                "candidate": trial.candidate.name,
                "eligible": trial.eligible,
                "rejection_reason": trial.rejection_reason,
                "score": str(trial.score),
                "trades": trial.result.total_trades,
                "net_profit": str(trial.result.net_profit),
                "profit_factor": (
                    None
                    if trial.result.profit_factor is None
                    else str(trial.result.profit_factor)
                ),
                "max_drawdown_percent": str(trial.result.max_drawdown_percent),
            }
            for trial in selection.trials
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
