# Trading Bot

Plataforma modular, em fase inicial, para estudar estratégias quantitativas com
dados históricos, backtesting, paper trading e notificações de resultados no
Discord.

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
│   ├── monitoring/     # Atividade no terminal e no Discord
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

O mesmo arquivo `data/trading_bot.db` mantém um checkpoint separado para cada
combinação de ativo, intervalo e estratégia. Após cada candle, o estado completo
da conta virtual e os trades recém-encerrados são atualizados atomicamente.
Assim, saldo, posição aberta, sinal pendente, limites diários, histórico e último
candle podem ser restaurados depois de uma reinicialização.

## Notificações no Discord

Os webhooks são carregados exclusivamente do `.env` e mantidos como segredo:

```dotenv
# Canal que recebe somente vitórias, derrotas e empates
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Outro canal, dedicado à atividade operacional
DISCORD_MONITORING_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

Os endereços devem pertencer a webhooks diferentes. Se o segundo não estiver
configurado, o monitoramento continua normalmente no terminal.

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

O serviço de resultados aceita somente objetos `Trade`. Sinais e posições abertas
são direcionados exclusivamente ao serviço de monitoramento. Falhas do Discord
são retornadas como resultados seguros, sem interromper o terminal e sem incluir
a URL do webhook nos erros. Backtests não enviam notificações automaticamente.

O canal de monitoramento recebe lotes compactos como:

```text
20:31 | BTCUSDT 1m | Candle processado.
20:31 | BTCUSDT 1m | Aguardando sinal.
20:42 | BTCUSDT 1m | Sinal de COMPRA encontrado.
20:43 | BTCUSDT 1m | Posição virtual COMPRADA aberta em 118000.
```

## Paper trading

O runner consulta candles públicos periodicamente e mantém apenas uma conta
virtual. Na primeira consulta ele aquece o histórico sem criar operações
retroativas; depois processa cada candle fechado uma única vez e salva o
checkpoint.

```powershell
python scripts/run_paper_trading.py --symbol BTCUSDT --interval 5m
```

Interrompa com `Ctrl+C`. O ciclo:

1. ignora o candle ainda em formação;
2. gera o sinal no fechamento;
3. simula a entrada na abertura do candle seguinte;
4. monitora stop e alvo;
5. registra toda operação encerrada no histórico paper;
6. registra também as perdas no banco de aprendizado;
7. notifica o canal de resultados somente quando o trade termina;
8. envia a atividade ao terminal e ao canal separado de monitoramento.

Ao executar novamente o mesmo ativo, intervalo e estratégia, a sessão anterior é
restaurada. Para consultar o estado sem iniciar o runner:

```powershell
python scripts/show_paper_status.py --symbol BTCUSDT --interval 1m
```

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
estratégia automaticamente. Todas as vitórias, derrotas e empates já são
registrados em `data/trading_bot.db`, formando o conjunto de comparação
necessário para o aprendizado futuro.

## Escopo desta versão

Ainda não há:

- integração autenticada com corretoras;
- execução de ordens;
- garantia de rentabilidade;
- uso de dinheiro real.

## Próximas etapas

- Importar e validar candles por CSV.
- Coletar histórico extenso da Binance.
- Implementar validação walk-forward.
- Testar filtros de mercado e um otimizador controlado.
- Treinar o primeiro filtro probabilístico somente após acumular dados.

Consulte [ROADMAP.md](ROADMAP.md) para acompanhar as dez prioridades.

## Licença

Distribuído sob a licença MIT. Consulte [LICENSE](LICENSE).
