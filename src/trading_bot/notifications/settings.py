"""Carregamento seguro das configurações do Discord."""

from pathlib import Path
from urllib.parse import urlparse

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DiscordSettings(BaseSettings):
    """Configuração carregada do ambiente sem revelar o webhook em logs."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_webhook_url: SecretStr

    @field_validator("discord_webhook_url")
    @classmethod
    def validate_webhook_url(cls, value: SecretStr) -> SecretStr:
        """Rejeita convites e URLs que não sejam webhooks HTTPS do Discord."""

        parsed = urlparse(value.get_secret_value())
        valid_hosts = {"discord.com", "discordapp.com"}
        path_parts = [part for part in parsed.path.split("/") if part]
        valid_path = len(path_parts) >= 4 and path_parts[:2] == ["api", "webhooks"]
        if (
            parsed.scheme != "https"
            or parsed.hostname not in valid_hosts
            or not valid_path
        ):
            raise ValueError("DISCORD_WEBHOOK_URL não é um webhook válido do Discord.")
        return value

    @classmethod
    def from_env_file(cls, path: str | Path) -> "DiscordSettings":
        """Carrega um arquivo específico, útil fora do diretório do projeto."""

        return cls(_env_file=path)  # type: ignore[call-arg]
