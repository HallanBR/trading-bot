"""Testes da mensagem enviada ao Discord."""

from dataclasses import replace
from decimal import Decimal

from trading_bot.domain import ExitReason, Trade, TradeResult
from trading_bot.notifications import DiscordTradeFormatter


def test_formatter_builds_green_embed_for_win(winning_trade: Trade) -> None:
    payload = DiscordTradeFormatter().format(winning_trade)

    embed = payload["embeds"][0]
    assert embed["title"] == "🟢 Operação vitoriosa"
    assert embed["color"] == 0x2ECC71
    assert payload["allowed_mentions"] == {"parse": []}
    assert "BTCUSDT" in embed["fields"][0]["value"]
    assert "+9" in embed["fields"][3]["value"]


def test_formatter_builds_red_embed_for_loss(winning_trade: Trade) -> None:
    losing_trade = replace(
        winning_trade,
        exit_price=Decimal(95),
        fees=Decimal(1),
        exit_reason=ExitReason.STOP_LOSS,
    )

    payload = DiscordTradeFormatter().format(losing_trade)

    assert losing_trade.result is TradeResult.LOSS
    assert payload["embeds"][0]["title"] == "🔴 Operação perdedora"
    assert "-6" in payload["embeds"][0]["fields"][3]["value"]


def test_formatter_builds_neutral_embed_for_break_even(
    winning_trade: Trade,
) -> None:
    break_even_trade = replace(
        winning_trade,
        exit_price=Decimal(101),
        fees=Decimal(1),
        exit_reason=ExitReason.STRATEGY,
    )

    payload = DiscordTradeFormatter().format(break_even_trade)

    assert break_even_trade.result is TradeResult.BREAK_EVEN
    assert payload["embeds"][0]["title"] == "⚪ Operação encerrada no zero"
