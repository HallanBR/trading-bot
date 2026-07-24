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

### Histórico extenso

O coletor pagina automaticamente o limite de mil candles por resposta, remove
repetições e grava valores financeiros sem conversão para `float`:

```powershell
python scripts/download_history.py --symbol BTCUSDT --interval 1m --start 2026-01-01 --end 2026-07-01
```

O CSV validado é salvo em `data/history/` e não entra no Git. Também é possível
informar `--output`, `--page-limit` e `--max-candles`. As datas sem horário são
interpretadas como UTC e o instante final é exclusivo.

## Indicadores técnicos

O núcleo inclui EMA, SMA, RSI, ATR, VWAP móvel, volume relativo e Bandas de
Bollinger:

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

## Estratégias

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

Os candidatos adicionais ficam isolados para que não sejam misturados antes da
validação:

- `filtered`: EMA + RSI + ATR com tendência, VWAP, volume, volatilidade e
  cobertura mínima de taxas e slippage;
- `breakout`: rompimento de faixa confirmado por tendência e volume relativo;
- `mean-reversion`: reversão à média com Bollinger e RSI somente em regime
  compatível;
- `base`: estratégia inicial, mantida como referência.

Mais filtros não garantem uma taxa de acerto maior. Eles reduzem operações
fracas, mas cada candidato precisa superar a referência em dados que não foram
usados para sua configuração.

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

No runner paper, as futuras posições possuem ainda um teto absoluto padrão de
`10 USDT`. Com capital virtual de `10.000 USDT`, isso limita a exposição a
`0,1%` da conta e substitui o teto anterior que poderia chegar a `2.500 USDT`.
O valor pode ser alterado explicitamente por `--max-position-usdt`, sem mudar o
saldo virtual nem apagar o histórico.

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

### Walk-forward e comparação

O walk-forward mantém o treino sempre antes do teste. O período de aquecimento
fornece indicadores ao primeiro candle de teste, mas nenhuma operação pode ser
aberta durante o treino.

Depois de baixar um CSV, compare os candidatos:

```powershell
python scripts/compare_strategies.py --csv data/history/BTCUSDT_1m_20260101_20260701.csv --train-size 20000 --test-size 5000
```

A tabela considera somente resultados fora da amostra e inclui custos
simulados. O ranking é uma ferramenta para descartar candidatos fracos; ele não
é garantia de resultado futuro. Para uma verificação rápida do pipeline, use
`--max-candles`; campanhas finais devem usar o CSV inteiro.

### Otimizador controlado

A prioridade 7 usa uma grade deliberadamente pequena. Dentro de cada fold, os
parâmetros são avaliados somente no trecho de validação pertencente ao treino.
Depois, o candidato elegível é testado no período seguinte, que permaneceu
intocado. Se todos tiverem lucro não positivo, amostra insuficiente, profit
factor baixo ou drawdown excessivo, o sistema escolhe `NO_ELIGIBLE_CANDIDATE`
e não abre operações.

```powershell
python scripts/run_controlled_optimizer.py
```

O comando é específico para os candles de `5m` desta fase e grava o relatório
detalhado em `data/research/optimizer_5m.json`. Ele não altera o paper trading
e não promove parâmetros automaticamente.

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

# Canal opcional, reservado para pesquisas e relatórios futuros
DISCORD_RESEARCH_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

Os endereços configurados devem pertencer a webhooks diferentes. O terceiro
canal já é reconhecido e validado, mas ainda não recebe mensagens
automaticamente. Se o segundo não estiver configurado, o monitoramento continua
normalmente no terminal.

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
python scripts/run_paper_trading.py --symbol BTCUSDT --interval 5m --max-position-usdt 10
```

Após comparar um candidato no walk-forward, ele pode ser selecionado
explicitamente:

```powershell
python scripts/run_paper_trading.py --symbol BTCUSDT --interval 1m --strategy filtered
```

As opções são `base`, `filtered`, `breakout` e `mean-reversion`. A opção padrão
continua sendo `base`; o sistema não troca de estratégia sozinho com base em
uma única vitória ou derrota. Cada estratégia possui sua própria sessão
persistida.

Para consultar saldo, lucro ou perda acumulada e contagem de operações:

```powershell
python scripts/show_paper_status.py --symbol BTCUSDT --interval 5m
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

- Executar campanhas comparativas em outros ativos e intervalos.
- Treinar o primeiro filtro probabilístico somente após acumular dados.
- Integrar exclusivamente com Binance Spot Testnet.
- Criar o dashboard de sessões, operações e pesquisas.

Consulte [ROADMAP.md](ROADMAP.md) para acompanhar as dez prioridades e
[RESEARCH.md](RESEARCH.md) para ver campanhas e decisões baseadas em evidências.

## Licença

Distribuído sob a licença MIT. Consulte [LICENSE](LICENSE).
