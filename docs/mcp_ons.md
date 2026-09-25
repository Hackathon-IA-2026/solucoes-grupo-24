# MCP do ONS

## É oficial?

**Sim.** Repositório [`ONSBR/TIAGO-Dados-Abertos`](https://github.com/ONSBR/TIAGO-Dados-Abertos), dentro da organização oficial `ONSBR` no GitHub. A página do próprio portal, [dados.ons.org.br/mcp](https://dados.ons.org.br/mcp), aponta para o servidor público `https://mcp.dados.tiago.ons.org.br/`. Pacote no PyPI: `mcp-tiago-dados-abertos` (Python ≥ 3.12). Licença do código: Apache 2.0. Dados: CC-BY (termos do portal). Verificado em 2026-09-25.

## Como funciona

Não guarda cópia dos dados: o servidor lê com DuckDB, de forma anônima, os Parquet do bucket público do ONS (`s3://ons-aws-prod-opendata/dataset/...`, região `us-west-2`) no momento da consulta. Cada conjunto tem um **contrato ODCS** (YAML em `contracts/ons/`) com schema, unidade, aditividade, casts obrigatórios (`TRY_CAST`, porque várias colunas vêm como VARCHAR), granularidade e cobertura temporal.

## Tools

| Tool | O que faz |
|---|---|
| `listar_datasets` | Catálogo inteiro, uma linha por conjunto (granularidade, perspectiva, uso). Também exposto como resource `catalogo://datasets`. |
| `buscar_dataset` | Filtra o catálogo por termo (palavra-chave + BM25). |
| `descrever_dataset` | Schema, unidades, avisos de tipo, padrões SQL e exemplos de um conjunto. |
| `executar_sql` | Executa SQL DuckDB **somente leitura**, só sobre origens do ONS, paginado. Devolve a tabela + blocos `result-schema` (unidade/aditividade provadas) e `tiago-dados-abertos-sources` (conjunto e URL). |

## Formato de query

SQL DuckDB contra os Parquet do bucket, sempre depois de `descrever_dataset`:

```sql
SELECT id_subsistema, ROUND(AVG(TRY_CAST(val_cargaenergiamwmed AS DOUBLE)), 1) AS carga_mwmed
FROM read_parquet('s3://ons-aws-prod-opendata/dataset/carga_energia_di/*.parquet')
WHERE id_subsistema = 'SE' AND din_instante >= '2020-08-01' AND din_instante < '2020-09-01'
GROUP BY id_subsistema
```

## Limites (padrões do servidor)

| Parâmetro | Padrão |
|---|---|
| Timeout por consulta | 30 s (`MCP_QUERY_TIMEOUT_S`) |
| Linhas por página | até 1000 (`MCP_MAX_PAGE_LIMIT`) |
| Memória do DuckDB | 2 GB |
| Tamanho do SQL | 65 536 caracteres |
| Taxa | 600 consultas/min por processo, rajada de 20/s, sem limite por cliente |
| Fuso para "hoje/ontem" | `America/Sao_Paulo` |

## Cobertura do inventário

Cobre **80 dos 85** conjuntos de `docs/inventario_portal_ons.md` (coluna "MCP"). Ficam de fora:

- `carga-energia-verificada` e `carga-energia-programada`: só existem na API REST `https://apicarga.ons.org.br/prd` (não estão no bucket). **São as séries centrais do Desafio 2.**
- `precipitacao-estacao`, `bacia_contorno`, `ambiente-colaborativo`: irrelevantes para o projeto.

Todas as séries do Desafio 1 que selecionamos (tm, detail, térmicas, intercâmbio, fator de capacidade, cadastros) estão cobertas.

## Decisão de uso no projeto

- **Carga em volume: download direto** (`src/ingestion/download.py`). Com 1000 linhas por página e 30 s de timeout, o MCP não serve para puxar as bases detail (dezenas de milhões de linhas).
- **MCP: exploração e checagem.** Serve para conferir schema, unidade e aditividade antes de escrever uma transformação, e para responder perguntas pontuais. Os contratos ODCS são a melhor documentação de colunas disponível (melhores que os PDFs de dicionário).
- **Carga verificada**: API REST direto, porque o MCP não cobre.

## Inconsistência encontrada no MCP

No contrato `restricao_coff_eolica_usi.odcs.yaml`, o campo `servers[0].location` aponta para `dataset/restricao_coff_fotovoltaica_tm/*.parquet` (a base **solar**). O `sourceExpression` do mesmo contrato está correto (`restricao_coff_eolica_tm`). Não afeta o projeto (baixamos direto do portal), mas é bom saber: **não confie cegamente no campo `location`** desse contrato. Vale reportar no repositório do ONS.
