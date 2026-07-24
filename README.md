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
│   ├── learning/       # Banco isolado de exemplos para aprendizado futuro
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

## Gestão de risco

Antes de aceitar um sinal, `RiskManager` verifica limites globais e calcula a
quantidade simulada:

```python
from decimal import Decimal

from trading_bot.risk import RiskContext, RiskManager

context = RiskContext(
    account_equity=Decimal("10000"),
    day_start_equity=Decimal("10000"),
)
assessment = RiskManager().evaluate(signal, context)
```

Os limites padrão incluem 1% de risco por operação, 3% de perda diária, cinco
operações por dia, três perdas consecutivas e uma posição simultânea. Todos são
configuráveis e devem ser validados por backtest antes de qualquer uso.

## Backtest

O motor executa sinais somente na abertura do candle seguinte e inclui custos
configuráveis:

```python
from trading_bot.backtest import BacktestEngine

engine = BacktestEngine(strategy)
result = engine.run(candles)

print(result.net_profit)
print(result.win_rate_percent)
print(result.max_drawdown_percent)
```

O resultado inclui trades, lucro líquido, retorno percentual, taxa de acerto,
drawdown, profit factor, curva de capital e sinais rejeitados pelo risco. Se
stop e alvo forem tocados no mesmo candle, o motor considera primeiro o stop,
uma hipótese conservadora necessária quando não existem dados de ticks.

## Persistência SQLite

Resultados e trades podem ser gravados atomicamente em um banco local:

```python
from trading_bot.persistence import BacktestRepository, Database

database = Database.from_path("data/trading_bot.db")
database.create_schema()

repository = BacktestRepository(database)
run_id = repository.save(
    result,
    strategy=strategy.name,
    symbol="BTCUSDT",
    interval="5m",
)
```

Valores `Decimal` são armazenados como texto exato e datas são normalizadas em
UTC, evitando conversões silenciosas para ponto flutuante ou timestamps sem
fuso. Cada resultado e seus trades são salvos na mesma transação.

## Notificações no Discord

O webhook é carregado exclusivamente do `.env` e mantido como segredo:

```python
from trading_bot.notifications import (
    DiscordSettings,
    DiscordWebhookNotifier,
    NotificationService,
)

settings = DiscordSettings()
discord = DiscordWebhookNotifier.from_settings(settings)
notifications = NotificationService([discord])

results = notifications.notify_trade(trade)
discord.close()
```

O serviço aceita somente objetos `Trade`, portanto sinais e posições abertas
não geram mensagens. Falhas do Discord são retornadas como resultados seguros,
sem interromper outros canais e sem incluir a URL do webhook nos erros.
Backtests não enviam notificações automaticamente.

## Paper trading

O runner consulta candles públicos periodicamente e mantém apenas uma conta
virtual. Na primeira consulta ele aquece o histórico sem criar operações
retroativas; depois processa cada candle fechado uma única vez.

```powershell
python scripts/run_paper_trading.py --symbol BTCUSDT --interval 5m
```

Interrompa com `Ctrl+C`. O ciclo:

1. ignora o candle ainda em formação;
2. gera o sinal no fechamento;
3. simula a entrada na abertura do candle seguinte;
4. monitora stop e alvo;
5. notifica o Discord somente quando o trade virtual termina.

O script não contém cliente autenticado da Binance, chave de corretora nem
qualquer método de criação de ordens.

## Banco de operações perdedoras

Durante o paper trading, cada operação com resultado líquido negativo é gravada
automaticamente em um banco SQLite separado:

```text
data/losing_trades.db
```

O registro preserva preços, quantidade, taxas, lucro/prejuízo bruto e líquido,
horários, estratégia, motivo do sinal e os indicadores técnicos disponíveis no
momento da entrada. Vitórias e empates não entram nesse banco, e um identificador
estável impede que a mesma perda seja gravada duas vezes.

Para consultar um resumo sem abrir o arquivo SQLite:

```powershell
python scripts/show_losing_trades.py
```

O arquivo fica somente no computador e é ignorado pelo Git. Esta etapa apenas
constrói o conjunto de exemplos; ela ainda não treina modelos nem altera a
estratégia automaticamente. Antes do aprendizado, também serão coletadas
operações vencedoras em um conjunto de comparação, porque um modelo não pode
aprender a diferença entre sucesso e fracasso observando somente perdas.

## Escopo desta versão

Ainda não há:

- integração autenticada com corretoras;
- execução de ordens;
- garantia de rentabilidade;
- uso de dinheiro real.

## Próximas etapas

- Importar e validar candles por CSV.
- Persistir o estado da sessão paper para recuperação após reinicialização.
- Criar o conjunto de comparação de vitórias e a validação temporal do modelo.

## Configuração futura

Para manter configurações sensíveis apenas no computador:

```powershell
Copy-Item .env.example .env
```

Preencha `DISCORD_WEBHOOK_URL` no arquivo `.env`. O arquivo `.env` é ignorado
pelo Git; `.env.example` deve permanecer sempre sem credenciais.

## Licença

Distribuído sob a licença MIT. Consulte [LICENSE](LICENSE).
