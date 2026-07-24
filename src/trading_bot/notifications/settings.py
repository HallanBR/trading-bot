"""Carregamento seguro das configurações do Discord."""

from pathlib import Path
from urllib.parse import urlparse

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


class DiscordSettings(BaseSettings):
    """Configuração carregada do ambiente sem revelar o webhook em logs."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_webhook_url: SecretStr
    discord_monitoring_webhook_url: SecretStr | None = None
    discord_research_webhook_url: SecretStr | None = None

    @field_validator("discord_webhook_url")
    @classmethod
    def validate_webhook_url(cls, value: SecretStr) -> SecretStr:
        """Rejeita convites e URLs que não sejam webhooks HTTPS do Discord."""

        cls._require_discord_webhook(value, "DISCORD_WEBHOOK_URL")
        return value

    @field_validator(
        "discord_monitoring_webhook_url",
        "discord_research_webhook_url",
        mode="before",
    )
    @classmethod
    def empty_optional_webhook_is_disabled(cls, value: object) -> object:
        """Interpreta uma configuração opcional vazia como canal desativado."""

        return None if value == "" else value

    @field_validator("discord_monitoring_webhook_url")
    @classmethod
    def validate_monitoring_webhook_url(
        cls,
        value: SecretStr | None,
    ) -> SecretStr | None:
        """Valida separadamente o webhook exclusivo de monitoramento."""

        if value is not None:
            cls._require_discord_webhook(
                value,
                "DISCORD_MONITORING_WEBHOOK_URL",
            )
        return value

    @field_validator("discord_research_webhook_url")
    @classmethod
    def validate_research_webhook_url(
        cls,
        value: SecretStr | None,
    ) -> SecretStr | None:
        """Valida o canal reservado a relatórios e pesquisas de estratégia."""

        if value is not None:
            cls._require_discord_webhook(
                value,
                "DISCORD_RESEARCH_WEBHOOK_URL",
            )
        return value

    @staticmethod
    def _require_discord_webhook(value: SecretStr, variable_name: str) -> None:
        parsed = urlparse(value.get_secret_value())
        valid_hosts = {"discord.com", "discordapp.com"}
        path_parts = [part for part in parsed.path.split("/") if part]
        valid_path = len(path_parts) >= 4 and path_parts[:2] == ["api", "webhooks"]
        if (
            parsed.scheme != "https"
            or parsed.hostname not in valid_hosts
            or not valid_path
        ):
            raise ValueError(f"{variable_name} não é um webhook válido do Discord.")

    @model_validator(mode="after")
    def require_distinct_channels(self) -> Self:
        """Impede que resultados e atividade sejam enviados ao mesmo canal."""

        configured = [
            self.discord_webhook_url.get_secret_value(),
            *(
                webhook.get_secret_value()
                for webhook in (
                    self.discord_monitoring_webhook_url,
                    self.discord_research_webhook_url,
                )
                if webhook is not None
            ),
        ]
        if len(configured) != len(set(configured)):
            raise ValueError("Todos os webhooks configurados devem ser diferentes.")
        return self

    @classmethod
    def from_env_file(cls, path: str | Path) -> "DiscordSettings":
        """Carrega um arquivo específico, útil fora do diretório do projeto."""

        return cls(_env_file=path)  # type: ignore[call-arg]
