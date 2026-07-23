"""Testes do serviço resiliente de notificações."""

from dataclasses import dataclass

from trading_bot.domain import Trade
from trading_bot.notifications import NotificationError, NotificationService


@dataclass
class FakeNotifier:
    name: str
    should_fail: bool = False
    calls: int = 0

    def notify_trade(self, trade: Trade) -> None:
        del trade
        self.calls += 1
        if self.should_fail:
            raise NotificationError("Falha controlada.")


def test_service_attempts_all_channels_when_one_fails(
    winning_trade: Trade,
) -> None:
    failing = FakeNotifier("failing", should_fail=True)
    working = FakeNotifier("working")
    service = NotificationService([failing, working])

    results = service.notify_trade(winning_trade)

    assert failing.calls == 1
    assert working.calls == 1
    assert results[0].success is False
    assert results[0].error == "Falha controlada."
    assert results[1].success is True
