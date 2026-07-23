"""Canais de notificação de operações encerradas."""

from trading_bot.notifications.discord import DiscordWebhookNotifier
from trading_bot.notifications.exceptions import (
    NotificationError,
    NotificationRateLimitError,
)
from trading_bot.notifications.formatter import DiscordTradeFormatter
from trading_bot.notifications.service import (
    NotificationResult,
    NotificationService,
)
from trading_bot.notifications.settings import DiscordSettings

__all__ = [
    "DiscordSettings",
    "DiscordTradeFormatter",
    "DiscordWebhookNotifier",
    "NotificationError",
    "NotificationRateLimitError",
    "NotificationResult",
    "NotificationService",
]
