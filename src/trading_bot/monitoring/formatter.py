"""Formatação compacta dos eventos de monitoramento."""

from collections.abc import Sequence
from datetime import datetime, timezone, tzinfo

from trading_bot.monitoring.events import MonitoringEvent


class MonitoringFormatter:
    """Produz linhas legíveis e payloads dentro do limite do Discord."""

    def __init__(self, *, display_timezone: tzinfo | None = None) -> None:
        local_timezone = datetime.now().astimezone().tzinfo
        self.display_timezone = display_timezone or local_timezone or timezone.utc

    def line(self, event: MonitoringEvent) -> str:
        """Formata uma linha no fuso horário escolhido."""

        timestamp = event.occurred_at.astimezone(self.display_timezone)
        return f"{timestamp:%H:%M} | {event.symbol} {event.interval} | {event.message}"

    def discord_payload(
        self,
        events: Sequence[MonitoringEvent],
    ) -> dict[str, object]:
        """Agrupa as linhas recentes em uma única mensagem segura."""

        if not events:
            raise ValueError("Ao menos um evento é necessário.")
        all_lines = [self.line(event) for event in events]
        selected: list[str] = []
        current_size = 0
        content_budget = 1_650
        for line in reversed(all_lines):
            next_size = current_size + len(line) + 1
            if selected and next_size > content_budget:
                break
            selected.append(line[:content_budget])
            current_size = next_size
        selected.reverse()
        omitted = len(all_lines) - len(selected)
        if omitted:
            selected.insert(0, f"... {omitted} eventos anteriores resumidos ...")
        body = "\n".join(selected)
        return {
            "content": f"**Monitoramento do Trading Bot**\n```text\n{body}\n```",
            "allowed_mentions": {"parse": []},
        }
