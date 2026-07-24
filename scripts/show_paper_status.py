"""Mostra o checkpoint e o histórico da sessão paper sem iniciar o robô."""

import argparse
import sys
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from trading_bot.persistence import (
    Database,
    PaperSessionRepository,
    build_paper_session_id,
)
from trading_bot.strategies import STRATEGY_BUILDERS, create_strategy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="5m")
    parser.add_argument(
        "--strategy",
        choices=tuple(STRATEGY_BUILDERS),
        default="base",
    )
    parser.add_argument("--initial-equity", type=Decimal, default=Decimal(10_000))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    symbol = args.symbol.upper()
    strategy = create_strategy(args.strategy)
    session_id = build_paper_session_id(symbol, args.interval, strategy.name)
    database = Database.from_path(PROJECT_ROOT / "data" / "trading_bot.db")
    database.create_schema()
    sessions = PaperSessionRepository(database)
    try:
        state = sessions.load_state(session_id)
        counts = sessions.trade_counts(session_id)
        print(f"Sessão: {session_id}")
        print(
            f"Operações: {counts.total} | Vitórias: {counts.wins} | "
            f"Derrotas: {counts.losses} | Empates: {counts.break_even}"
        )
        if state is None:
            print(f"Capital virtual: {args.initial_equity:.2f}")
            print("Resultado acumulado: +0.00 USDT (0.0000%)")
            print("Estado: sessão ainda não iniciada.")
            return 0
        account = state.executor
        net_result = account.equity - args.initial_equity
        net_percent = (net_result / args.initial_equity) * Decimal(100)
        print(f"Capital virtual: {account.equity:.2f}")
        print(f"Resultado acumulado: {net_result:+.2f} USDT ({net_percent:+.4f}%)")
        print(f"Último candle: {state.last_processed_open_time}")
        if account.open_position is not None:
            position = account.open_position
            print(
                f"Posição aberta: {position.side.value} "
                f"{position.symbol} em {position.entry_price}"
            )
        elif account.pending_signal is not None:
            print(f"Sinal pendente: {account.pending_signal.action.value}")
        else:
            print("Posição: aguardando sinal.")
    finally:
        database.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
