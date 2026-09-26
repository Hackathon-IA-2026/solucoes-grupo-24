/**
 * Grupo Investimento: Alocação de BESS, Método e sensibilidade, Projeção do corte ENE.
 * Origem: docs/oraculo/documentacao_sphinx/source/modulos/investimento/*.rst, conferido contra
 * src/oraculo/pages/{Bess,BessMetodo,Projecao}.tsx.
 */
import { aviso, codigo, formula, lista, passos, secao, tabela, type PaginaDoc } from '../modelo'

const GRUPO = 'Investimento'

/** Aviso comum às três telas do grupo (escrito uma vez só). */
const CORTE_NAO_E_FUTURO = aviso(
  'limite',
  'O corte observado não é o corte futuro',
  'Obras de transmissão previstas podem eliminar restrições locais. O ranking indica onde o armazenamento teria recuperado mais energia na janela observada; a decisão de investimento ainda depende de receita, regulação e do plano de expansão.',
)

export const BESS: PaginaDoc = {
  id: 'bess',
  titulo: 'Alocação de BESS pelo corte observado',
  grupo: GRUPO,
  resumo: 'Onde um armazenamento recupera mais energia cortada das usinas centralizadas, e quanto desse corte é excedente criado pela MMGD.',
  pergunta: 'Em quais subestações de conexão das usinas centralizadas um BESS recuperaria mais energia cortada, e quanto desse corte é excedente que a MMGD cria ao reduzir a carga líquida?',
  rotas: ['GET /api/bess/status', 'GET /api/bess/ranking?w_energia=&w_mmgd=&w_recorrencia=&w_local=', 'GET /api/bess/sitio/{code}'],
  secoes: [
    secao(
      'Onde está o corte, e onde está a MMGD',
      '**O corte acontece nas usinas centralizadas; a MMGD não é cortada.** Ela reduz a carga líquida ao meio-dia e aprofunda a barriga da **curva do pato**: o excedente vira restrição por razão energética de origem sistêmica (ENE + SIS) em qualquer usina do SIN. Por isso há duas teses:',
      lista(
        '**Tese 1 · BESS junto à geração cortada** — o ranking. Absorve o corte da usina e devolve na rampa do fim da tarde.',
        '**Tese 2 · BESS junto à carga** — onde a MMGD mais pesa sobre a carga (ver [[fronteira]]). Achata a curva do pato na origem, mas não recupera o corte de uma usina específica.',
      ),
      codigo(
        [
          'constrained-off apurado (ONS, 12 meses, FV + eólica)',
          '         │  por ponto de conexão → SE (código ONS · SIGA/ANEEL)',
          '         ▼',
          'série semi-horária do corte por sítio',
          '         │  BESS simulado: carga no corte, 1 ciclo/dia',
          '         ▼',
          'energia recuperável e dimensionamento pelo ciclo marginal',
          '         │  + corte ENE+SIS atribuível à MMGD do SIN (curva do pato)',
          '         ▼',
          'ranking de sítios, com pesos ajustáveis e teste de estabilidade',
        ].join('\n'),
      ),
    ),
    secao(
      'A base',
      'Doze meses completos de `restricao_coff_fotovoltaica` e `restricao_coff_eolica_usi`. O corte é o campo oficial `val_geracaonaorealizadaapurada` (MW médio em 30 min). Cada mês é agregado por ponto de conexão; o bruto (~70 MB por mês) não é guardado. Na primeira abertura, o cartão **Progresso** mostra os meses agregados.',
      'O `id_pontoconexao` tem o código da SE em largura fixa de 6 caracteres (`RNACT-500-A` → RNACT; `MGJBA3500-A` → MGJBA3): separar pelo primeiro hífen erraria os códigos de 6 letras. Quando a SE é coletora privada e não está no cadastro do ONS, a posição vem das usinas (`modalidade-usina` → CEG → coordenada no SIGA/ANEEL).',
    ),
    secao(
      'Simulação e dimensionamento',
      formula('absorvido = min(E, Σ_t min(corte_t, P) · 0,5 h)        entregue = η · absorvido,   η = 0,88'),
      'Por dia, com potência P e energia E, um ciclo por dia; energia e ciclos anualizados.',
      aviso(
        'premissa',
        'Dimensionamento pelo ciclo marginal',
        'Sobe-se na fronteira eficiente da grade (25 a 500 MW × 2, 4 e 6 h) e para-se quando o MWh **adicional** cicla menos de 200 vezes por ano. A regra "maior BESS que ainda cicla bem" escolheria sempre o topo da grade num sítio grande: o ativo inteiro cicla bem mesmo quando os últimos MWh quase não são usados.',
      ),
    ),
    secao(
      'Corte induzido pela MMGD',
      formula('induzido(t) = min(corte_ENE+SIS,SIN(t), MMGD_SIN(t))'),
      'Sem a MMGD, a carga líquida seria maior nessa quantidade. O volume é rateado entre os sítios pelo corte ENE+SIS de cada um. É um **limite superior** contrafactual; corte CNF, REL ou de origem local não é atribuído à MMGD.',
      aviso('nota', 'A MMGD vizinha não escolhe o sítio de geração', 'MMGD alta ao lado de uma usina não faz aquela usina ser mais cortada. A penetração local de MMGD aparece na Tese 2, não na pontuação do sítio.'),
    ),
    secao(
      'Pontuação',
      'Soma ponderada de **postos percentuais** (0 a 1). Postos em vez de valores brutos impedem que um sítio gigante esmague os outros; empate recebe o posto médio. Os pesos são ajustáveis no cartão **Pesos da pontuação** e o servidor refaz o ranking (a interface não calcula nada).',
      tabela(
        ['Componente', 'Peso padrão', 'Medida'],
        [
          ['Energia recuperável', '45%', 'GWh/ano entregues pelo BESS dimensionado para o sítio'],
          ['Excedente da MMGD', '20%', 'fração do corte do sítio atribuível à MMGD (ENE+SIS na curva do pato)'],
          ['Recorrência', '20%', 'fração dos dias com corte ≥ 1 MWh'],
          ['Restrição local', '15%', 'fração do corte com origem LOC'],
        ],
      ),
    ),
    secao(
      'O que a tela mostra',
      lista(
        '**KPIs** — corte apurado, concentração, excedente da MMGD e recuperável no top 10.',
        '**Mapa de sítios de corte** — dimensionados pela energia cortada; top 10 numerado, pontuação ≥ 0,5 e demais.',
        '**Por que há excedente: a curva do pato** — perfil médio horário por subsistema: carga com MMGD, supervisionada, líquida (menos eólica e solar centralizadas) e o corte.',
        '**Detalhe do sítio** — BESS sugerido, energia recuperada, as frases de *por que este sítio*, curva de dimensionamento, **quando o corte acontece** (mês × hora), perfil médio diário, razão, origem e usinas no sítio.',
        '**Pipeline replicável** e **Premissas**.',
      ),
      CORTE_NAO_E_FUTURO,
    ),
  ],
}

export const BESS_METODO: PaginaDoc = {
  id: 'bessmetodo',
  titulo: 'BESS: método, cobertura e sensibilidade',
  grupo: GRUPO,
  resumo: 'De onde vem cada número do ranking, o que ficou de fora e o quanto o resultado depende dos pesos.',
  pergunta: 'De onde vem cada número do ranking, o que ficou de fora e o quanto o resultado depende dos pesos escolhidos?',
  rotas: ['GET /api/bess/metodo'],
  secoes: [
    secao(
      'Cobertura',
      'O cartão **Localização do corte** mostra a fração da energia cortada localizada pela SE do ONS, pelas usinas no SIGA e não localizada. Sítio sem coordenada continua no ranking, com a penetração de MMGD da UF, e aparece em **Sítios não localizados**. **Razão da restrição** e **Origem** decompõem o corte total.',
    ),
    secao(
      'Estabilidade do top 10',
      'O top 10 dos pesos padrão é comparado ao top 10 em seis cenários: só energia, curva do pato (excedente da MMGD em destaque), restrição local, pesos iguais, sem MMGD e o próprio padrão. Excedente da MMGD e restrição local são quase complementares: expressam teses diferentes.',
      aviso('medido', 'Sítio robusto', 'O sítio que permanece no top 10 em todos os cenários é candidato **robusto**: sua posição não depende de uma escolha de peso.'),
    ),
    secao(
      'Limites declarados',
      aviso(
        'limite',
        'Limites',
        passos(
          'O corte apurado é a decisão operativa observada, não o potencial físico, e obras de transmissão podem eliminá-lo.',
          'Um ciclo por dia, sem restrição de rede na descarga; sem modelo de receita (PLD, serviços ancilares, capacidade).',
          'Corte sistêmico (SIS) é aliviado por armazenamento em qualquer ponto do subsistema; o local (LOC), só no ponto.',
          'O corte induzido pela MMGD é limite superior contrafactual, e a MMGD vem da estimativa do envelope (um piso).',
          'A MMGD não é cortada e não escolhe o sítio de geração.',
        ),
      ),
    ),
  ],
}

export const PROJECAO: PaginaDoc = {
  id: 'projecao',
  titulo: 'Projeção do corte por razão energética',
  grupo: GRUPO,
  resumo: 'Quanto corte ENE vem pela frente, quanto dele a MMGD explica, e quanto BESS ele justifica no SIN.',
  pergunta: 'Quanto corte por razão energética (ENE) vem pela frente, quanto dele a MMGD explica, e quanto armazenamento ele justifica no SIN?',
  rotas: ['GET /api/ene/status', 'GET /api/ene/projecao?g_vre=&g_mmgd=&g_load=&flex_gw='],
  secoes: [
    secao(
      'As séries',
      tabela(
        ['Série', 'Origem'],
        [
          ['Corte ENE+SIS horário do SIN', 'constrained-off do ONS; eólica desde 10/2021, fotovoltaica desde 04/2024'],
          ['Carga, eólica e solar verificadas', 'balanço de energia horário do ONS, SIN'],
          ['MMGD conectada por mês', 'cadastro da ANEEL, pela data de conexão'],
        ],
      ),
      'A série fotovoltaica de corte só existe a partir de 04/2024; antes disso o total do SIN está incompleto, e o modelo só é calibrado dali em diante.',
    ),
    secao(
      'Por que um modelo físico',
      'O corte ENE cresceu em saltos; uma tendência ajustada a isso projeta o salto para sempre. O que o gera, porém, é mensurável hora a hora:',
      formula(['NL(t) = carga supervisionada(t) − [eólica + solar]_potencial(t)', 'corte_ENE+SIS(t) = α · max(0, θ_mês − NL(t))'].join('\n')),
      'A geração **potencial** é a verificada mais a cortada: sem somar o corte de volta, o modelo seria circular. θ tem um valor por mês (a inflexibilidade hidráulica é sazonal) e α mede quanto do excedente vira corte apurado. Parâmetros ajustados por mínimos quadrados em grade.',
    ),
    secao(
      'Validação',
      'Ajuste até 08/2025, teste nos 12 meses seguintes, comparado com o ingênuo *mesmo mês do ano anterior*: erro percentual mensal, viés do total e correlação horária no teste (KPI **Erro fora da amostra** e cartão **Validação fora da amostra**).',
    ),
    secao(
      'Projeção e cenários',
      formula(['NL_k = [(sup + MMGD)·(1+g_c)^k − MMGD·(1+g_m)^k] − VRE·(1+g_v)^k', 'θ_k = θ − flex · k'].join('\n')),
      'Sobre o ano de referência observado (últimos 12 meses: mesmo clima, mesmo perfil). Crescer a MMGD reduz a carga supervisionada e aprofunda a curva do pato.',
      lista(
        '**PLAN 2026-2030 (2ª RQ)** — a referência: carga global e MMGD do SIN ano a ano (ONS/EPE/CCEE, 07/08/2026): carga de 84.989 MWmed (2026) a 101.947 MWmed (2030); MMGD de 8.536 a 11.240 MWmed (55,6 a 72,5 GW instalados). Eólica + solar seguem o PAR/PEL 2025 (+2,3% a.a.).',
        '**PAR/PEL 2025** — MMGD de 46,2 GW (dez/2025) a 65,3 GW (fim de 2029).',
        '**Tendência observada** — extrapolação das séries; só contraste.',
        '**Cenário personalizado** — taxas de crescimento e flexibilidade escolhidas na tela, enviadas ao servidor.',
      ),
      'A MMGD horária tem o perfil da estimativa do envelope e o **nível oficial**: a estimativa (3,1 GWmed no ano de referência) é escalada para os 8.536 MWmed do PLAN em 2026 — sozinha, subestimava a MMGD em 2,7 vezes. A coluna "da MMGD" é a diferença para a mesma projeção com a MMGD no nível de referência: **atribuição, não cenário**.',
      aviso(
        'medido',
        'A leitura que decide o investimento',
        'Na trajetória oficial, a carga global (+4,5% a.a., com datacenters) cresce mais que a expansão centralizada considerada (+2,3% a.a.): o corte ENE+SIS cai, mas cerca de metade dele em 2030 passa a ser devida ao crescimento da MMGD. No ritmo observado de expansão centralizada, o corte explode. O caso de BESS depende sobretudo do ritmo da expansão centralizada frente à carga.',
      ),
    ),
    secao(
      'BESS justificável',
      'O corte ENE+SIS é **sistêmico**: um armazenamento em qualquer ponto do SIN o absorve. O BESS é dimensionado no nível do SIN com o critério do ciclo marginal (1 a 30 GW × 2, 4 e 6 h, enquanto o GWh adicional cicla ao menos 200 vezes por ano). O cartão **Onde o BESS do último ano entraria** rateia o resultado entre os sítios de maior corte ENE+SIS.',
      aviso(
        'limite',
        'Limites',
        'Um único ano de referência (clima e hidrologia daquele ano). θ constante no cenário base: sem nova transmissão nem flexibilidade, o corte projetado é o que rede, armazenamento e flexibilidade precisariam resolver. Expansão centralizada além do PAR/PEL aumenta o corte.',
      ),
      CORTE_NAO_E_FUTURO,
    ),
  ],
}

export const PAGINAS_INVESTIMENTO: PaginaDoc[] = [BESS, BESS_METODO, PROJECAO]
