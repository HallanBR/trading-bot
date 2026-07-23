"""Erros produzidos pelos provedores de dados de mercado."""


class MarketDataError(RuntimeError):
    """Erro base ao consultar ou interpretar dados de mercado."""


class BinanceAPIError(MarketDataError):
    """Resposta de erro recebida da API pública da Binance."""


class BinanceResponseError(MarketDataError):
    """Resposta da Binance em formato inesperado."""
