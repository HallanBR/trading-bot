"""Erros seguros da camada de notificações."""


class NotificationError(RuntimeError):
    """Falha de notificação sem exposição de credenciais."""


class NotificationRateLimitError(NotificationError):
    """O Discord solicitou redução na frequência de envios."""

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        message = "O Discord limitou temporariamente as notificações."
        if retry_after is not None:
            message += f" Tente novamente em {retry_after:g} segundos."
        super().__init__(message)
