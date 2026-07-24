"""Mostra um resumo seguro do banco separado de operações perdedoras."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from trading_bot.learning import LearningDatabase, LosingTradeRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = PROJECT_ROOT / "data" / "losing_trades.db"
    database = LearningDatabase.from_path(path)
    database.create_schema()
    repository = LosingTradeRepository(database)
    try:
        cases = repository.list_recent(limit=args.limit)
        print(f"Operações perdedoras armazenadas: {repository.count()}")
        for case in cases:
            print(
                f"- {case.closed_at.isoformat()} | {case.symbol} "
                f"{case.interval} | {case.side.value} | "
                f"resultado líquido {case.net_pnl}"
            )
    finally:
        database.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
