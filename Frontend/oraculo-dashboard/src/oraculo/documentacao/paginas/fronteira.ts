/**
 * Grupo Fronteira T–D: SE × distribuição e Qualidade da correlação.
 * Origem: docs/oraculo/documentacao_sphinx/source/modulos/fronteira/*.rst, conferido contra
 * src/oraculo/pages/{Fronteira,Correlacao}.tsx (KPIs e títulos dos cartões).
 */
import { aviso, codigo, formula, lista, passos, secao, tabela, type PaginaDoc } from '../modelo'

const GRUPO = 'Fronteira T–D'

export const FRONTEIRA: PaginaDoc = {
  id: 'fronteira',
  titulo: 'SE de fronteira × subestação de distribuição',
  grupo: GRUPO,
  resumo: 'Cada subestação de distribuição da BDGD associada à SE de fronteira do ONS que a alimenta, com a carga e a MMGD que ela leva.',
  pergunta: 'Que subestações de distribuição cada SE de fronteira da rede básica alimenta, e que carga e que MMGD chegam a ela por esse caminho?',
  rotas: ['GET /api/fronteira/status', 'GET /api/fronteira/resumo', 'GET /api/fronteira/se/{sub_id}', 'GET /api/clm/cartao?fonte=bdgd'],
  secoes: [
    secao(
      'Por que esta seção existe',
      'O Mapa Inteligente responde ao perfil de consumo e à GD por **evidência indireta** (telhados e prior do subsistema). A ANEEL publica, em dado aberto, as unidades consumidoras de média e alta tensão com o código da subestação de distribuição (SED) que as atende, 12 meses de energia e demanda e o vínculo com a GD. Com isso a composição da carga passa a ser **medida no faturamento**.',
      codigo(
        [
          'SE de fronteira (ONS)           SED (ANEEL · BDGD)',
          'subestacao + capacidade-  ←──── UCMT / UCAT: SUB, classe,',
          'transformacao, sec ≤ 138 kV     energia, demanda, CEG_GD',
          '         │     modelo gravitacional   │',
          '         └─────────────┬──────────────┘',
          '                       ▼',
          '   carga por classe + MMGD por SE de fronteira',
          '   (MT/AT medida · BT do SAMP rateada · GD do cadastro)',
          '                       ▼',
          '   cartão do Modelo de Carga Composta (fonte = BDGD)',
        ].join('\n'),
      ),
    ),
    secao(
      'Primeira execução',
      'Na primeira abertura a base agregada é construída em segundo plano (cerca de 1 minuto e ~270 MB baixados da ANEEL e do IBGE). O cartão **Progresso** mostra cada etapa e a tela se redesenha sozinha. Depois a base fica no cache por 7 dias.',
    ),
    secao(
      'Fontes, todas abertas',
      tabela(
        ['Conjunto', 'Uso', 'Granularidade'],
        [
          ['ONS `subestacao` + `capacidade-transformacao`', 'SE de fronteira: posição, agente, MVA de fronteira', 'por subestação'],
          ['ANEEL · BDGD `UCMT_PJ` e `UCAT_PJ`', 'reconstrução da SED; energia e demanda por classe', 'por unidade consumidora (pessoa jurídica)'],
          ['ANEEL · empreendimentos de MMGD', 'MMGD por município e, pelo `CEG_GD`, por SED', 'por empreendimento'],
          ['ANEEL · SAMP', 'energia de baixa tensão por distribuidora e classe', 'por distribuidora, mensal'],
          ['IBGE · SIDRA 6579 e malha municipal', 'rateio da baixa tensão; centroide do município', 'por município'],
        ],
      ),
    ),
    secao(
      'Como a SED é reconstruída',
      'Agrupando as UCs ativas (`SIT_ATIV = AT`) por `DIST|SUB` (o código é único na distribuidora, não no país):',
      lista(
        '**posição** — mediana das coordenadas das UCs: a posição da **carga**, não a do barramento;',
        '**energia por classe** — soma dos 12 meses, nas quatro classes do CLM;',
        '**demanda** — máximo mensal de cada UC, somado (não coincidente);',
        '**municípios atendidos** — contagem de UCs por município, usada no rateio.',
      ),
    ),
    secao(
      'A associação',
      'Para cada SED s e cada SE de fronteira f a até 150 km:',
      formula('a(s,f) = MVA_f^α · e^(−d(s,f)/λ) · b_UF · b_grupo          p(s,f) = a(s,f) / Σ_f\' a(s,f\')'),
      'Com α = 0,5, λ = 20 km, bônus de 1,5 para a mesma UF e de 1,5 quando a distribuidora e o agente da SE no ONS são do mesmo grupo econômico. O vínculo primário é o de maior p; abaixo de 0,5 é marcado **ambíguo**.',
      aviso(
        'medido',
        'Por que α = 0,5 e λ = 20 km',
        'Escolhidos pela varredura de [[correlacao]]. Com α = 1 a SE grande atrai demais e deixa 103 SEs sem carga; com α = 0 (só distância) SEs ficam sobrecarregadas em até 330%. A combinação escolhida dá o carregamento mais homogêneo, nenhuma SE acima de 100%, e escolhe a SE mais próxima em 87% dos casos.',
      ),
    ),
    secao(
      'Baixa tensão e MMGD',
      'A BDGD aberta usada aqui publica só pessoa jurídica. A baixa tensão vem do **SAMP** (energia TUSD por distribuidora e classe, apenas mercados *Regular*: as linhas de Sistema de Compensação registram energia compensada e somá-las contaria o consumo duas vezes). O SAMP desce aos municípios pela população do IBGE e sobe às SEDs na proporção das UCs de média tensão de cada uma no município.',
      'A MMGD vem do cadastro da ANEEL. A que está numa UC de média tensão casa **exatamente** com a SED pelo `CEG_GD`; o restante é rateado pelo município.',
    ),
    secao(
      'O que a tela mostra',
      tabela(
        ['Elemento', 'Conteúdo'],
        [
          ['**KPIs**', 'SEs de fronteira com carga, SEDs associadas, energia alocada, MMGD alocada'],
          ['**Mapa**', 'SEs de fronteira (tamanho ∝ √MVA) e SEDs coloridas pela probabilidade do vínculo (≥ 0,7; 0,5–0,7; 0,3–0,5; < 0,3 ambígua; sem SE no raio); a SE selecionada desenha as linhas até suas SEDs'],
          ['**SEs de fronteira**', 'lista para escolher a SE'],
          ['**Detalhe da SE**', 'SEDs associadas, energia, carga média, MMGD instalada; energia medida e rateada por classe, sazonalidade, carregamento implícito e penetração'],
          ['**Duas representações da mesma SE**', 'composição e MMGD pelo Mapa Inteligente e pela BDGD, lado a lado, com a diferença em pontos percentuais'],
          ['**Insumo ao Modelo de Carga Composta**', 'o botão envia a SE à tela [[clm]] com a composição pela BDGD'],
          ['**Subestações de distribuição associadas**', 'distribuidora, UCs, energia, classe dominante, MMGD direta, distância, p e as SEs alternativas'],
          ['**Pipeline replicável** e **Premissas da associação**', 'as etapas e os parâmetros declarados'],
        ],
      ),
      aviso(
        'nota',
        'Privacidade',
        'CPF/CNPJ e nome do titular da GD, endereço e CEP das UCs não são lidos. O arquivo bruto vai para um diretório temporário e é apagado após a agregação; o cache guarda só agregados por SED, município e distribuidora.',
      ),
      aviso(
        'limite',
        'O limite mais importante',
        '**A associação SED → SE de fronteira é inferida.** A topologia de subtransmissão está no cadastro interno da distribuidora, não em dado aberto. Cada vínculo sai com probabilidade e alternativas; [[correlacao]] mostra onde a inferência é frágil.',
      ),
    ),
  ],
}

export const CORRELACAO: PaginaDoc = {
  id: 'correlacao',
  titulo: 'Qualidade da correlação SE × SED',
  grupo: GRUPO,
  resumo: 'Sem verdade de campo para a topologia: validação externa contra a carga do ONS, coerência física e sensibilidade às premissas.',
  pergunta: 'O quanto se pode confiar na associação SED → SE de fronteira, se não existe verdade de campo para comparar?',
  rotas: ['GET /api/fronteira/qualidade'],
  secoes: [
    secao(
      'Os KPIs',
      tabela(
        ['KPI', 'Como ler'],
        [
          ['**SEDs associadas**', 'quantas SEDs receberam vínculo'],
          ['**Vínculos ambíguos**', 'fração com p < 0,5 (várias SEs plausíveis)'],
          ['**Mesma UF**', 'fração associada a SE da mesma UF'],
          ['**SE mais próxima escolhida**', 'fração em que o vínculo primário é a SE mais próxima'],
        ],
      ),
    ),
    secao(
      'Três frentes de validação',
      passos(
        '**Validação externa contra o ONS** — a energia alocada às SEs de cada subsistema é comparada com a carga verificada do ONS no mesmo ano. As duas são calculadas de forma independente.',
        '**Coerência física** — o carregamento implícito de cada SE (carga média alocada ÷ MVA de fronteira, FP 0,92) deve ser homogêneo e plausível.',
        '**Sensibilidade às premissas** — varredura de α ∈ {1; 0,5; 0} e λ ∈ {30; 20; 12} km.',
      ),
      aviso(
        'premissa',
        'A razão fica abaixo de 100% por construção',
        'Perdas técnicas e não técnicas, autoconsumo da MMGD e carga ligada direto na rede básica não aparecem no faturamento da distribuidora. Verifica-se a **ordem de grandeza** e a estabilidade entre subsistemas. No Norte a razão é menor porque parte relevante da carga é eletrointensiva e conectada à rede básica.',
      ),
      'SE acima de 100% indica SE vizinha ausente do cadastro de fronteira ou atração excessiva; SE abaixo de 5% costuma ser de interligação, com pouca carga local. O cartão **SEs fora da faixa plausível** as lista.',
      aviso(
        'medido',
        'Como ler a varredura',
        'Não existe linha "certa": existe a fisicamente mais coerente. λ menor reduz a ambiguidade, mas com α = 0,5 e λ = 12 km surgem SEs acima de 100%. A configuração em uso (destacada) é a de menor dispersão de carregamento sem nenhuma SE sobrecarregada.',
      ),
    ),
    secao(
      'Histogramas',
      lista(
        '**Distância SED → SE** — mediana em torno de 20 km, compatível com o alcance da subtransmissão de 69–138 kV.',
        '**Probabilidade do vínculo** — concentração abaixo de 0,5 nas metrópoles, onde há várias SEs a poucos quilômetros.',
        '**Carregamento implícito** — energia média, não ponta: valores entre 10% e 40% são esperados.',
      ),
      'Completam a tela os cartões **MMGD e baixa tensão**, **Premissas**, **Privacidade** e **Limites declarados**.',
    ),
    secao(
      'Limites declarados',
      aviso(
        'limite',
        'Limites',
        passos(
          'A topologia de subtransmissão não é dado público: a associação deve ser confirmada com o cadastro da distribuidora ou com o SIGA/ONS antes de uso operativo.',
          'A posição da SED é a mediana das UCs de média e alta tensão, não a coordenada do barramento.',
          'A baixa tensão residencial é rateada por população, não medida por SED.',
          'Carregamento é energia média sobre MVA nominal: indicador de consistência, não de ponta.',
        ),
      ),
    ),
  ],
}

export const PAGINAS_FRONTEIRA: PaginaDoc[] = [FRONTEIRA, CORRELACAO]
