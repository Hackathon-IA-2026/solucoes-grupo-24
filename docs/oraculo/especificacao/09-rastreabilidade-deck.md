# 09 · Rastreabilidade: deck → especificação → código → teste

Fonte: `ORACULO_pitch_12_slides_revisado.pptx` (versão final consolidada).

| Slide | Afirmação do deck | Requisito | Módulo do protótipo | Teste |
|---|---|---|---|---|
| 1 | Camada de inteligência preditiva para a interface ONS–DSO | RF-20, RF-31 | `oraculo/api/app.py` | `test_api.py` |
| 2 | A GD alterou o perfil da carga supervisionada; impacto sistêmico sem observabilidade equivalente | RF-10, RF-11 | `models/decomposition.py`, `models/mmgd.py` | `test_decomposition.py`, `test_mmgd.py` |
| 3 | A Rede Básica é supervisionada; na distribuição a observabilidade não é a mesma | RF-04, RNF-04 | `ons/cache.py`, `api/envelope.py` | `test_envelope.py` |
| 4 | Excedente vira restrição: alta renovável + baixa demanda + MMGD → menor carga líquida; até 4,9 GW em domingos de 2029 | RF-30, RF-31, RF-32 | `models/risk.py` | `test_risk.py` |
| 5 | Dois eixos prioritários, uma inteligência comum | RF-12, RF-20 | `pipeline/`, `features/builder.py` | `test_features.py` |
| 6 | Da série histórica ao Composite Load Model; entrega qualificada e limite declarado | RF-12 | `models/decomposition.py` (perfis), `api/service.py::profiles` | `test_profiles.py` |
| 7 | Uma interface precisa de um payload: grandeza, granularidade, antecedência, formato | RF-20, RF-31, RF-04 | `api/app.py` (`/forecast`, `/risk`), `api/envelope.py` | `test_api.py::test_payload_contract` |
| 8 | Cinco fontes, três evidências, dois produtos; limites assumidos desde o início | RF-01, RF-40, RF-41 | `ons/catalog.py`, `triangulation/evidence.py` | `test_catalog.py`, `test_triangulation.py` |
| 9 | Decompor, projetar, quantificar incerteza (P10/P50/P90, múltiplos horizontes) | RF-10, RF-20 | `models/quantile.py` | `test_quantile.py` |
| 10 | Localizar, priorizar, explicar e recomendar; mapa híbrido → lista → alerta rastreável | RF-31, RF-33, RF-32 | `models/risk.py`, `web/js/views/risco.js` | `test_risk.py::test_severity_order` |
| 11 | Backtest temporal, baselines e métricas, limites e rastreabilidade | RF-22, RF-50, RF-51, RF-52 | `validation/backtest.py`, `validation/metrics.py` | `test_backtest.py`, `test_metrics.py` |
| 12 | Interpretar sinais, antecipar condições, apoiar decisões | RNF-08 | `api/envelope.py` (`mode`), selo na interface | `test_api.py::test_mode_declared` |

## Desafio Radix — Mapa Inteligente (slides do PPT da Radix)

| Slide | Exigência | Módulo | Teste |
|---|---|---|---|
| 11–12 | Mapa Inteligente de Perfis de Carga e GD | `substations/mapper.py` | `test_mapa.py::test_analise_responde_as_duas_perguntas_do_desafio` |
| 13 | Identificação de subestações de distribuição | `substations/registry.py` (conjunto `subestacao` do ONS) | `test_mapa.py::test_fronteira_exige_secundario_de_distribuicao` |
| 14 | Identificação das classes de consumidores, com percentual | `profiles/classes.py` (NNLS + morfologia) | `test_mapa.py::test_nnls_recupera_mistura_conhecida` |
| 15 | Identificação de painéis solares — presença de MMGD | `vision/detector.py`, `vision/evaluate.py` | `test_vision.py::test_desempenho_do_detector_atende_o_compromisso` |
| 16 | Bases de dados de consumo | `ons/catalog.py` + limite declarado (BDGD / IBGE PPH) | `test_mapa.py::test_morfologia_urbana_nao_afirma_industrial_pelo_cadastro` |
| 17 | Pipeline replicável | `substations/mapper.py::analyse_many` | `test_mapa.py::test_analise_e_deterministica` |
| 18 | Protótipo funcional com entrada e saída definidas | `/api/mapa/*` | `test_mapa.py::test_lista_de_subestacoes_tem_as_duas_respostas` |
| 19 | Subsidiar a parametrização do CLM no ORGANON | `substations/mapper.py::clm_hint` | `test_mapa.py::test_insumo_clm_declara_que_nao_e_parametro_pronto` |

## Conceitos do glossário do deck aplicados no código

| Termo do deck | Nome no código | Onde |
|---|---|---|
| carga supervisionada | `carga_supervisionada` | `models/decomposition.py` |
| carga global | `carga_global` | idem |
| MMGD estimada | `mmgd_estimada` (nunca `medida`) | `models/mmgd.py` |
| razão da restrição REL/CNF/ENE/PAR | `cod_razaorestricao` preservado da fonte | `ons/csvio.py`, `models/risk.py` |
| origem LOC/SIS | `cod_origemrestricao` preservado | idem |
| defasagem de sistema | `lag_de_sistema` | `triangulation/evidence.py` |
| instalação não homologada | `nao_homologada` | idem |
| patamares (mínima diurna, rampa, ponta noturna) | `PATAMARES` | `config.py` |
| payload da interface ONS–DSO | envelope + `/forecast` + `/risk` | `api/` |

## Modelo de Carga Composta — parametrização para o ORGANON

Especificação em [`12-modelo-clm-parametrizacao.md`](12-modelo-clm-parametrizacao.md).
A coluna *fonte* distingue o que é normativo do que é nosso.

| Elemento do modelo | Fonte | Módulo | Teste |
|---|---|---|---|
| Topologia: trafo com LTC, alimentador, shunts, três barramentos | WECC | `api/service_clm.py::_clm_topology` | `test_payload_de_spec` |
| Critérios de aplicabilidade (5 MW · 0,98 pu · P/Q 1,61) | WECC | `clm/theory.py::applicability` | `test_aplicabilidade_reprova_e_diz_qual_criterio` |
| Base MVA: positivo, fator de carregamento, padrão 0,8 | WECC | `clm/theory.py::mva_base_from_spec` | `test_base_mva_tres_casos` |
| Carga estática ZIP com frequência | WECC | `clm/theory.py::static_pq` | `test_estatica_devolve_um_em_tensao_nominal` |
| Carga eletrônica com memória de `Vmin` | WECC | `clm/theory.py::electronic_fraction` | `test_eletronica_tem_memoria` |
| Motor D: três regimes, `Q'o`, `Gstall`/`Bstall` | WECC | `clm/theory.py::motor_d_pq` | `test_motor_d_continuo_na_tensao_de_quebra` |
| `Vstallbrk` pelo laço publicado e por bissecção | WECC | `clm/theory.py::vstallbrk` | `test_vstallbrk_dois_metodos_concordam` |
| Relé térmico e contatores com histerese | WECC | `clm/theory.py::thermal_fraction` · `contactor_fraction` | `test_termica_rampa` · `test_contator_extremos_e_histerese` |
| Conjugado `Tm = Tmo ω^Etrq` | WECC | `clm/theory.py::mech_torque` | `test_conjugado_mecanico` |
| Normalização das frações quando somam > 1 | WECC | `clm/theory.py::static_remainder` | `test_fracoes_excedentes_normalizam_e_zeram_a_estatica` |
| `Ll = 0,80 Lpp` | WECC | `clm/spec.py::_motor_3f` | `test_reatancia_de_dispersao_segue_a_regra_da_especificacao` |
| **Exemplo numérico de 100 MW, tabela publicada** | WECC | `clm/theory.py::extra_vars_allocation` | **`test_exemplo_publicado_da_especificacao`** |
| Reativos extras vêm do balanço de rede, não da soma | WECC | idem | `test_reativos_extras_nao_sao_a_soma_dos_componentes` |
| Conjunto de 124 parâmetros com valores de referência | REF | `clm/spec.py::REGISTRO` | `test_registro_completo_e_sem_duplicata` |
| H e Etrq distinguem os motores A, B e C | REF | `clm/spec.py::MOTORES_3F` | `test_motores_trifasicos_diferem_em_h_e_etrq` |
| Frações a partir da composição de classe | DERIVADO | `clm/parametrize.py::fractions_from_mix` | `test_fracoes_de_mix_puro_reproduzem_a_linha_da_classe` |
| Coerência com a fração motora do Mapa Inteligente | DERIVADO | `clm/parametrize.py::coherence_check` | `test_composicao_bate_com_o_mapa_inteligente` |
| Base MVA da capacidade de fronteira | DERIVADO | `clm/parametrize.py::build_card` | `test_cartao_marca_como_derivado_o_que_vem_de_dado_nosso` |
| Sensibilidade da penetração de ar condicionado | PREMISSA | `clm/parametrize.py::fractions_from_mix` | `test_ac_factor_move_o_motor_d_e_devolve_o_resto_a_estatica` |
| `Rfdr`/`Xfdr` escalados pelo comprimento equivalente | PREMISSA | `clm/parametrize.py::feeder_scale` | `test_escala_do_alimentador_ancora_na_mediana` |
| 29 campos não afirmados, com justificativa | A_CALIBRAR | `clm/spec.py` | `test_parametros_a_calibrar_tem_justificativa` |
| MMGD como injeção; ausência de dinâmica de inversor | declarado | `clm/parametrize.py::_dg_block` | `test_bloco_de_geracao_distribuida_declara_o_que_falta` |
| Cartão neutro, com procedência em cada linha | — | `api/service_clm.py::_card_text` | `test_cartao_texto_tem_procedencia_em_cada_linha_de_parametro` |
