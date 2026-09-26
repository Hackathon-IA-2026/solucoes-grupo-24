# Área piloto — comparativo e recomendação (PROVISÓRIA)

A área piloto é onde aplicamos a tese TSO–DSO de ponta a ponta: BDGD da distribuidora → manchas de rede (área por subestação) → capacidade de MMGD por mancha → correção por imagem de satélite (Luiz) → comparação com a MMGD que o ONS estima. **O Luiz depende desta escolha para baixar as imagens.**

Todos os números abaixo vêm de dados baixados neste projeto (2026-09-25): BDGD e MMGD da ANEEL, API de carga do ONS e rótulos de curtailment (`Backend/data/processed/rotulos_curtailment.parquet`). O RJ entrou no comparativo porque o hackathon anterior (`Backend/RDX/`) já tem o pipeline pronto para LIGHT e ENEL RJ.

## Comparativo

| Critério | CEMIG-D (MG) | CELESC (SC) | Energisa (Sul-Sudeste: interior SP/PR/MG · Minas Rio: Zona da Mata MG) | LIGHT + ENEL RJ (RJ) |
|---|---|---|---|---|
| **BDGD disponível (mais recente)** | 2025-12-31 V11 | 2025-12-31 V11 | 2025-12-31 V11 (ambas) | 2025-12-31 V11 (ambas) |
| **Volume da BDGD (zip)** | **3,97 GB** | 1,30 GB | 0,30 GB + 0,19 GB | 1,14 GB + 1,01 GB |
| **MMGD instalada (ANEEL)** | **5,84 GW** / 427 mil empreendimentos | 2,07 GW / 181 mil | 0,73 GW (ESS) + 0,61 GW (EMR) | 0,85 GW (LIGHT) + 1,06 GW (ENEL RJ) |
| **MMGD / carga ao meio-dia (ONS, 2025, área de carga)** | **37,7%** (área MG) | 22,4% (área SC) | parte das áreas SP (16,9%) e MG | 13,8% (área RJ) |
| **Curtailment observado na UF (jan/2025→set/2026, ENE+CNF)** | **7,6 TWh**, solar: 20 conjuntos; polo Janaúba–Jaíba concentra ~4 TWh; vários conectados em 138 kV "(Distribuição)" | 0,07 TWh (2 eólicas) | SP: 0,8 TWh solar; MG: ver CEMIG | **nenhum** |
| **Qualidade observada** | não avaliada ainda | não avaliada ainda | não avaliada ainda | BDGD 2021/2022 da RDX com MMGD da LIGHT inconsistente (152 usinas somando 1,6 GW); a versão 2025 não foi testada |
| **Reaproveitamento da RDX** | código do `extrator.py` (as camadas da BDGD são padrão PRODIST Módulo 10) | idem | idem | código **e** saídas prontas (manchas, classificação, elo ONS↔distribuidora por número de barra) |
| **Risco de processamento nesta máquina (8 GB RAM)** | **alto**: exige leitura seletiva de camadas/colunas e recorte regional | médio | baixo | médio |

Observação sobre a ENE: ela é sistêmica. A MMGD reduz a carga supervisionada do SIN inteiro ao meio-dia e isso gera corte nas renováveis onde quer que estejam. Por isso a área piloto não precisa conter usinas cortadas para ser útil à tese. Mas, quando contém (caso de MG), dá para mostrar os dois lados na mesma região: MMGD invisível ao ONS e curtailment local por CNF.

## Recomendação provisória

**CEMIG-D — Norte de Minas, polo Janaúba–Jaíba** (subestações de distribuição em torno de Janaúba, Jaíba, Francisco Sá e Várzea da Palma).

1. **Maior MMGD do país na distribuidora e maior fração da carga** (37,7% ao meio-dia na área MG): é onde o gap TSO–DSO mais pesa.
2. **Curtailment real na mesma região**, com conjuntos solares ligados à rede de 138 kV da própria CEMIG: é a interface TSO–DSO literalmente.
3. **O recorte regional resolve o volume**: lemos só as camadas e colunas necessárias da BDGD, direto do zip (`/vsizip/`), e filtramos pela região. A BDGD inteira de 4 GB nunca precisa caber na RAM.
4. A comparação com o ONS é direta: a área de carga "MG" da API tem MMGD estimada semi-horária.

**Alternativa se o tempo apertar: RJ (LIGHT + ENEL RJ)**, que tem custo quase zero porque a RDX já tem as manchas. O preço é ficar sem curtailment local e com a menor fração de MMGD entre as candidatas.

Gravada como provisória em `Backend/config/projeto.yaml` (`area_piloto`, `area_piloto_provisoria: true`).

## Pendência humana

**Tiago: confirmar a área piloto e avisar o Luiz** (as imagens de satélite dependem disso). Se confirmar, mude `area_piloto_provisoria` para `false`.

> **Decisão (Tiago, 2026-09-26): RJ (LIGHT + Enel RJ)**, reaproveitando a pipeline do `Backend/RDX/`. `area_piloto_provisoria: false`. Implementação e método em `docs/metodo_espacial.md`.
