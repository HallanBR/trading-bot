"""Executa paper trading contínuo usando somente dados públicos da Binance."""

import argparse
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from threading import Event

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from trading_bot.execution import FillSimulator, PaperExecutor
from trading_bot.learning import LearningDatabase, LosingTradeRepository
from trading_bot.market_data import BinanceMarketDataProvider
from trading_bot.monitoring import (
    ConsoleMonitoringNotifier,
    DiscordMonitoringNotifier,
    MonitoringEvent,
    MonitoringEventType,
    MonitoringService,
)
from trading_bot.notifications import (
    DiscordSettings,
    DiscordWebhookNotifier,
    NotificationService,
)
from trading_bot.persistence import (
    Database,
    PaperSessionRepository,
    build_paper_session_id,
)
from trading_bot.risk import RiskManager
from trading_bot.strategies import STRATEGY_BUILDERS, create_strategy
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
    parser.add_argument(
        "--strategy",
        choices=tuple(STRATEGY_BUILDERS),
        default="base",
        help="Estratégia paper. Compare no walk-forward antes de trocar a base.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    symbol = args.symbol.upper()
    strategy = create_strategy(args.strategy)
    learning_path = PROJECT_ROOT / "data" / "losing_trades.db"
    operational_path = PROJECT_ROOT / "data" / "trading_bot.db"
    settings = DiscordSettings.from_env_file(PROJECT_ROOT / ".env")
    discord = DiscordWebhookNotifier.from_settings(settings)
    monitoring_discord = (
        None
        if settings.discord_monitoring_webhook_url is None
        else DiscordMonitoringNotifier(settings.discord_monitoring_webhook_url)
    )
    console_monitoring = ConsoleMonitoringNotifier()
    monitoring = (
        MonitoringService([console_monitoring])
        if monitoring_discord is None
        else MonitoringService([console_monitoring, monitoring_discord])
    )
    provider = BinanceMarketDataProvider()
    learning_database = LearningDatabase.from_path(learning_path)
    learning_database.create_schema()
    losing_trades = LosingTradeRepository(learning_database)
    operational_database = Database.from_path(operational_path)
    operational_database.create_schema()
    paper_sessions = PaperSessionRepository(operational_database)
    session_id = build_paper_session_id(symbol, args.interval, strategy.name)
    executor = PaperExecutor(
        initial_equity=args.initial_equity,
        risk_manager=RiskManager(),
        fills=FillSimulator(
            fee_rate=Decimal("0.001"),
            slippage_rate=Decimal("0.0005"),
        ),
    )
    engine = PaperTradingEngine(
        strategy,
        executor,
        notifications=NotificationService([discord]),
        losing_trades=losing_trades,
        checkpoint_store=paper_sessions,
        session_id=session_id,
        max_history=args.lookback,
    )
    restored_state = paper_sessions.load_state(session_id)
    if restored_state is not None:
        engine.restore_state(restored_state)
    runner = PaperTradingRunner(
        provider,
        engine,
        config=PaperTradingConfig(
            symbol=symbol,
            interval=args.interval,
            lookback=args.lookback,
            poll_seconds=args.poll_seconds,
        ),
        monitoring=monitoring,
    )
    stop_event = Event()
    print("Paper trading iniciado. Pressione Ctrl+C para encerrar.")
    print(f"Sessão: {session_id}")
    print(f"Estratégia: {strategy.name}")
    print(f"Estado e operações serão armazenados em: {operational_path}")
    print(f"Perdas serão armazenadas em: {learning_path}")
    if monitoring_discord is None:
        print(
            "Discord de monitoramento não configurado; "
            "o acompanhamento continuará no terminal."
        )
    else:
        print("Discord de monitoramento configurado em canal separado.")
    if restored_state is not None:
        restored_event = MonitoringEvent(
            event_type=MonitoringEventType.SESSION_RESTORED,
            occurred_at=datetime.now(timezone.utc),
            symbol=symbol,
            interval=args.interval,
            message="Sessão anterior restaurada com sucesso.",
        )
        for result in monitoring.publish([restored_event]):
            if not result.success:
                print(f"Falha no canal {result.channel}: {result.error}")
    try:
        runner.run_forever(stop_event)
    except KeyboardInterrupt:
        stop_event.set()
        print("Paper trading encerrado.")
    finally:
        provider.close()
        discord.close()
        if monitoring_discord is not None:
            monitoring_discord.close()
        learning_database.dispose()
        operational_database.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
