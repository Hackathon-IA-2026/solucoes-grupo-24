# Método da espacialização (Fase 6): BDGD → áreas de influência → MMGD por área de influência → excedentes

Área piloto: **RJ (LIGHT + Enel RJ)**, decidida pelo Tiago em 2026-09-26. O motivo foi reaproveitar a pipeline do `Backend/RDX/`, do hackathon anterior. O código fica em `Backend/src/spatial/` e os parâmetros em `Backend/config/espacial.yaml`. O `run_heavywork.py` roda tudo na etapa `espacializacao`, entre o processamento e os treinos. Para depurar, dá para rodar só esta etapa com `python -m src.spatial.construir`, de dentro de `Backend/`.

## Fontes (todas baixadas pela ingestão, `config/fontes_ons.yaml` → `arquivos_diretos`)

| Fonte | Arquivo | Para quê |
|---|---|---|
| BDGD LIGHT e Enel RJ, ref. 2025-12-31 (ANEEL, portal ArcGIS) | `data/raw/aneel/bdgd/*.gdb.zip` (~2,1 GB) | subestações, trafos, alimentadores, consumidores AT, unidades geradoras |
| Cadastro de MMGD (ANEEL, diário) | `data/raw/aneel/empreendimento_geracao_distribuida.parquet` | potência oficial e data de cada empreendimento |
| Malhas do IBGE (API v3, qualidade máxima) | `data/raw/ibge/*.geojson` | limite do estado (vazios entre áreas de influência) |
| Carga verificada do ONS, área RJ | `data/processed/carga_area.csv` | carga global e MMGD estimada da área, 30 min |

A BDGD é lida **de dentro do .zip** (GDAL `/vsizip/`, via pyogrio). Descompactada, ela passa de 5 GB por distribuidora, e o disco da máquina é apertado. Para trocar de ano, basta mudar `url` e `destino` na config. O download percebe que a URL mudou e baixa de novo.

## 1. Áreas de influência (`src/spatial/areas_influencia.py`)

É um polígono por subestação, e juntos eles cobrem o estado sem sobreposição. O método é o do RDX:

1. **Área inicial**: fecho convexo dos transformadores MT/BT (`UNTRMT`) da subestação. Quando há menos de 3, vira uma semente de 10 m em volta dela.
2. **Sobreposições**: as sementes são resolvidas primeiro. Depois vêm as áreas de influência mais internas (a subestação cai dentro de áreas alheias) e, por fim, as de maior potência AT/MT. Cada área de influência fica com o que sobrou.
3. **Vazios do estado**: um vazio que toca só uma área de influência é absorvido por ela. Um vazio que toca várias é dividido por Voronoi entre as subestações vizinhas.
4. **Recorte pelo limite do IBGE e simplificação de 1 m.** Se o recorte apagar uma área de influência inteira (ilha ou faixa de praia fora da malha), o erro é do limite e não da rede, então a área de influência fica sem recorte.

A **classificação** (plena, satélite, transformadora pura, transporte) e a **mãe** de cada subestação seguem a lógica do RDX: circuitos dos trafos e busca em largura na malha AT (`SSDAT`).

Mudanças em relação ao RDX, cada uma com o motivo:

| Mudança | Por quê |
|---|---|
| Cálculos em CRS métrico (EPSG:31983) | o RDX fazia as diferenças de polígonos em graus |
| Sementes resolvidas antes de tudo | um fecho de mesma profundidade engolia a semente, e a subestação sumia (10 casos na BDGD 2025) |
| Área de influência vazia não é descartada; o recorte que apagaria a área de influência é ignorado | o RDX descartava em silêncio (Paquetá, Posto Seis) |
| Voronoi com `ordered=True` | correspondência célula → subestação direta, sem a busca geométrica que falhava na borda |
| MMGD = CEG no padrão `GD.` | o RDX contava qualquer CEG e somava 2,2 GW de usinas grandes da UGAT da LIGHT como MMGD |
| Camadas iguais para as duas distribuidoras | desde a BDGD 2022 a LIGHT usa `UNTRMT`/`UNTRAT` (a de 2021 usava `UNTRS`/`UNTRD`) |
| Malha do IBGE pela API v3 | substitui o pacote `geobr`, sem dependência nova |

Ficaram de fora o enriquecimento CNEFE/OSM e o mapa Streamlit (`RDX/main.py`). No `extrator.py` do RDX, os provedores de dados estavam vazios, e o mapa agora é o dashboard.

## 2. MMGD por área de influência: desempate BDGD × ANEEL (`src/spatial/mmgd.py`)

O cruzamento é pelo código do empreendimento (CEG_GD da BDGD = CodEmpreendimento da ANEEL). Ele implementa as camadas 2 e 3 da auditoria do Pilar 2 (`docs/Oraculo_planejamento.md`):

| Categoria | BDGD | ANEEL | Entra na capacidade? |
|---|---|---|---|
| `bdgd_e_aneel` | sim | sim | sim: potência da ANEEL, subestação da BDGD |
| `lag_sistema` | não | sim | sim: rateada entre as áreas de influência da mesma distribuidora no mesmo município (proporção da capacidade já localizada; sem ela, da potência dos trafos) |
| `bdgd_sem_homologacao` | sim | não | **não** (exceção, fica só no relatório) |

- **A potência vem sempre da ANEEL.** Na BDGD 2025 da Enel RJ, o `POT_INST` é ~5× menor que o cadastro para o mesmo CEG (mediana 0,20). Na LIGHT os dois batem (1,00).
- **Data de entrada** = `DthAtualizaCadastralEmpreend`, a mesma convenção de `capacidade_mmgd.csv`. No replay, a capacidade só conta o que já estava cadastrado até o "agora".
- **Fator de correção do satélite (Luiz)**: CSV `area_id,fator_correcao` apontado em `config/projeto.yaml` (`caminho_fator_correcao`). Ele é aplicado na potência de cada unidade. Sem o arquivo, o fator fica nulo e a capacidade corrigida é igual à cadastrada.
- **Duas chaves de área de influência.** `area_id` é *onde a usina está* (`UG.SUB`) e alimenta o mapa e a densidade. `area_fronteira` é *por onde ela chega à rede básica*: a subestação de origem do alimentador (`CTMT.SUB`), que alimenta os excedentes. Na LIGHT as duas diferem em ~15% das unidades (subestações satélite).

Resultado com a BDGD 2025 e o cadastro de 2026-09: são **1.908,7 MW** de MMGD nas duas distribuidoras. Desse total, **293,5 MW** são lag de sistema, ou seja, estão no cadastro e ainda não na BDGD. Os números por distribuidora estão em `docs/reports/desempate_mmgd.md`.

## 3. Excedentes (`src/spatial/excedentes.py`)

O excedente de uma subestação de fronteira em uma semi-hora é **max(0, geração de MMGD − carga)**. Quando ele é positivo, há fluxo reverso para a rede básica, que é justamente o que o ONS não vê.

- **Geração** = capacidade de MMGD da fronteira × fator de geração da área. O fator de geração é a MMGD estimada pelo ONS na área RJ ÷ a capacidade cadastrada na ANEEL no RJ, na data. Hipótese: o fator é o mesmo em toda a área, porque ainda não há irradiância por área de influência.
- **Carga** = carga global da área RJ (ONS) × peso da subestação no mês. O peso sai da energia **bruta** da subestação na BDGD: energia líquida medida nos alimentadores + MMGD que sai por ela + consumidores AT. A carga global do ONS também é bruta.
- **Previsão para 1h, 3h e D+1**: persistência sazonal de 1 dia, em que o alvo t usa o observado em t − 24 h. Para alvos até 24 h à frente, ela só usa dado ≤ agora. O teste `test_previsao_nao_usa_dado_depois_do_agora` troca o futuro por lixo e exige resultado idêntico.
- **Publicação**: por subestação, o pico de excedente nas próximas 24 h. O horizonte publicado é o menor horizonte cuja janela contém o pico. Entram as subestações com excedente > 0 (até 15). Se forem menos de 5, a lista é completada com as de maior penetração (geração ÷ carga), com excedente 0. A posição publicada é a da própria subestação. A prioridade segue limiares em MW (`config/espacial.yaml`).

**Conferência contra medição.** A BDGD traz 12 alimentadores com energia líquida **negativa** em algum mês, ou seja, fluxo reverso medido pela própria distribuidora (`docs/reports/alimentadores_fluxo_reverso.csv`). Na publicação de 2026-09-26, os **3 maiores excedentes previstos** (Centenário, Influência, Brisamar) estão entre as 9 subestações de origem desses alimentadores. Santa Cecília, Três Rios, Volta Redonda, Fontinele, Carmari e Rocha Freire exportam na medição, mas não aparecem com excedente na previsão desse dia. É um limite conhecido do método (fator de geração único na área, perfil de carga plano no mês) e é o próximo ponto a melhorar.

## Saídas

| Arquivo | Conteúdo |
|---|---|
| `Backend/output/areas_influencia_rj.geojson` | 448 áreas de influência + atributos de MMGD (para o Mapa Híbrido; fora do contrato até combinar o schema com o Luiz) |
| `Backend/data/processed/mmgd_area_influencia.csv` | uma linha por área de influência: rede, classificação, capacidade por categoria, fonte, fator de correção, pontos |
| `Backend/data/processed/mmgd_fronteira_diaria.csv` | capacidade de MMGD por subestação de fronteira e data (base dos excedentes) |
| `Backend/data/processed/carga_area_influencia_mensal.csv` | energia bruta e peso de cada subestação de fronteira por mês |
| `docs/reports/desempate_mmgd.md` e `alimentadores_fluxo_reverso.csv` | relatório do desempate e evidência medida |

No contrato (schema inalterado), `excedentes` e `mmgd_densidade` passam a sair daqui com `mock: false`.
