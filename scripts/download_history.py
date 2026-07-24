"""Baixa candles públicos paginados da Binance e grava um CSV validado."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from trading_bot.market_data import BinanceMarketDataProvider, CandleCsvStore


def parse_datetime(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Use uma data ISO, por exemplo 2026-01-01 ou 2026-01-01T00:00:00+00:00."
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="1m")
    parser.add_argument("--start", type=parse_datetime, required=True)
    parser.add_argument("--end", type=parse_datetime, required=True)
    parser.add_argument("--page-limit", type=int, default=1_000)
    parser.add_argument("--max-candles", type=int)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    symbol = args.symbol.strip().upper()
    output = args.output or (
        PROJECT_ROOT
        / "data"
        / "history"
        / (f"{symbol}_{args.interval}_{args.start:%Y%m%d}_{args.end:%Y%m%d}.csv")
    )

    print(
        f"Baixando {symbol} {args.interval} de "
        f"{args.start.isoformat()} até {args.end.isoformat()}..."
    )
    with BinanceMarketDataProvider() as provider:
        candles = provider.get_historical_candles(
            symbol,
            args.interval,
            start_time=args.start,
            end_time=args.end,
            page_limit=args.page_limit,
            max_candles=args.max_candles,
        )
    if not candles:
        print("Nenhum candle foi retornado; nenhum arquivo foi alterado.")
        return 1

    destination = CandleCsvStore().write(output, candles)
    print(f"{len(candles)} candles validados e salvos em: {destination}")
    print(
        f"Período efetivo: {candles[0].open_time.isoformat()} "
        f"até {candles[-1].close_time.isoformat()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
