# Contrato de dados: Backend → dashboard

## Fonte oficial

**`Frontend/oraculo-dashboard/src/data/types.ts`** (schemas Zod do dashboard do Luiz). Decisão do Tiago em 2026-09-25: o contrato é o que o dashboard já consome. A proposta v1 (JSON único por execução) foi aposentada; histórico em `docs/schema_changelog.md`.

| Onde | O quê | Quem mantém |
|---|---|---|
| `Frontend/oraculo-dashboard/src/data/types.ts` | contrato oficial (Zod + tipos TypeScript) | Luiz |
| `Backend/src/contrato/modelos.py` | espelho em Python (Pydantic), com as mesmas validações | Tiago |
| `docs/schema_contrato.json` | JSON Schema **gerado** dos modelos Python (`python -m src.contrato.esquema`). Não editar à mão | gerado |

Como os três não divergem:
- `Backend/tests/test_contrato.py` valida **cada mock do dashboard** (`src/data/mock/*.json`) contra os modelos Python e exige ida e volta idêntica. Campo renomeado, removido ou acrescentado de um lado só faz o teste falhar.
- O mesmo arquivo de teste falha se `docs/schema_contrato.json` estiver desatualizado em relação aos modelos.
- **Qualquer mudança de campo: pare e combine com o Luiz** (regra do `CLAUDE.md`). Mudança no `types.ts` exige a mesma mudança em `modelos.py` e a regeneração do JSON.

## Recursos e rotas

Todas as rotas são GET, com prefixo `/api` (`Backend/config/api.yaml`), e servem a publicação mais recente.

| Recurso | Rota | Resposta | Origem hoje |
|---|---|---|---|
| carga | `/api/carga/snapshot` | `CargaSnapshot` | **real** (`mock: false`) |
| previsao | `/api/previsao` | `PrevisaoCurva[]` (os 3 horizontes) | pontos reais; fatores climáticos mock → `mock: true` |
| riscos | `/api/riscos` | `RiscoUsina[]` | real, exceto `distribuidora` e `lat`/`lon` (sede da UF) → `mock: true` |
| alertas | `/api/alertas/{riscoUsinaId}` | `AlertaDetalhado` (404 se não houver) | **real** (`mock: false`) |
| excedentes | `/api/excedentes` | `ExcedenteTsoDso[]` | **real** (`mock: false`): subestações de fronteira do RJ, `docs/metodo_espacial.md` |
| validacao | `/api/validacao` | `MetricasValidacao` | **real** (`mock: false`) |
| mmgd_densidade | `/api/mmgd/densidade` | `DensidadeMmgd` (heatmap: `pontos` = `[lat, lon, intensidade 0–1]`) | **real** (`mock: false`): capacidade de MMGD por mancha do RJ |

Fora do contrato: `/api/saude` informa a execução servida (`execucaoId`, `geradoEm`, `instanteReferencia`).

## Regras que valem para todos os recursos (herdadas do `types.ts`)

- `mock` é obrigatório em todo registro de nível superior. A publicação recusa item mock sem `"mock": true`.
- Timestamps ISO-8601 em **UTC com `Z`**; a conversão para horário de Brasília é só na tela.
- Potências em MW; percentuais 0–100 (sufixo `Pct`); frações 0–1.
- Campo desconhecido é recusado (`extra="forbid"`).
- Validações de negócio repetidas no Backend: supervisionada = global − MMGD (tolerância de 1 MW), P10 ≤ P50 ≤ P90, motivos do alerta somando 100%. O Backend recusa gravar o que o dashboard recusaria exibir.

## Como a carga real é calculada (`CargaSnapshot`)

Implementado em `Backend/src/publicacao/montar.py::snapshot_carga`:

| Campo | Cálculo |
|---|---|
| `timestampUtc` | a última semi-hora (até o "agora" de `config/publicacao.yaml`) em que os 4 subsistemas têm carga global **e** MMGD; início do intervalo, convertido para UTC |
| `cargaGlobalMw`, `mmgdEstimadaMw` | soma dos 4 subsistemas (API de carga verificada do ONS) |
| `cargaSupervisionadaMw` | global − MMGD |
| `percentualMmgdNaGeracao` | MMGD ÷ carga global × 100 (participação da MMGD no atendimento, como na Figura 7 do plano) |
| `mmgdSobreCapacidadeInstalada` | MMGD estimada pelo ONS ÷ potência de MMGD cadastrada na ANEEL até a data do instante |

Limitações: a ANEEL não publica data de conexão, então a data usada é a de atualização cadastral (a capacidade no passado fica subestimada). O cadastro cobre o país inteiro, e a estimativa do ONS só o SIN.

## Como a previsão é montada (`PrevisaoCurva`)

Implementado em `Backend/src/publicacao/montar.py::curvas_previsao`, a partir das previsões fora da amostra da etapa 4 (`Backend/src/models/carga.py`). Série: SIN (`serie_publicada` em `Backend/config/modelos_carga.yaml`), modelo LightGBM quantílico.

| Campo | Cálculo |
|---|---|
| `horizonte` | modelo direto por horizonte: 30min = 1 passo, 3h = 6, D+1 = 48 passos de 30 min entre a emissão e o alvo |
| `pontos` | as 48 semi-horas que **terminam em agora + horizonte**. Cada ponto é a previsão emitida um horizonte antes do próprio alvo, então nenhuma usa dado posterior ao "agora". D+1 = as próximas 24 h inteiras; 3h e 30min = a trajetória recente daquele horizonte até 3 h / 30 min à frente |
| `p10`, `p50`, `p90` | um LightGBM por quantil; quantis reordenados se cruzarem (rearranjo) |
| `rampaProjetadaMw` | maior subida do P50 em `janelaRampaHoras` (mesma regra do `trechoDeRampa` do dashboard) |
| `janelaRampaHoras` | 3 (config `curva.janela_rampa_horas`) |
| `fatoresClimaticos` | **mock** (copiados do mock do dashboard, por horizonte): não há fonte meteorológica. Por isso o registro sai com `mock: true` |

## Como a validação é calculada (`MetricasValidacao`)

Implementado em `Backend/src/publicacao/montar.py::metricas_validacao`, com as mesmas funções do relatório `docs/reports/baseline_carga.md` (`Backend/src/models/metricas.py`).

| Campo | Cálculo |
|---|---|
| `erroMedioAbsolutoMw`, `rmseMw`, `mapePct` | P50 do LightGBM, SIN, horizonte D+1 (config `validacao`), todo o período de teste com real conhecido até o "agora" |
| `skillVsClimatologia` | 1 − MAE do modelo ÷ MAE da climatologia (média do treino por mês × dia da semana × horário), nas mesmas semi-horas |
| `baselineNome` | rótulo do baseline do histórico (config `validacao.nome_baseline`: "Climatologia") |
| `historicoErro30d` | MAE e RMSE por dia do modelo **e da climatologia** (`maeBaseline`, `rmseBaseline`), últimos 30 dias completos nos dois até o "agora" |
| `modelo.nome` | config `validacao.nome_modelo` |
| `modelo.versao` | `cfg-` + hash das seções da config que definem o treino (split, features, hiperparâmetros...), gravado em `data/modelos/carga/metadados.json` no treino: muda sozinho quando a config de treino muda |
| `modelo.dataTreino` | data do treino (mesmo `metadados.json`; modelo antigo sem o arquivo: data do `modelos.joblib`) |
| `modelo.periodoTreino` / `periodoTeste` | split da config (`inicio_treino`–`fim_treino`; teste de `inicio_teste` até o último dia com real conhecido até o "agora"). Contrato recusa teste começando antes do fim do treino |
| `statusFontes` | manifesto de download, agrupado em `Backend/config/publicacao.yaml` (`status_fontes`): `online` = última tentativa de todos os arquivos do grupo deu certo; `ultimaSincronizacao` = download mais recente do grupo |

## Como os riscos e alertas são montados (`RiscoUsina`, `AlertaDetalhado`)

Implementado em `Backend/src/publicacao/montar.py::riscos_e_alertas`, a partir das previsões fora da amostra do classificador de curtailment (`Backend/src/models/curtailment.py`, etapa 4).

| Campo | Cálculo |
|---|---|
| emissão usada | a mais recente até o "agora" (as bases de constrained-off atrasam em relação à carga); `atualizadoHaMin` mostra essa defasagem |
| lista | por usina, entre horizontes e razões, a previsão de maior montante esperado; as `top_usinas` (config) de maior montante |
| `id` | chave da usina (fonte + id do ONS), ex. `eolica-bacla2x` |
| `nome`, `uf`, `fonte` | registro mais recente da usina nas bases tm do ONS |
| `lat`, `lon` | **aproximação**: sede (capital) da UF da usina, `posicao_uf` em `Backend/config/publicacao.yaml`; o projeto ainda não ingere coordenada por usina. Por isso o risco sai `mock: true` (`POSICAO_USINA_REAL`) |
| `distribuidora` | **pendente** ("a definir"): o que mostrar para usinas da rede básica é decisão do Luiz. Por isso o risco sai `mock: true` |
| `razao` | a razão (ENE, CNF) de maior montante esperado |
| `probabilidadePct` | P(corte da razão) do classificador LightGBM × 100 |
| `montanteMw` | P(corte) × E[MW cortados \| corte] (regressor LightGBM ajustado só nas semi-horas com corte) |
| `horizonte` | o horizonte (30min, 3h, D+1) dessa previsão |
| `severidade` | pela probabilidade: limiares em `Backend/config/modelos_curtailment.yaml` (`publicacao.severidade`) |
| `acaoRecomendada` | texto-regra por razão, com a faixa horária de curtailment do alvo (config `publicacao.acao`) |
| alerta: `motivos` | probabilidade de cada razão no mesmo alvo, normalizada para somar 100% |
| alerta: `shapValues` | SHAP exato do LightGBM (`pred_contrib`, log-odds) da razão escolhida, somado por grupo de variáveis com rótulo legível (`src/features/curtailment.py::rotulo_explicacao`); as 6 maiores |
| alerta: `metodoExplicacao` | `ExplicadorLightGBM` (`Backend/pipeline/explicabilidade.py`) |
| alerta: `textoAlerta` | mesmo gerador do pipeline de explicabilidade (`gerar_texto_alerta`) |
