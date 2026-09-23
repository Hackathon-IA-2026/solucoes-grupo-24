# O.R.A.C.U.L.O. — Hackathon IA COPPE/UFRJ 2026

## Contexto

Solução para dois desafios do ONS:
- **Desafio 1 — curtailment:** prever risco e montante de corte de geração eólica e solar (constrained-off), com foco nas razões ENE e CNF conforme o dicionário de dados do ONS.
- **Desafio 2 — demanda:** prever a carga supervisionada (carga global menos MMGD estimada) com quantis.

Tese central: o gap TSO–DSO. A MMGD (micro e minigeração distribuída) é pouco visível ao ONS. Usamos a BDGD da distribuidora + imagens de satélite para estimar capacidade instalada por "mancha" de rede e corrigir as estimativas.

Divisão do time:
- **Tiago (eu):** dados ONS, carga supervisionada, baselines, TFT, classificadores de curtailment, BDGD e manchas, excedentes, JSON do contrato.
- **Luiz:** imagens de satélite, fator de correção de capacidade instalada por mancha, dashboard.

## Estrutura do repositório

```
data/raw/            # bruto, fora do git
data/processed/      # derivados
notebooks/
src/ingestion/
src/spatial/
src/models/
src/utils/
docs/
reports/
output/
```

Stack: Python, pandas, pyarrow, duckdb, geopandas, matplotlib, seaborn, lightgbm, pytorch-forecasting (ou neuralforecast).

## Regras do projeto

- Antes de começar a fazer qualquer alteração deve-se checar se existe atualizações da branch atual, se não tiver alterações conflitantes atualize com pull para ter a versão mais atual do time.
- **Nunca inventar dados.** Se uma série, endpoint ou arquivo não existir ou não estiver acessível, pare e reporte. Dado sintético ou placeholder só com flag explícita (`mock=True` ou coluna `is_mock`) e registrado em `docs/real_vs_mock.md`.
- **Split sempre cronológico.** Nunca aleatório. Toda etapa de modelagem precisa de um teste que prove ausência de vazamento temporal.
- **Nunca cruzar** recortes por subsistema e por área operativa sem `data/processed/mapeamento_subsistema_area.csv`.
- Bases tm de constrained-off: chave composta = fonte + id.
- Carga supervisionada = carga global − MMGD estimada, resolução 30 min, por subsistema.
- Feriados tratados como domingo.
- Horizontes de previsão: 30 min, 3h e D+1. Quantis: P10, P50, P90.
- Patamares: ponta noturna 19–22h; mínima diurna 09–16h.
- Faixas horárias de curtailment: 00–07 | 07–09 e 16–18 | 09–16 | 18–24.
- Dados grandes em Parquet particionado. `data/raw` no `.gitignore`.
- Parâmetros (pesos da loss, datas de corte, caminhos) em `config/*.yaml`, nunca hardcoded.
- Antes de downloads longos ou treinos acima de ~10 min: avise e estime o tempo.
- Commits pequenos e descritivos. Ao fim de cada tarefa, registre o andamento em `docs/STATUS.md`.
- Após fazer commit faça imediatamente push para enviar logo as alterações para o time.
- Respeite os principios DRY! evite ao máximo ter mais de uma cópia do mesmo código!

## README (modelo da competição)

- O `README.md` da raiz segue **exatamente** o modelo em `docs/modelo_readme_competicao.md`: mesmas seções, mesma ordem, mesmos títulos. Não crie seções extras nele.
- Documentação detalhada (schema, status, real vs. mock, métodos) vai para `docs/`. No README, no máximo um link para ela dentro das seções existentes.
- O README é da equipe: a parte do dashboard e do link da demo é do Luiz. Não invente o que não está no repositório — deixe `TODO (Luiz)` e me avise.
- Sempre que mudar dependência, comando de execução ou pré-requisito, atualize as seções "Tecnologias utilizadas", "Como rodar o projeto" e "Pré-requisitos".

## Contrato com o Luiz

Schema em `docs/schema_contrato.json`, descrito em `docs/schema_contrato.md`. **Qualquer mudança no schema: pare e pergunte** — o dashboard do Luiz depende dele.

## Prioridade

- Nunca cortar: catálogo de séries, baselines, TFT com perda assimétrica, classificador ENE, JSON do contrato.
- Cortável: classificador CNF, rascunho das tools MCP.
