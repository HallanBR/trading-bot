"""Testes do carregamento seguro do webhook."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from trading_bot.notifications import DiscordSettings


def test_settings_load_webhook_from_specific_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    fake_webhook = "https://discord.com/api/" + "webhooks/123/secret-token"
    env_file.write_text(
        f"DISCORD_WEBHOOK_URL={fake_webhook}\n",
        encoding="utf-8",
    )

    settings = DiscordSettings.from_env_file(env_file)

    assert settings.discord_webhook_url.get_secret_value().endswith("secret-token")
    assert "secret-token" not in repr(settings)


def test_settings_reject_discord_invite() -> None:
    with pytest.raises(ValidationError, match="webhook válido"):
        DiscordSettings(discord_webhook_url="https://discord.gg/invite")


def test_settings_reject_non_discord_host() -> None:
    with pytest.raises(ValidationError, match="webhook válido"):
        fake_webhook = "https://example.com/api/" + "webhooks/123/token"
        DiscordSettings(discord_webhook_url=fake_webhook)
