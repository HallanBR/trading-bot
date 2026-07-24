# Roadmap

O desenvolvimento é dividido em partes pequenas e verificáveis. Uma etapa só é
considerada concluída depois de testes automatizados e validação em paper
trading.

## Parte 1 — Confiabilidade e observabilidade

- [x] Persistir e restaurar a sessão paper.
- [x] Registrar todas as operações encerradas.
- [x] Melhorar os registros do terminal.
- [x] Separar o Discord de resultados do Discord de monitoramento.

## Parte 2 — Dados e validação temporal

- [x] Coletar histórico extenso e paginado da Binance.
- [x] Criar armazenamento e importação de candles por CSV.
- [x] Implementar backtests walk-forward sem acesso a dados futuros.

## Parte 3 — Pesquisa de estratégia

- [x] Implementar filtros de tendência, VWAP, volume, volatilidade e custos.
- [x] Adicionar candidatos de rompimento e reversão à média.
- [x] Comparar candidatos fora da amostra contra a estratégia-base.
- [ ] Executar campanhas em diferentes ativos, intervalos e regimes.
- [ ] Criar otimizador com conjuntos separados de treino e validação.

## Parte 4 — Aprendizado de máquina

- [ ] Construir features versionadas a partir de vitórias e derrotas.
- [ ] Treinar um primeiro modelo como filtro, sem autonomia de execução.
- [ ] Calibrar probabilidades e comparar modelo atual contra candidato.
- [ ] Promover ou reverter modelos usando resultados fora da amostra.

## Parte 5 — Integrações e visualização

- [ ] Integrar exclusivamente com a Binance Spot Testnet.
- [ ] Manter execução com dinheiro real bloqueada.
- [ ] Criar dashboard de sessões, trades, métricas e modelos.
