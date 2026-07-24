"""Mostra o checkpoint e o histórico da sessão paper sem iniciar o robô."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from trading_bot.persistence import (
    Database,
    PaperSessionRepository,
    build_paper_session_id,
)
from trading_bot.strategies import EmaRsiAtrStrategy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="5m")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    symbol = args.symbol.upper()
    strategy = EmaRsiAtrStrategy()
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
            print("Estado: sessão ainda não iniciada.")
            return 0
        account = state.executor
        print(f"Capital virtual: {account.equity}")
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
