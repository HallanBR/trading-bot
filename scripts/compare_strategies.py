"""Compara estratégias em janelas walk-forward fora da amostra."""

import argparse
import sys
from collections.abc import Callable, Sequence
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
from trading_bot.strategies import STRATEGY_BUILDERS, Strategy


def constant_strategy_factory(
    builder: Callable[[], Strategy],
) -> Callable[[Sequence[Candle]], Strategy]:
    """Adapta uma estratégia fixa ao contrato futuro do otimizador."""

    def factory(_train: Sequence[Candle]) -> Strategy:
        return builder()

    return factory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--train-size", type=int, default=20_000)
    parser.add_argument("--test-size", type=int, default=5_000)
    parser.add_argument("--step-size", type=int)
    parser.add_argument("--warmup-size", type=int, default=300)
    parser.add_argument(
        "--max-candles",
        type=int,
        help="Recorte diagnóstico a partir do início do CSV.",
    )
    parser.add_argument(
        "--strategies",
        nargs="+",
        choices=tuple(STRATEGY_BUILDERS),
        default=list(STRATEGY_BUILDERS),
    )
    parser.add_argument("--initial-equity", type=Decimal, default=Decimal(10_000))
    parser.add_argument("--fee-rate", type=Decimal, default=Decimal("0.001"))
    parser.add_argument("--slippage-rate", type=Decimal, default=Decimal("0.0005"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candles = CandleCsvStore().read(args.csv)
    if args.max_candles is not None:
        if args.max_candles <= 0:
            raise SystemExit("--max-candles deve ser positivo.")
        candles = candles[: args.max_candles]
    walk_config = WalkForwardConfig(
        train_size=args.train_size,
        test_size=args.test_size,
        step_size=args.step_size,
        warmup_size=args.warmup_size,
    )
    backtest_config = BacktestConfig(
        initial_equity=args.initial_equity,
        fee_rate=args.fee_rate,
        slippage_rate=args.slippage_rate,
        strategy_history_limit=max(args.warmup_size, 100),
    )

    minimum = args.train_size + args.test_size
    if len(candles) < minimum:
        raise SystemExit(
            f"O CSV tem {len(candles)} candles; são necessários ao menos {minimum}."
        )

    print(f"Comparando {len(args.strategies)} estratégias em {len(candles)} candles.")
    print("Somente os períodos de teste entram nas métricas abaixo.\n")
    heading = (
        f"{'Estratégia':<28} {'Folds':>5} {'Trades':>7} "
        f"{'Acerto':>9} {'Lucro líquido':>15} {'Folds +':>9}"
    )
    print(heading)
    print("-" * len(heading))

    summaries: list[tuple[str, Decimal]] = []
    for strategy_key in args.strategies:
        builder = STRATEGY_BUILDERS[strategy_key]
        result = WalkForwardEngine(
            constant_strategy_factory(builder),
            config=walk_config,
            backtest_config=backtest_config,
        ).run(candles)
        strategy_name = builder().name
        summaries.append((strategy_key, result.net_profit))
        print(
            f"{strategy_name:<28} {len(result.folds):>5} "
            f"{result.total_trades:>7} "
            f"{result.win_rate_percent:>8.2f}% "
            f"{result.net_profit:>15.2f} "
            f"{result.profitable_folds:>4}/{len(result.folds):<4}"
        )

    ordered = sorted(summaries, key=lambda item: item[1], reverse=True)
    print("\nRanking preliminar por lucro líquido fora da amostra:")
    for position, (name, net_profit) in enumerate(ordered, start=1):
        print(f"{position}. {name}: {net_profit:+.2f}")
    print(
        "\nResultado histórico não garante lucro futuro. "
        "O ranking serve para rejeitar candidatos fracos, não para prometer ganhos."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
