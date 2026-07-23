# Trading Bot

Plataforma modular, em fase inicial, para estudar estratégias quantitativas com
dados históricos, backtesting, paper trading e notificações de resultados no
Discord.

> [!WARNING]
> Este projeto é educacional e experimental. Ele não garante rentabilidade, não
> constitui recomendação financeira e ainda não executa operações com dinheiro
> real.

## Objetivo inicial

O primeiro marco funcional será:

1. importar candles históricos;
2. calcular indicadores técnicos básicos;
3. gerar sinais por uma estratégia configurável;
4. simular entradas, saídas, taxas e slippage;
5. registrar o resultado da operação;
6. avisar pelo Discord se a operação simulada foi vitoriosa ou perdedora.

O Discord será apenas um canal de notificação. A lógica de análise e simulação
permanecerá independente.

## Estrutura

```text
trading-bot/
├── src/trading_bot/
│   ├── backtest/       # Simulação histórica e métricas
│   ├── core/           # Configuração, logs e tipos compartilhados
│   ├── domain/         # Entidades do domínio
│   ├── execution/      # Execução simulada e, futuramente, adaptadores
│   ├── indicators/     # Indicadores técnicos
│   ├── market_data/    # Provedores e validação de dados
│   ├── notifications/  # Notificações, incluindo Discord
│   ├── persistence/    # Banco de dados e repositórios
│   ├── risk/           # Regras de gestão de risco
│   ├── strategies/     # Estratégias isoladas
│   └── trading/        # Orquestração do ciclo das operações
├── tests/              # Testes automatizados
├── data/               # Dados locais não versionados
├── scripts/            # Utilitários de desenvolvimento
├── .env.example
└── pyproject.toml
```

## API pública da Binance

O projeto já possui um provedor inicial para candles do mercado Spot:

```python
from trading_bot.market_data import BinanceMarketDataProvider

with BinanceMarketDataProvider() as binance:
    candles = binance.get_candles("BTCUSDT", "5m", limit=100)
```

Ele usa somente o endpoint público de dados de mercado da Binance. Não requer
chave, não acessa saldo e não envia ordens.

## Indicadores técnicos

O núcleo inicial inclui EMA, RSI e ATR:

```python
from trading_bot.indicators import atr, ema, rsi

closes = [candle.close for candle in candles]

ema_9 = ema(closes, period=9)
rsi_14 = rsi(closes, period=14)
atr_14 = atr(candles, period=14)
```

Os resultados têm o mesmo tamanho da entrada. As posições que ainda não possuem
histórico suficiente recebem `None`, impedindo que estratégias usem dados antes
do período de aquecimento.

## Estratégia inicial

`EmaRsiAtrStrategy` combina:

- cruzamento entre EMA rápida e EMA lenta;
- filtro de RSI configurável;
- stop-loss e take-profit calculados pela volatilidade do ATR.

```python
from trading_bot.strategies import EmaRsiAtrStrategy

strategy = EmaRsiAtrStrategy()
signal = strategy.generate_signal(candles)

print(signal.action, signal.reason)
```

A estratégia somente gera um objeto `Signal` explicável. Ela não possui acesso
a saldo, conta de corretora ou rotas de execução de ordens.

## Escopo desta versão

Esta versão contém somente a fundação do repositório. Ainda não há:

- lógica de compra ou venda;
- integração autenticada com corretoras;
- execução de ordens;
- estratégia pronta;
- uso de dinheiro real.

## Próximas etapas

- Importar e validar candles por CSV.
- Criar o primeiro motor de backtest sem viés de dados futuros.
- Simular custos, slippage e gestão de risco.
- Enviar ao Discord apenas o resultado de operações encerradas.

## Configuração futura

Quando o módulo de notificações for implementado:

```powershell
Copy-Item .env.example .env
```

Preencha `DISCORD_WEBHOOK_URL` no arquivo `.env`. Nunca publique esse endereço
no repositório.

## Licença

Distribuído sob a licença MIT. Consulte [LICENSE](LICENSE).
