# Catálogo de séries selecionadas [NUNCA CORTAR]

Seleção feita a partir de `docs/inventario_portal_ons.md`. Os nomes são os ids exatos no portal (CKAN) ou o endpoint exato da API. A forma de acesso usada no projeto é **download direto** (`src/ingestion/download.py`, parâmetros em `config/fontes_ons.yaml`); a coluna "MCP" diz se a série também pode ser consultada pelo MCP oficial (ver `docs/mcp_ons.md`). Contagem de linhas por arquivo em `docs/reports/download_log.csv`; sanidade em `docs/reports/download_sanidade.csv`.

Fuso: bases do portal em horário de Brasília (`din_instante`); API de carga em UTC (`din_referenciautc`, fim do intervalo). Tudo é padronizado em UTC-3 fixo, com timestamp no início do intervalo (`src/utils/tempo.py`).

## Desafio 1 — curtailment

| Série (id exato) | Apelido local | Granularidade | Período baixado | Unidade | Acesso | MCP | Justificativa |
|---|---|---|---|---|---|---|---|
| `restricao_coff_eolica_usi` (**base tm eólica**) | `coff_eolica_tm` | 30 min × usina/conjunto | 2021-10 → 2026-09 | MWmed; minutos | download Parquet | sim | Rótulo principal: razão (ENE/CNF/REL), origem (LOC/SIS), GNRa, minutos por razão |
| `restricao_coff_fotovoltaica` (**base tm solar**) | `coff_solar_tm` | 30 min × usina/conjunto | 2024-04 → 2026-09 | MWmed; minutos | download Parquet | sim | Idem, solar. Não existe antes de abr/2024 |
| `restricao_coff_eolica_detail` (**detail eólica**) | `coff_eolica_detail` | 30 min × usina | 2021-10 → 2026-09 | MW; m/s | download, consolidado por `id_ons` | sim | Vento verificado e geração estimada por usina (features de disponibilidade do recurso) |
| `restricao_coff_fotovoltaica_detail` (**detail solar**) | `coff_solar_detail` | 30 min × usina | 2024-04 → 2026-09 | MW; W/m² | download, consolidado por `id_ons` | sim | Irradiância e geração estimada por usina |
| `geracao-termica-despacho-2` (**térmicas por motivo de despacho**) | `termica_despacho` | horária × usina | 2013 → 2026-09 | MWmed | download Parquet | sim | Inflexibilidade térmica empurra excedente → ENE |
| `intercambio-nacional` (**intercâmbio verificado**) | `intercambio_nacional` | horária × par de subsistemas | 2000 → 2026-09 (2000–2022 vêm em CSV e são convertidos para Parquet) | MWmed | download | sim | Saturação da exportação do NE (CNF) |
| `fator-capacidade-2` (**capacidade instalada eólica/solar**) | `fator_capacidade` | horária × usina/conjunto | 2009-07 → 2026-09 | MW (capacidade), p.u. | download Parquet | sim | Capacidade instalada eólica/solar ao longo do tempo, com lat/lon da subestação coletora |
| `usina_conjunto` | `usina_conjunto` | cadastro | retrato atual | — | download | sim | Liga usina ↔ conjunto (tm usa conjunto, detail usa usina) |
| `modalidade-usina` | `modalidade_usina` | cadastro | retrato atual | — | download | sim | Modalidade Tipo I/II das usinas apuradas |
| `capacidade-geracao` | `capacidade_geracao` | cadastro × unidade geradora | retrato atual | MW | download | sim | Potência nominal atual das despachadas |

## Desafio 2 — demanda

| Série (id exato) | Apelido local | Granularidade | Período baixado | Unidade | Acesso | MCP | Justificativa |
|---|---|---|---|---|---|---|---|
| `carga-energia-verificada` — API `GET https://apicarga.ons.org.br/prd/cargaverificada` (**carga verificada com carga global e MMGD estimada**) | `carga_verificada` | 30 min × área de carga (4 subsistemas + 25 áreas + 4 perdas) | 2016-01 → ontem | MWmed | API REST (máx. 3 meses/chamada) | **não** | Fonte única de `val_cargaglobal`, `val_cargammgd` (**MMGD estimada**) e `val_cargaglobalsmmgd` → carga supervisionada |
| `carga-energia-programada` — API `GET .../cargaprogramada` | `carga_programada` | 30 min × subsistema | 2021-03 → ontem | MWmed | API REST | **não** | Previsão do próprio ONS: baseline natural para D+1 (tela 6) |
| `curva-carga` | `curva_carga` | horária × subsistema | 2000 → 2026-09 | MWmed | download Parquet | sim | Histórico longo de carga (pré-2016) para sazonalidade |

## Ambos

| Série (id exato) | Apelido local | Granularidade | Período baixado | Unidade | Acesso | MCP | Justificativa |
|---|---|---|---|---|---|---|---|
| `balanco-energia-subsistema` | `balanco_subsistema` | horária × subsistema | 2000 → 2026-09 | MWmed | download Parquet | sim | Carga e geração por fonte; eólica+solar vs. carga (Figura 1 e features de ENE) |
| Relação de empreendimentos de MMGD (ANEEL, **fora do ONS**) | `aneel_mmgd_empreendimentos` | cadastro × empreendimento (com data de conexão) | retrato atual (série reconstruível pela data de conexão) | kW | download direto | não | **Capacidade instalada de MMGD** por distribuidora/município/UF — o ONS não publica isso |

## Obrigatórias — situação

| Obrigatória | Situação |
|---|---|
| constrained-off eólica e solar, bases tm e detail | ✅ as quatro baixadas |
| carga verificada (com carga global) | ✅ API de carga verificada |
| MMGD estimada | ✅ `val_cargammgd` na mesma API |
| térmicas por motivo de despacho | ✅ |
| limites de exportação NE e N/NE | ❌ **não existem no portal** (ver Excluídas) |
| intercâmbio verificado | ✅ |
| capacidade instalada eólica/solar por subsistema | ✅ `fator-capacidade-2` (por usina, agregável por subsistema) |
| capacidade instalada de MMGD por subsistema | ⚠️ não existe no ONS; substituída pela base da ANEEL (agregável por UF → subsistema via `src/utils/joins.py`) |

## Excluídas (com motivo)

| Série | Motivo |
|---|---|
| Limites de exportação NE e N/NE | Não publicados no portal nem no MCP. `programacao_fluxo_controlado` só tem fluxo programado de elos CC e defasadores; `ind_confiarb_atls` é mensal/anual. Bloqueia a feature "folga até o limite" do CNF (cortável) |
| `coff_eolica_usi_intrasemihora`, `coff_fotovoltaica_intrasemihora` | Redundantes com os minutos por razão já presentes na base tm |
| `carga-energia`, `carga-mensal`, `demanda_maxima_di` | Agregações diárias/mensais da mesma carga que já temos em 30 min |
| `programacao_diaria` | Série só a partir de 10/2024 e muito volumosa (2.117 arquivos); fica como sugestão |
| `geracao-usina-2`, `disponibilidade_usina` | Sobrepostas às bases tm/detail para as usinas apuradas |
| Hidrologia (EAR/ENA por reservatório/bacia), indicadores `ind_*`, TEIF/TEIP, cadastros de reservatórios | Sem relação direta com curtailment de renováveis ou carga supervisionada no horizonte do projeto |
| `cargaglobal-roraima` | Coberta pela área `RR` da API de carga |

## Sugestões (não baixar agora)

| Série | Para quê |
|---|---|
| `balanco_dessem_detalhe` (desde 05/2025) | MMGD e demanda **previstas** pelo DESSEM: comparar nossa previsão com a do ONS |
| `programacao_x_previsao` (desde 10/2024) | Previsão eólica/solar do ONS como feature de D+1 no curtailment |
| `cmo-semi-horario` | Sinal de preço/excedente para ENE |
| `ear-diario-por-subsistema`, `ena-diario-por-subsistema` | Condição hídrica, que modula o excedente energético (ENE) |
| `energia-vertida-turbinavel` | Vertimento turbinável: excedente hídrico simultâneo ao corte de renováveis |
| ERA5 (temperatura 2 m, ssrd) | Desligado (`era5_disponivel: false`); os modelos rodam com `usar_era5: false` |
