"""Executa paper trading contínuo usando somente dados públicos da Binance."""

import argparse
import sys
from decimal import Decimal
from pathlib import Path
from threading import Event

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from trading_bot.execution import FillSimulator, PaperExecutor
from trading_bot.learning import LearningDatabase, LosingTradeRepository
from trading_bot.market_data import BinanceMarketDataProvider
from trading_bot.notifications import (
    DiscordSettings,
    DiscordWebhookNotifier,
    NotificationService,
)
from trading_bot.risk import RiskManager
from trading_bot.strategies import EmaRsiAtrStrategy
from trading_bot.trading import (
    PaperTradingConfig,
    PaperTradingEngine,
    PaperTradingRunner,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="5m")
    parser.add_argument("--lookback", type=int, default=300)
    parser.add_argument("--poll-seconds", type=float, default=30.0)
    parser.add_argument("--initial-equity", type=Decimal, default=Decimal(10_000))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    learning_path = PROJECT_ROOT / "data" / "losing_trades.db"
    settings = DiscordSettings.from_env_file(PROJECT_ROOT / ".env")
    discord = DiscordWebhookNotifier.from_settings(settings)
    provider = BinanceMarketDataProvider()
    learning_database = LearningDatabase.from_path(learning_path)
    learning_database.create_schema()
    losing_trades = LosingTradeRepository(learning_database)
    executor = PaperExecutor(
        initial_equity=args.initial_equity,
        risk_manager=RiskManager(),
        fills=FillSimulator(
            fee_rate=Decimal("0.001"),
            slippage_rate=Decimal("0.0005"),
        ),
    )
    engine = PaperTradingEngine(
        EmaRsiAtrStrategy(),
        executor,
        notifications=NotificationService([discord]),
        losing_trades=losing_trades,
        max_history=args.lookback,
    )
    runner = PaperTradingRunner(
        provider,
        engine,
        config=PaperTradingConfig(
            symbol=args.symbol.upper(),
            interval=args.interval,
            lookback=args.lookback,
            poll_seconds=args.poll_seconds,
        ),
    )
    stop_event = Event()
    print("Paper trading iniciado. Pressione Ctrl+C para encerrar.")
    print(f"Perdas serão armazenadas em: {learning_path}")
    try:
        runner.run_forever(stop_event)
    except KeyboardInterrupt:
        stop_event.set()
        print("Paper trading encerrado.")
    finally:
        provider.close()
        discord.close()
        learning_database.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
