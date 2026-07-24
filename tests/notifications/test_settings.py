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
    assert settings.discord_monitoring_webhook_url is None
    assert settings.discord_research_webhook_url is None


def test_settings_load_separate_monitoring_webhook(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    results_webhook = "https://discord.com/api/" + "webhooks/123/results-token"
    monitoring_webhook = "https://discord.com/api/" + "webhooks/456/monitoring-token"
    env_file.write_text(
        (
            f"DISCORD_WEBHOOK_URL={results_webhook}\n"
            f"DISCORD_MONITORING_WEBHOOK_URL={monitoring_webhook}\n"
        ),
        encoding="utf-8",
    )

    settings = DiscordSettings.from_env_file(env_file)

    assert settings.discord_monitoring_webhook_url is not None
    assert settings.discord_monitoring_webhook_url.get_secret_value().endswith(
        "monitoring-token"
    )
    assert "monitoring-token" not in repr(settings)


def test_settings_reject_discord_invite() -> None:
    with pytest.raises(ValidationError, match="webhook válido"):
        DiscordSettings(discord_webhook_url="https://discord.gg/invite")


def test_settings_reject_non_discord_host() -> None:
    with pytest.raises(ValidationError, match="webhook válido"):
        fake_webhook = "https://example.com/api/" + "webhooks/123/token"
        DiscordSettings(discord_webhook_url=fake_webhook)


def test_settings_reject_monitoring_invite() -> None:
    results_webhook = "https://discord.com/api/" + "webhooks/123/results-token"
    with pytest.raises(ValidationError, match="DISCORD_MONITORING_WEBHOOK_URL"):
        DiscordSettings(
            discord_webhook_url=results_webhook,
            discord_monitoring_webhook_url="https://discord.gg/invite",
        )


def test_settings_reject_same_webhook_for_both_channels() -> None:
    webhook = "https://discord.com/api/" + "webhooks/123/shared-token"

    with pytest.raises(ValidationError, match="devem ser diferentes"):
        DiscordSettings(
            discord_webhook_url=webhook,
            discord_monitoring_webhook_url=webhook,
        )


def test_settings_load_third_research_webhook(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    results_webhook = "https://discord.com/api/webhooks/123/results-token"
    research_webhook = "https://discord.com/api/webhooks/789/research-token"
    env_file.write_text(
        (
            f"DISCORD_WEBHOOK_URL={results_webhook}\n"
            f"DISCORD_RESEARCH_WEBHOOK_URL={research_webhook}\n"
        ),
        encoding="utf-8",
    )

    settings = DiscordSettings.from_env_file(env_file)

    assert settings.discord_research_webhook_url is not None
    assert settings.discord_research_webhook_url.get_secret_value().endswith(
        "research-token"
    )
    assert "research-token" not in repr(settings)
