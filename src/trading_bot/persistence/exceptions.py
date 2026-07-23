"""Erros produzidos pela camada de persistência."""


class PersistenceError(RuntimeError):
    """Falha ao salvar ou recuperar dados persistidos."""


class BacktestNotFoundError(PersistenceError):
    """Execução de backtest não encontrada."""
