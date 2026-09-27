# Conciliação da capacidade de MMGD por transformador

ANEEL × BDGD × visão computacional, na área piloto (Rio de Janeiro/LIGHT e Niterói/Enel RJ).
Relatório com os números da última execução: [reports/relatorio_conciliacao.md](reports/relatorio_conciliacao.md).

## O que cada fonte entra dizendo

| Fonte | Diz | Não diz |
|---|---|---|
| Cadastro de MMGD da ANEEL | QUANTO (kW) e QUANDO | onde na rede (só o município) |
| BDGD 2025 (LIGHT, Enel RJ) | ONDE NA REDE: o transformador MT/BT de cada unidade | nada depois da data-base (31/12/2025) |
| Visão computacional (Esri + YOLO) | ONDE FISICAMENTE há painel, e desde quando (data da imagem) | potência: a área do painel **não** vira kW nesta etapa |

Princípio: conciliar agregados por município e por transformador, **nunca casar telhado com registro**.
O único casamento registro a registro é BDGD ↔ ANEEL pelo código do empreendimento (CEG), que já existia na
plataforma.

## O que foi conferido nos dados reais (27/09/2026)

- **Unidade geradora da BDGD não tem geometria própria**: `UGBT_tab`, `UGMT_tab` e `UGAT_tab` são tabelas. A
  UGBT aponta para o transformador (`UNI_TR_MT` → `UNTRMT.COD_ID`, casamento de 100% nas duas distribuidoras) e
  para o ponto de conexão (`PN_CON` → `PONNOT`, poste com coordenada). A UGMT liga em média tensão: não tem
  transformador MT/BT e entra só no total do município.
- **Data-base**: 31/12/2025 nas duas distribuidoras (`Light_382_2025-12-31_V11_20260824`,
  `Enel_RJ_383_2025-12-31_V11_20260827`). A BDGD tem `DAT_CON` por unidade (máximo 31/12/2025).
- **Município do transformador**: `UNTRMT.MUN`, código IBGE de 7 dígitos, nunca nulo. É **cadastral**, não
  geográfico: 550 transformadores com `MUN` = Rio ficam a km dali (Seropédica, Nilópolis, São João de Meriti).
  O município é o da BDGD, como pedido; esses transformadores ficam sem área atendida (flag
  `ponto_fora_do_municipio`), mantêm a capacidade e recebem a parte fallback da defasagem.
- **Cadastro da ANEEL não tem data de conexão**. O dicionário (v2.3, 17/11/2025) descreve "a data da conexão" na
  visão geral, mas o único campo de data é `DthAtualizaCadastralEmpreend`, "data da última atualização
  cadastral". É o que a plataforma já usava. O arquivo também não traz as coordenadas do empreendimento que o
  dicionário lista (só as da subestação). Frequência declarada: mensal.
- **Suspensão SISGD → MMGD** (23/09 a 13/11/2025): no RJ, outubro/2025 tem ~2.000 cadastros de UFV contra
  ~2.700/mês no entorno: é uma queda, não um buraco zerado. A série marca a janela e os 90 dias seguintes.
- **Inserção atrasada**: o arquivo de 26/09/2026 tem 32 cadastros de agosto/2026 no RJ. Nos dois municípios do
  piloto, o mais recente é de 30/07/2026, que vira o `data_ref` padrão (com flag `data_ref_sujeita_a_atraso`).

## Método

1. **Série ANEEL** (`capacidade_aneel_municipio.parquet`): UFV da distribuidora do piloto, potência acumulada
   por município × data, cortada em `data_ref`.
2. **Retrato BDGD por transformador**: soma da potência e nº de unidades de BT por transformador. A potência é
   a do **cadastro da ANEEL** para o mesmo CEG (na Enel o `POT_INST` da BDGD vem ~5× menor para o mesmo
   empreendimento). CEG sem cadastro: fica o `POT_INST`, com flag `kw_sem_cadastro_aneel`.
3. **Cobertura** = capacidade BDGD do município (todas as camadas UG) ÷ capacidade ANEEL na data-base. Fora de
   0,8–1,2: `baixa_confiabilidade_cobertura`.
4. **Defasagem** = capacidade ANEEL em `data_ref` − capacidade ANEEL na data-base da BDGD.
5. **Sinal da visão**: área atendida = célula de Voronoi dos transformadores do município, recortada pelo
   município (IBGE) e por um círculo de 400 m. Transformadores no mesmo ponto (12% no Rio) dividem a célula.
   Um transformador "tem imagem" com ≥ 95% da área varrida; a data é a da imagem que cobre a maior parte.
   Detecção com confiança ≥ 0,6. `excesso_det = max(0, detecções − unidades BDGD)`, calculado no grupo.
6. **Distribuição da defasagem.** Todo transformador começa com a parte fallback, proporcional à sua fatia da
   capacidade BDGD do município. Nos transformadores com imagem de data *d*, a parte de cada um correspondente
   às conexões ANEEL entre a data-base e *d* é juntada e redistribuída pelo excesso de detecções.
   - **Como a regra foi lida:** "parte até a data da imagem → só entre os transformadores com imagem" foi
     aplicada à fatia da área varrida. Aplicar ao município inteiro mandaria tudo o que o Rio conectou até a
     imagem para as 4 subestações varridas.
   - Sem excesso, ou com imagem anterior à data-base: só fallback.
   - A conservação é exata por construção, e nada fica negativo.
7. **Incerteza e resíduo.** A faixa [mín, máx] de cada transformador vai da alocação com visão à alocação 100%
   fallback. O resíduo é o excesso de detecções acima de 2× as conexões ANEEL esperadas na área varrida entre a
   data-base e a imagem. Ele fica registrado e **não soma à capacidade**.

As checagens obrigatórias (conservação, nada negativo, nenhum transformador sem município, nada depois de
`data_ref`) rodam em toda execução e interrompem a publicação se falharem. Testes em
`Backend/tests/test_conciliacao.py`.

## Visão computacional: base Radix, fonte Esri

`Backend/pipeline/paineis_por_transformador.py` segue a lógica do
[Hackaton-Radix](https://github.com/Linkfy-Project/Hackaton-Radix) (`Solar/solar_panels_rj_2stage.py`):
- ladrilhos XYZ que tocam as áreas;
- YOLOv8-seg `best.pt` com imgsz 640;
- checkpoint SQLite que retoma de onde parou.

A diferença principal é a imagem. A varredura anterior do time usava ladrilhos do **Google** (conferido pelo
hash do arquivo), que não publica a data de captura. Sem data, não dá para fazer a etapa 6. Por isso a
imagem agora é a **Esri World Imagery**, com a data consultada no serviço de metadados da Esri para o centro
de cada ladrilho.

Datas nas 5 subestações varridas (Leme, Leblon, Mackenzie, Camerino e Icaraí):

| Data | Ladrilhos | Onde |
|---|---|---|
| 25/05/2025 | 1.949 | Rio |
| 07/12/2025 | 43 | Rio |
| 28/01/2026 | 972 | Icaraí/Niterói |

Só Icaraí é posterior à data-base da BDGD.

### Sensibilidade medida (27/09/2026)

**Esri z19 contra Google z20.** Foram sorteados 60 painéis que a varredura anterior (Google z20) achou com
confiança > 0,85. Nos mesmos locais, o `best.pt` rodou nos ladrilhos Esri z19 (o ladrilho do ponto e os 8
vizinhos). A tolerância cobre a precisão posicional declarada pela Esri, de 8,47 m.

| Raio | Qualquer confiança | Confiança ≥ 0,6 |
|---|---|---|
| 5 m | 5/60 | 3/60 |
| 10 m | 11/60 | 8/60 |
| 20 m | 18/60 | 14/60 |

**Tentativas de contornar**, sem ganho:
- A Esri não tem z20 no RJ: o ladrilho é um placeholder de 2 KB.
- Ampliar quadrantes do z19 para simular a escala do z20 deu 4/40 no ponto exato, contra 3/40 do ladrilho
  inteiro.

**Leitura:** o modelo, treinado em Google z20 (~0,15 m/px), acha na Esri (0,34 m nativos) só **~1 em cada 6
painéis**. A contagem de detecções é um piso, e o excesso tende a ser subestimado. O caminho para melhorar é
um *fine-tuning* com imagens Esri da área piloto, que ainda não foi feito.

## Real, premissa e pendente

**Dado real:**
- BDGD 2025 (LIGHT, Enel RJ), cadastro da ANEEL de 26/09/2026 e malha municipal do IBGE;
- ladrilhos e datas da Esri;
- detecções do `best.pt`.

**Premissas** (todas em `Backend/config/conciliacao.yaml`):
- data do cadastro = data da última atualização cadastral;
- janela de acúmulo pós-suspensão de 90 dias;
- raio de 400 m da área atendida;
- transformador com imagem = ≥ 95% varrido;
- confiança mínima de 0,6;
- partes a < 2 m = uma instalação;
- resíduo a partir de 2× o esperado;
- intensidade do mapa pelo percentil 99.

**Pendente:**
- *fine-tuning* do detector em Esri;
- imagem do Rio posterior à data-base;
- área atendida pelo traçado real da BT (UCBT → `PONNOT`) em vez de Voronoi;
- conversão de área de painel em kW (fora desta etapa por decisão).

## Como rodar (de `Backend/`)

```bash
python -m src.spatial.areas_trafo              # áreas atendidas por transformador (~15 s)
python -m pipeline.paineis_por_transformador   # varredura Esri + YOLO (~20 min na CPU; retoma se parar)
python -m src.spatial.conciliacao              # etapas 1–7, parquets, camada do mapa e relatório (~15 s)
```

A camada do mapa é servida em `GET /api/conciliacao/mmgd-trafo`, no mesmo formato do heatmap
`mmgd_densidade`, e aparece no Mapa Híbrido no botão **MMGD por transformador**.
