# Registro de pesquisa

Este arquivo registra campanhas reproduzíveis. Resultados históricos são
hipotéticos, não garantem desempenho futuro e não autorizam dinheiro real.

## Campanha 2026-07-23 — BTCUSDT

Custos simulados em todas as operações:

- taxa por execução: `0,10%`;
- slippage por execução: `0,05%`;
- capital inicial por fold: `10.000 USDT`;
- gestão de risco padrão do projeto;
- métricas calculadas somente nos períodos de teste.

### Intervalo de 1 minuto

Foram coletados `131.040` candles públicos, de 2026-04-01 a 2026-06-30.
O diagnóstico inicial usou os primeiros `30.000` candles, quatro folds,
`10.000` candles de treino, `5.000` de teste e `100` de aquecimento.

| Estratégia | Trades | Acerto | Lucro líquido | Folds positivos |
|---|---:|---:|---:|---:|
| EMA_RSI_ATR | 52 | 3,85% | -384,43 USDT | 0/4 |
| EMA_RSI_ATR_FILTERED | 4 | 25,00% | -31,82 USDT | 1/4 |
| BREAKOUT_VOLUME_ATR | 39 | 30,77% | -260,51 USDT | 0/4 |
| MEAN_REVERSION_BOLLINGER | 0 | 0,00% | 0,00 USDT | 0/4 |

Conclusão: nenhum candidato demonstrou vantagem. A reversão não pode ser
classificada porque não realizou operações. Os custos projetados têm impacto
especialmente alto em `1m`.

### Intervalo de 5 minutos

Foram coletados e avaliados `52.128` candles públicos, de 2026-01-01 a
2026-06-30. A campanha usou seis folds, `20.000` candles de treino, `5.000` de
teste e `100` de aquecimento.

| Estratégia | Trades | Acerto | Lucro líquido | Folds positivos |
|---|---:|---:|---:|---:|
| EMA_RSI_ATR | 421 | 21,38% | -3.022,60 USDT | 0/6 |
| EMA_RSI_ATR_FILTERED | 105 | 23,81% | -827,14 USDT | 0/6 |
| BREAKOUT_VOLUME_ATR | 378 | 26,19% | -2.774,88 USDT | 0/6 |
| MEAN_REVERSION_BOLLINGER | 1 | 0,00% | -13,01 USDT | 0/6 |

Conclusão: o filtro de tendência, VWAP, volume, volatilidade e custos reduziu
operações e perdas em relação à base, mas permaneceu negativo em todos os
folds. Nenhuma estratégia está aprovada para promoção.

## Decisão

- Manter dinheiro real bloqueado.
- Manter `base` como padrão apenas para preservar compatibilidade das sessões.
- Não escolher parâmetros olhando os períodos de teste acima.
- Na prioridade 7, otimizar parâmetros somente dentro do treino de cada fold.
- Exigir lucro líquido positivo, amostra suficiente, drawdown aceitável e
  estabilidade entre folds antes de promover um candidato para paper.

## Campanha 2026-07-24 — Otimizador controlado em 5 minutos

Foram avaliados doze conjuntos de EMA e saídas por ATR. Cada um dos seis folds
externos usou:

- `20.000` candles de treino;
- os últimos `3.000` candles do treino como validação interna;
- `100` candles de aquecimento;
- `5.000` candles posteriores e intocados como teste externo;
- as mesmas taxas e slippage conservadores das campanhas anteriores.

Todos os doze candidatos tiveram lucro líquido negativo na validação interna de
todos os folds. Até o melhor resultado de cada fold permaneceu entre
`-173,94 USDT` e `-244,92 USDT`.

O otimizador selecionou `NO_ELIGIBLE_CANDIDATE` em seis de seis folds. Assim,
nenhuma operação foi aberta no teste externo e o resultado foi `0,00 USDT`.
Essa preservação não é evidência de rentabilidade: ela apenas confirma que o
sistema deixou de escolher obrigatoriamente a alternativa menos ruim.

Decisão:

- não promover parâmetros;
- concentrar as próximas pesquisas em filtros e features de regime para `5m`;
- usar teto de `10 USDT` por posição nos experimentos paper futuros;
- manter a execução real bloqueada.
