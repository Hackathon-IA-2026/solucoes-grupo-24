# Conciliação da capacidade de MMGD — área piloto

Gerado por `python -m src.spatial.conciliacao` em 2026-09-27 12:46 UTC.
Método, premissas e limitações: [docs/metodo_conciliacao.md](../metodo_conciliacao.md).

- **Data-base da BDGD:** 2025-12-31 (LIGHT e Enel RJ, extrato V11).
- **Data de referência (data_ref):** 2026-07-30 (cadastro da ANEEL gerado em 2026-09-26).
- **Área piloto:** LIGHT: Rio de Janeiro; ENEL_RJ: Niterói.
- **Visão computacional:** 3038 ladrilhos Esri z19 varridos,
  373 detecções agrupadas, 167 com confiança ≥ 0.6.

## Números-chave por município

| Município | Transformadores | Com MMGD na BDGD | BDGD (MW) | ANEEL data-base (MW) | ANEEL data_ref (MW) | Defasagem (MW) | Razão BDGD/ANEEL | Com imagem | Data(s) da imagem | Excesso de detecções | Resíduo (instalações) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Niterói (3303302) | 7.572 | 2.509 | 68,68 | 77,23 | 85,49 | 8,26 | 0,933 | 1.436 | 2026-01-28 | 22,0 | 16,0 |
| Rio de Janeiro (3304557) | 50.306 | 14.748 | 313,78 | 349,88 | 377,35 | 27,47 | 0,933 | 1.368 | 2025-05-25, 2025-12-07 | 83,0 | 83,0 |

Capacidade BDGD = potência do **cadastro da ANEEL** para o mesmo CEG, localizada no transformador pela BDGD
(CEG sem cadastro: POT_INST da BDGD, 596 empreendimentos, 4.408 kW).
Só as unidades de baixa tensão (UGBT) têm transformador MT/BT; a razão de cobertura usa todas (UGBT, UGMT, UGAT).

## Cobertura BDGD × ANEEL

Faixa de confiança: 0.8–1.2. Flags por município:

- **Niterói**: suspensao_aneel_no_intervalo;data_ref_sujeita_a_atraso;residuo_satelite
- **Rio de Janeiro**: suspensao_aneel_no_intervalo;data_ref_sujeita_a_atraso;residuo_satelite;multiplas_datas_imagem;imagem_anterior_data_base

Recadastro depois da data-base (possível dupla contagem: está na BDGD e também na defasagem, porque a única
data do cadastro é a da última atualização cadastral): Niterói 427 kW; Rio de Janeiro 2.000 kW.

## Maiores parcelas de defasagem por transformador

| Transformador | Município | BDGD (kW) | Parcela da defasagem (kW) | Faixa (kW) | Método |
|---|---|---|---|---|---|
| LIGHT:9271358 | Rio de Janeiro | 530.0 | 46.4 | 576.4–576.4 | fallback |
| LIGHT:11162319 | Rio de Janeiro | 480.0 | 42.0 | 522.0–522.0 | fallback |
| LIGHT:623838171 | Rio de Janeiro | 395.8 | 34.6 | 430.5–430.5 | fallback |
| LIGHT:101729686 | Rio de Janeiro | 384.7 | 33.7 | 418.4–418.4 | fallback |
| LIGHT:452920705 | Rio de Janeiro | 370.6 | 32.4 | 403.0–403.0 | fallback |
| LIGHT:10951253 | Rio de Janeiro | 362.1 | 31.7 | 393.9–393.9 | fallback |
| LIGHT:11041863 | Rio de Janeiro | 344.3 | 30.1 | 374.4–374.4 | fallback |
| LIGHT:219441564 | Rio de Janeiro | 329.6 | 28.9 | 358.5–358.5 | fallback |
| ENEL_RJ:NI34397 | Niterói | 236.8 | 28.5 | 265.3–265.3 | fallback |
| LIGHT:106074761 | Rio de Janeiro | 325.0 | 28.4 | 353.5–353.5 | fallback |

## Onde a visão mudou a alocação

| Transformador | Excesso de detecções | Com visão (kW) | 100% fallback (kW) |
|---|---|---|---|
| ENEL_RJ:N760691 | 2.0 | 5.77 | 0.00 |
| ENEL_RJ:U0511 | 1.0 | 2.88 | 0.00 |
| ENEL_RJ:U0142 | 1.0 | 2.88 | 0.00 |
| ENEL_RJ:U1002 | 1.0 | 2.88 | 0.00 |
| ENEL_RJ:U0151 | 1.0 | 2.88 | 0.00 |
| ENEL_RJ:NI33995 | 1.0 | 2.88 | 0.00 |
| ENEL_RJ:NI33212 | 1.0 | 2.88 | 0.00 |
| ENEL_RJ:NI33285 | 1.0 | 2.88 | 0.00 |
| ENEL_RJ:NI33533 | 1.0 | 2.88 | 0.00 |
| ENEL_RJ:U636 | 1.0 | 2.88 | 0.00 |

## Flags por transformador

| Flag | Transformadores |
|---|---|
| grupo_colocalizado | 11.720 |
| imagem_anterior_data_base | 1.368 |
| ponto_fora_do_municipio | 559 |
| kw_sem_cadastro_aneel | 460 |
| imagem_parcial | 450 |

## Limitações

- A ANEEL não publica data de conexão: a série usa a data da **última atualização cadastral**. A migração
  SISGD → MMGD (2025-09-23 a 2025-11-13) e o acúmulo de 90 dias depois ficam
  marcados (`flag_suspensao`, `flag_pos_suspensao` em `capacidade_aneel_municipio.parquet`), não corrigidos.
- Os últimos meses do cadastro chegam incompletos (inserção atrasada): `data_ref` perto da geração do arquivo
  subestima a defasagem.
- O detector (`best.pt`, treinado em Google z20) perde sensibilidade na Esri z19: a contagem de detecções é um
  piso, e o excesso tende a zero. Ver a medição em docs/metodo_conciliacao.md.
- A imagem Esri do Rio é anterior à data-base da BDGD: ali a visão não aloca defasagem, só gera resíduo.
- Área atendida = célula de Voronoi dos transformadores (raio máximo 400 m), não o
  traçado real da rede de BT. Transformadores no mesmo posto dividem a célula.
- Resíduo e excesso NÃO entram na capacidade (instalações aguardando conexão, falsos positivos e irregulares).
