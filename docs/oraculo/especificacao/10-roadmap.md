# 10 · Roadmap

## 10.1 Fatias do MVP — cada uma demonstrável isoladamente

| Fatia | Conteúdo | Estado no protótipo |
|---|---|---|
| **F1** | Ingestão real via CKAN + cache + proveniência; leitura de balanço de energia e constrained-off | **implementada** |
| **F2** | Decomposição de carga e estimador de MMGD com geometria solar | **implementada** |
| **F3** | Baselines e métricas por patamar, backtest cronológico | **implementada** |
| **F4** | Regressão quantílica com perda assimétrica; comparação liga/desliga da assimetria | **implementada** |
| **F5** | Classificador de risco por razão energética, severidade e decomposição de motivo | **implementada** |
| **F6** | Triangulação de evidências e fator de correção de capacidade | **implementada** (fontes reais de BDGD/satélite pendentes) |
| **F7** | Interface web com sete painéis e explorador do catálogo | **implementada** |

## 10.2 Próximos passos — fase presencial (25–27)

| Prioridade | Entrega | Por que agora |
|---|---|---|
| 1 | **BDGD de uma distribuidora piloto** | move a granularidade de estado para área de concessão e transformação de fronteira — é o que o payload da interface ONS–DSO exige |
| 2 | **Cadastro diário de GD da ANEEL** | ativa a camada 3 da triangulação com dado real e permite datar a defasagem |
| 3 | **Previsão numérica real (ECMWF/GFS/WRF) e INMET** | substitui o proxy de nebulosidade e permite **medir** o viés de *perfect-prog* |
| 4 | **Gradient boosting como terceiro baseline** | eleva o piso de comparação; hoje o piso são persistência e sazonal-ingênuo |
| 5 | **Tool no MCP oficial do ONS** | devolve a solução ao ecossistema em vez de criar mais um silo; a equipe do ONS convidou contribuições |
| 6 | **Séries `restricao_coff_*_detail`** | vento e irradiância verificados por usina permitem calibrar a relação recurso → geração |

## 10.3 Evolução de médio prazo

1. **Temporal Fusion Transformer** substituindo a regressão quantílica linear,
   mantendo a mesma função de perda assimétrica e o mesmo protocolo de backtest.
   A perda é o ativo; o estimador é substituível.
2. **Espacialização por mancha sub-municipal**, com polígonos em torno de
   transformadores e alimentadores, onde as grades de 25 km e 10 km não alcançam.
3. **Visão computacional em produção** sobre imagens de satélite, com
   *fine-tuning* local e degradação artificial para simular a qualidade
   disponível no Brasil.
4. **Valoração do corte** cruzando montante restringido com CMO semi-horário,
   para priorizar por impacto econômico e não apenas por potência.
5. **Painel de excedentes por transformação de fronteira** com acionamento
   coordenado, fechando o ciclo do Plano de Gestão de Excedentes.

## 10.4 Critério de promoção de modelo

Nenhum modelo substitui outro sem:

1. skill positivo contra **todos** os baselines, por horizonte;
2. nenhuma piora na ponta noturna nem na mínima diurna;
3. calibração probabilística dentro de ±5 pontos percentuais do nominal;
4. backtest cronológico reproduzível a partir do manifesto de proveniência.
