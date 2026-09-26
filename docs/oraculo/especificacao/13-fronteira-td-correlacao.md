# 13 · Fronteira T–D — subestação de distribuição × SE da rede básica

Objetivo: levar ao modelo de carga de cada **SE de fronteira da rede básica**
(ONS) a carga e a MMGD que efetivamente passam por ela, a partir das
**subestações de distribuição** (SED) que ela alimenta — com energia faturada
real, e não com estimativa morfológica.

## 13.1 O problema de dado

| Ponta | Onde está | Acesso a partir da rede corporativa |
|---|---|---|
| SE de fronteira | ONS · `subestacao` + `capacidade-transformacao` | CKAN/S3 do ONS — ok |
| SED (camada `SUB` da BDGD) | ANEEL · hub ArcGIS | **bloqueado** (proxy com certificado próprio) |
| UCs de MT/AT com o código da SED | ANEEL · CKAN, pacote BDGD (`UCMT_PJ`, `UCAT_PJ`) | ok |
| MMGD por empreendimento | ANEEL · CKAN, relação de empreendimentos de GD | ok |
| Mercado de baixa tensão | ANEEL · CKAN, SAMP (`datastore_search`) | ok |
| População e malha municipal | IBGE · SIDRA 6579 e API de malhas | ok |

A camada geográfica `SUB` não é alcançável, mas **não é necessária**: cada
UC de média e alta tensão traz `SUB` (código da SED), `CTMT` (alimentador),
`CLAS_SUB`, `ENE_01..12`, `DEM_01..12`, `CEG_GD` e `POINT_X/POINT_Y`. A SED é
reconstruída a partir das cargas que atende.

Medido em 26/09/2026:

| | |
|---|---|
| UCMT | 314.493 UCs (288.864 ativas) · 3.996 SEDs · 99 distribuidoras · 141 TWh/ano |
| UCAT | 2.122 UCs · 1.457 códigos SUB · 86 TWh/ano |
| Cadastro de MMGD | 4.656.839 empreendimentos · 53,97 GW |
| `NomSubEstacao` preenchido no cadastro de GD | 2.938 (0,06%) — **inutilizável** como vínculo |
| `CEG_GD` da UCMT que casa com o cadastro | 40.358 empreendimentos · 7,72 GW — **vínculo exato** |
| SAMP 2025, BT, mercados Regular | residencial 160 TWh (ordem de grandeza nacional) |

## 13.2 Decisões

| # | Decisão | Motivo |
|---|---|---|
| F1 | SED = agregado de UCs por `DIST|SUB` | `SUB` é único dentro da distribuidora, não no país |
| F2 | Posição da SED = mediana das UCs | É a posição da **carga** que importa para a associação; a mediana resiste a UC mal georreferenciada |
| F3 | Associação gravitacional `MVA^α · e^(−d/λ)`, α = 0,5, λ = 20 km | Varredura de sensibilidade: α = 1 deixa 103 SEs vazias; α = 0 sobrecarrega SEs em até 330% |
| F4 | Bônus ×1,5 mesma UF; ×1,5 mesmo grupo econômico | O agente no ONS é quase sempre a transmissora: a coincidência é de grupo (CPFL T × CPFL Paulista), evidência moderada |
| F5 | Probabilidade < 0,5 = vínculo ambíguo, exibido | Não há verdade de campo; esconder a ambiguidade seria afirmar o que não se sabe |
| F6 | SAMP só mercados *Regular* | As linhas de *Sistema de Compensação* registram energia compensada: somá-las conta o mesmo consumo duas vezes |
| F7 | BT rateada por população e depois pelas UCs de MT da SED no município | A BDGD aberta só tem pessoa jurídica |
| F8 | MMGD: `CEG_GD` quando existe; senão, município | 14% da potência com vínculo exato; o resto, com o melhor proxy disponível |
| F9 | Só agregados no cache | O cadastro de GD traz CPF e nome do titular; a BDGD, endereço |
| F10 | Associação recalculada a cada carga, não guardada | Mudança de premissa em `config.FRONTEIRA` vale na hora, sem reconstruir a base |

## 13.3 Validação

Sem verdade de campo para a topologia de subtransmissão, três frentes:

1. **Externa** — energia alocada por subsistema ÷ carga verificada do ONS no
   mesmo ano. Abaixo de 1 por construção (perdas, autoconsumo da MMGD, carga
   na rede básica). Medido: SE 0,65 · S 0,75 · NE 0,62 · N 0,39.
2. **Coerência física** — carregamento implícito (MW médio ÷ MVA × 0,92):
   mediana ~0,2, nenhuma SE acima de 100% na configuração escolhida.
3. **Sensibilidade** — varredura α × λ exposta na tela.

## 13.4 Saída para o Modelo de Carga Composta

`GET /api/clm/cartao?sub_id=…&fonte=bdgd` usa a composição por classe da
correlação (energia faturada) e a MMGD do cadastro da ANEEL no lugar da
composição morfológica do Mapa Inteligente. A fração motora usa a mesma
tabela de premissas (`mapper.MOTOR_FRACTION`): as duas telas não podem
divergir sobre a mesma grandeza.

## 13.5 Limites

1. A associação é inferida; deve ser confirmada com o cadastro da
   distribuidora ou com o SIGA/ONS antes de uso operativo.
2. A posição da SED é a da carga, não a do barramento.
3. A baixa tensão residencial é rateada, não medida por SED.
4. Carregamento implícito é energia média, não ponta.
5. A camada `SUB` da BDGD (coordenada do barramento, nome da SED) melhoraria
   a posição e permitiria validar por nome; o protótipo aceita arquivos
   baixados manualmente em `ORACULO_FRONTEIRA_RAW`.
