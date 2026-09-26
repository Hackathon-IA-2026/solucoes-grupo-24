/**
 * Grupo Análise (telas do protótipo): Curtailment observado, Perfis e CLM, Triangulação.
 * Texto revisado a partir de docs/oraculo/documentacao_sphinx/source/modulos/analise/*.rst,
 * conferido contra src/oraculo/pages/{Curtailment,Perfis,Triangulacao}.tsx. Os significados dos
 * códigos de razão seguem o dicionário do ONS, como na nota da própria tela de Curtailment.
 */
import { aviso, formula, lista, secao, tabela, type PaginaDoc } from '../modelo'

const GRUPO = 'Análise'

/** Códigos de razão do constrained-off (dicionário do ONS); usados também pelo glossário. */
export const CODIGOS_RAZAO: string[][] = [
  ['**ENE**', 'razão **energética**: excedente de geração frente à carga e ao intercâmbio; foco do Desafio 1'],
  ['**CNF**', '**confiabilidade** elétrica: a rede não suporta escoar a geração com segurança'],
  ['**REL**', '**indisponibilidade externa** (de equipamento fora da usina); não é modelada nas previsões'],
  ['**PAR**', '**parecer de acesso**: restrição prevista nas condições de acesso da usina'],
]

export const CURTAILMENT: PaginaDoc = {
  id: 'curtailment',
  titulo: 'Curtailment observado',
  grupo: GRUPO,
  resumo: 'Montante, razão e origem da restrição, a partir dos registros de constrained-off do ONS.',
  pergunta: 'Quanto foi efetivamente restringido, em que área e por qual razão?',
  rotas: ['GET /api/risk?horizon=d1&level=estado&asymmetric=0'],
  secoes: [
    secao(
      'Mesma fonte do risco, pergunta oposta no tempo',
      'É o mesmo payload da tela [[risco]], lido pelo lado do **registro observado** em vez do lado preditivo: [[risco]] olha para frente e produz alerta; esta tela olha para o constrained-off já publicado.',
    ),
    secao(
      'Os quatro KPIs',
      tabela(
        ['KPI', 'Unidade', 'Como ler'],
        [
          ['**Energia restringida na janela**', 'GWh', 'integral do corte no período carregado; dimensiona o custo do problema'],
          ['**Maior corte horário**', 'MWmed', 'o pior instante da janela'],
          ['**Taxa média de ocorrência**', '%', 'fração das horas com restrição; separa o evento raro e intenso do crônico e moderado'],
          ['**Participação da razão ENE**', '%', 'quanto do total teve razão energética, o recorte que a solução persegue'],
        ],
      ),
    ),
    secao(
      'Cartões',
      lista(
        '**Montante restringido por área e razão** — barras empilhadas: onde a restrição se concentra e se a natureza é energética ou de rede.',
        '**Probabilidade horária por área** — cada linha uma área, cada coluna uma hora da janela prospectiva, intensidade proporcional à probabilidade. A forma revela a assinatura: fotovoltaica no meio do dia, eólica tipicamente noturna no Nordeste.',
        '**Histórico por área** — horas com registro, energia restringida, maior corte, taxa de ocorrência e razão predominante. Limiar de rótulo: 10% da disponibilidade agregada (p95).',
        '**Códigos de razão** e **Códigos de origem** — os dicionários do ONS, vindos da API.',
      ),
    ),
    secao(
      'Códigos de razão',
      tabela(['Código', 'Significado'], CODIGOS_RAZAO),
      aviso(
        'nota',
        'Por que os dicionários estão na tela',
        'Um número de corte sem o código de razão não é interpretável. A mesma restrição de 100 MW significa coisas diferentes se é **ENE** (sobra energia) ou **CNF** (a rede não suporta). Sem essa distinção, somaríamos grandezas de naturezas distintas.',
      ),
    ),
    secao(
      'Fonte dos dados',
      tabela(
        ['Conjunto', 'Conteúdo'],
        [
          ['`restricao_coff_fotovoltaica`', 'restrição semi-horária, por usina fotovoltaica'],
          ['`restricao_coff_eolica_usi`', 'restrição semi-horária, por usina eólica'],
        ],
      ),
      'Esquemas verificados por inspeção direta dos arquivos publicados. A leitura usa requisições `Range` para não baixar arquivos inteiros.',
    ),
    secao(
      'O que esta tela não afirma',
      aviso(
        'limite',
        'Limites',
        lista(
          '**O registro é a decisão operativa**, não o potencial físico: responde "quanto foi determinado como restrição", não "quanta energia teria sido gerada".',
          'A granularidade publicada é **por usina**; a agregação por área é nossa.',
          'A janela carregada é a recente; séries longas exigem ingestão de mais recursos (`POST /api/ingest`, em [[dados]]).',
        ),
      ),
    ),
  ],
}

export const PERFIS: PaginaDoc = {
  id: 'perfis',
  titulo: 'Perfis representativos e insumos ao CLM',
  grupo: GRUPO,
  resumo: 'Forma típica da carga e da MMGD por dia-tipo, e as grandezas agregadas que isso oferece à modelagem de carga.',
  pergunta: 'Qual é a forma típica da carga e da MMGD por dia-tipo, e que grandezas agregadas isso oferece à modelagem de carga?',
  rotas: ['GET /api/profiles?area=SE'],
  secoes: [
    secao(
      'Insumo, não produto',
      aviso(
        'nota',
        'Esta tela e a de parametrização do CLM',
        'Esta tela caracteriza **perfis agregados por subsistema** e propõe grandezas de entrada. A tela [[clm]] emite o **cartão de parâmetros do CMPLDW**, campo a campo, com procedência. Esta é o insumo; aquela é o produto.',
      ),
    ),
    secao(
      'Os quatro KPIs',
      tabela(
        ['KPI', 'Unidade', 'Como ler'],
        [
          ['**Fator de carga**', '—', 'carga média ÷ carga de pico; perto de 1, curva plana (assinatura industrial)'],
          ['**Penetração solar no pico**', '%', 'participação da solar no instante de maior carga: distingue a área onde a solar alivia a ponta daquela onde ela já saiu'],
          ['**Âncora noturna**', 'MWmed', 'carga na madrugada, quando a MMGD é nula por construção: a referência que separa carga de geração distribuída'],
          ['**Rampa máxima**', 'MW/h', 'maior variação horária no perfil típico; dimensiona a flexibilidade'],
        ],
      ),
    ),
    secao(
      'Perfis por dia-tipo e perfil de MMGD',
      'Curvas de 24 h por dia-tipo (útil, sábado, domingo e feriado) com banda de quantis em torno da mediana, e a mesma decomposição restrita à MMGD estimada: a forma vem da geometria solar; a amplitude, da capacidade instalada e do fator de nebulosidade.',
      aviso(
        'premissa',
        'Por que dia-tipo e não média',
        'A média de todos os dias produz uma curva que não corresponde a nenhum dia real: mistura o platô de expediente com o fim de semana. Os dias-tipo preservam a forma. Os feriados móveis são calculados pelo algoritmo de Meeus/Butcher para a Páscoa (`Backend/oraculo/core/calendar_br.py`).',
      ),
      aviso(
        'medido',
        'Um erro grande que este cartão expôs',
        'A primeira versão estimava a MMGD por extrapolação ancorada na noite e dava pico de **8,1 GW** no Sudeste, implausível: a extrapolação é mal condicionada, porque as harmônicas diárias são identificadas fora do suporte em que a geração existe. O **método do envelope** (percentil 90 da carga por mês, dia-tipo e hora) levou o pico a **12,5 GW**, participação de **23%**, compatível com a capacidade instalada declarada.',
      ),
    ),
    secao(
      'Insumos agregados propostos',
      'Fator de carga, participação da MMGD, âncora noturna, amplitude diária e rampa. Derivam da identidade verificada por teste:',
      formula('carga global = carga supervisionada + MMGD estimada'),
      aviso(
        'limite',
        'O que estes números são, e o que não são',
        'São **grandezas observadas** que o especialista usa ao escolher a composição do modelo de carga. **Não são parâmetros prontos para simulação**; a distinção está no próprio payload (campo `aviso`).',
      ),
    ),
    secao(
      'O que esta tela não afirma',
      aviso(
        'limite',
        'Limites',
        lista(
          'A MMGD é **estimada**, com viés conservador (um piso).',
          'Os perfis são **por subsistema**: não existe curva de carga por subestação em dado aberto (R3).',
          'Os quantis descrevem a **variabilidade histórica** da forma, não incerteza de previsão (essa está em [[operacao]]).',
        ),
      ),
    ),
  ],
}

export const TRIANGULACAO: PaginaDoc = {
  id: 'triangulacao',
  titulo: 'Triangulação de evidências',
  grupo: GRUPO,
  resumo: 'Três camadas independentes e a lógica de desempate que separa defasagem administrativa de instalação não homologada.',
  pergunta: 'O ativo de geração distribuída existe fisicamente, está na topologia da distribuidora e está homologado na ANEEL?',
  rotas: ['GET /api/triangulation'],
  secoes: [
    secao(
      'O problema',
      'Nenhuma das três bases é suficiente sozinha, e todas discordam entre si por razões legítimas de **cadência**:',
      tabela(
        ['#', 'Camada', 'Pergunta', 'Cadência'],
        [
          ['1', 'Realidade física — imagem de satélite e visão computacional', 'o ativo existe, e onde?', 'mensal / trimestral'],
          ['2', 'Topologia — BDGD (ANEEL)', 'a que alimentador está conectado?', 'anual'],
          ['3', 'Cadastro — empreendimentos de GD (ANEEL)', 'foi homologado, e quando?', 'diária'],
        ],
      ),
      aviso(
        'nota',
        'A discordância é informação, não ruído',
        'Um ativo homologado ontem **não pode** estar na BDGD, que é anual. Tratar essa ausência como erro de cadastro seria errado; tratá-la como irrelevante também. A matriz de desempate **nomeia** cada combinação e dá a ela um encaminhamento.',
      ),
    ),
    secao(
      'Os quatro KPIs',
      tabela(
        ['KPI', 'Como ler'],
        [
          ['**Unidades avaliadas**', 'tamanho da amostra classificada'],
          ['**Defasagem de sistema**', 'homologadas e ausentes da BDGD; **não é irregularidade**, é a cadência anual da base; entra no fator de correção'],
          ['**Não homologadas**', 'presentes fisicamente e sem registro; escaladas como exceção'],
          ['**Confirmadas**', 'as três camadas concordam; a estimativa pode ser usada sem ressalva'],
        ],
      ),
    ),
    secao(
      'Lógica de desempate',
      tabela(
        ['Classificação', 'Satélite', 'BDGD', 'ANEEL', 'Encaminhamento'],
        [
          ['**CONFIRMADA**', 'sim', 'sim', 'sim', 'usar sem ressalva'],
          ['**LAG_DE_SISTEMA**', 'sim', 'não', 'sim', 'homologada, ausente da base anual: **entra no fator de correção**'],
          ['**NAO_HOMOLOGADA**', 'sim', '—', 'não', 'existe e gera sem registro: **escalada como exceção, nunca somada silenciosamente**'],
          ['**CADASTRO_SEM_EVIDENCIA**', 'não', '—', 'sim', 'registro sem evidência física: instalação pendente, erro de coordenada ou limite do detector'],
          ['**SEM_EVIDENCIA**', 'não', 'não', 'não', 'nada a afirmar'],
        ],
      ),
      'Implementação em `Backend/oraculo/triangulation/evidence.py`, função `classify(detected, in_bdgd, in_aneel)`.',
      aviso(
        'nota',
        'A decisão de projeto mais importante',
        'Separar **defasagem de sistema** de **não homologada**. Somadas, dariam um número maior e sem sentido (atraso administrativo misturado com irregularidade). Separadas, a primeira corrige a estimativa e a segunda vira exceção a tratar.',
      ),
    ),
    secao(
      'Os outros cartões',
      lista(
        '**Três camadas de evidência** — fonte, pergunta, cadência e disponibilidade atual de cada camada.',
        '**Fator de correção por área** — unidades em defasagem e o fator a aplicar sobre a capacidade cadastrada. A capacidade implicada vem do déficit diurno observado na carga; uma razão muito acima de 1 sugere cadastro defasado.',
        '**Amostra de unidades classificadas** — as 40 primeiras, para verificar a lógica em casos concretos em vez de confiar só no agregado.',
      ),
      'A mesma lógica, aplicada à rede real da BDGD do RJ e às detecções do pipeline do time, está em [[auditoria]] e no mapa de [[mapa]].',
    ),
    secao(
      'O que esta tela não afirma',
      aviso(
        'limite',
        'Limites',
        lista(
          'A camada física do protótipo usa a detecção do banco de ensaio (ortoimagem sintética): o detector é real, a imagem é de demonstração. Ver [[visao]].',
          'A classificação **não é fiscalização**: "não homologada" é hipótese a verificar (pode haver erro de coordenada, de detecção ou de recorte temporal).',
          'A amostra exibida é amostra, não censo.',
        ),
      ),
    ),
  ],
}

export const PAGINAS_ANALISE: PaginaDoc[] = [CURTAILMENT, PERFIS, TRIANGULACAO]
