/**
 * Grupo Mapa Inteligente: Perfis por subestação, Visão computacional, Auditoria em 3 camadas,
 * Classes de consumo e Parametrização CLM.
 *
 * Origem: docs/oraculo/documentacao_sphinx/source/modulos/mapa/*.rst, ATUALIZADO para o estado
 * das telas em 2026-09-26 — o mapa do Brasil com a rede real da BDGD no RJ (Mapa.tsx,
 * RedeBdgd.tsx, docs/metodo_espacial.md), a detecção em imagem de satélite real (Visao.tsx,
 * CenaSatelite.tsx) e a auditoria do time (AuditoriaMmgd.tsx, docs/visao_geral_sistema.md §8).
 */
import { aviso, codigo, formula, lista, passos, secao, sub, tabela, type PaginaDoc } from '../modelo'

const GRUPO = 'Mapa Inteligente'

export const MAPA: PaginaDoc = {
  id: 'mapa',
  titulo: 'Perfis por subestação (Mapa Inteligente)',
  grupo: GRUPO,
  resumo: 'Para cada subestação: perfil predominante de consumo e presença de geração distribuída, com a rede real da BDGD no RJ.',
  pergunta: 'Para cada subestação georreferenciada, qual o perfil predominante de consumo da área atendida e existe presença relevante de geração distribuída no entorno?',
  rotas: [
    'GET /api/areas-influencia (rede da BDGD, área piloto RJ)',
    'GET /api/mapa/substations?uf=…',
    'GET /api/mapa/substations/{sub_id}',
    'GET /api/mapa/scene/{sub_id}.png',
  ],
  secoes: [
    secao(
      'O percurso do Mapa Inteligente',
      'São as duas perguntas literais do desafio Radix + AXIA + Cepel, e quatro telas de um mesmo percurso:',
      codigo(
        [
          'subestações (ONS + BDGD)  →  imagem de satélite  →  detecção de painéis',
          '  (Perfis por subestação)                     (Visão computacional / Auditoria)',
          '            └──────────────┬───────────────────────────────┘',
          '                           ▼',
          '              composição de classe da área   (Classes de consumo)',
          '                           ▼',
          '        parâmetros do Modelo de Carga Composta   (Parametrização CLM)',
        ].join('\n'),
      ),
      'O contexto é a perturbação de **15/08/2023** (desligamento da LT 500 kV Quixadá–Fortaleza II, 23.368 MW interrompidos), em que o desempenho dos parques eólicos e fotovoltaicos em campo ficou muito aquém do obtido nos estudos com os modelos dos agentes. A lacuna é de **representação**, por isso o percurso termina em parametrização de modelo.',
    ),
    secao(
      'Como navegar',
      passos(
        'A tela abre no **mapa do Brasil**. Os estados em destaque já têm a análise; clique num estado para aproximar.',
        'No estado aparecem as **subestações de fronteira do ONS** (círculos coloridos pelo nível de MMGD). No **Rio de Janeiro** aparece também a **rede de distribuição da BDGD**: áreas de influência, ícones por classificação da subestação e linhas de alimentação.',
        'Clique numa área ou num ícone da BDGD para o cartão da subestação; clique num círculo (ou numa linha da tabela) para o detalhe da subestação de fronteira do ONS.',
        '`← voltar ao Brasil` sai do estado; `Mapa` / `Satélite` troca o fundo; os chips ligam e desligam camadas (áreas, hierarquia, classificações, fronteira ONS, raio de análise).',
      ),
      tabela(
        ['No mapa', 'Significado'],
        [
          ['violeta (área de influência)', 'mais forte = mais MMGD na área'],
          ['contorno laranja', 'subestação de fronteira com excedente previsto (tracejado nas satélites dela)'],
          ['linha âmbar animada', 'alimentação mãe → satélite (hierarquia da malha AT da BDGD)'],
          ['ícone da subestação', 'classificação: distribuição plena, distribuição satélite, transformadora pura, transporte/manobra'],
          ['círculo', 'subestação de fronteira do ONS, cor pelo nível de MMGD (baixa / média / alta)'],
        ],
      ),
      aviso('limite', 'Cobertura da BDGD', 'Nesta versão só o **Rio de Janeiro** (LIGHT e Enel RJ) tem a rede da BDGD; os demais estados mostram apenas as subestações de fronteira do ONS.'),
    ),
    secao(
      'A rede da BDGD (RJ) — dado real',
      'Vem do recurso `areas_influencia` (`mock: false`): BDGD 2025 da LIGHT e da Enel RJ × cadastro de MMGD da ANEEL, pela pipeline do RDX migrada para `Backend/src/spatial` (método em `docs/metodo_espacial.md`).',
      sub('KPIs do estado'),
      tabela(
        ['KPI', 'Como ler'],
        [
          ['**Áreas de influência**', 'número de subestações da BDGD com polígono, por distribuidora'],
          ['**MMGD na rede**', 'capacidade do cadastro da ANEEL localizada pela BDGD, em MW'],
          ['**Lag de cadastro**', 'MW já homologados na ANEEL e ainda fora da BDGD (base anual)'],
          ['**Com excedente previsto**', 'subestações de fronteira com excedente > 0 nas próximas 24 h, e o total em MW'],
        ],
      ),
      sub('Cartão da subestação da BDGD'),
      'Distribuidora, classificação, subestação mãe (clicável), área de influência em km², código BDGD; capacidade de MMGD, parcela em lag de cadastro, fator de correção do satélite (quando existe) e excedente previsto em 24 h com o horizonte. Lista as subestações que ela alimenta.',
      sub('Como as áreas de influência são construídas'),
      passos(
        'fecho convexo dos transformadores MT/BT da subestação;',
        'onde os fechos se sobrepõem, cada ponto fica com a subestação **mais próxima**;',
        'vazios do estado: absorvidos pela única área vizinha ou divididos por Voronoi;',
        'recorte pelo limite do IBGE e simplificação de 1 m.',
      ),
      'A MMGD por área cruza CEG da BDGD com o cadastro da ANEEL: **a potência vem sempre da ANEEL** (na Enel RJ o `POT_INST` da BDGD é ~5× menor que o cadastro). O que está na ANEEL e ainda não na BDGD (lag de sistema) é rateado entre as áreas da mesma distribuidora no município. Com a BDGD 2025 e o cadastro de 2026-09: **1.908,7 MW** de MMGD, dos quais **293,5 MW** em lag.',
      sub('Excedente'),
      formula('excedente = max(0, geração de MMGD − carga)   por subestação de fronteira e semi-hora'),
      'Geração = capacidade × fator de geração da área RJ (MMGD estimada pelo ONS ÷ capacidade cadastrada). Carga = carga global da área RJ × peso da subestação no mês (energia bruta na BDGD). Previsão para 1 h, 3 h e D+1 por persistência sazonal de 1 dia, com teste de que não usa dado depois do "agora". Conferência: os 3 maiores excedentes previstos estão entre as subestações de origem dos alimentadores com fluxo reverso medido na BDGD.',
    ),
    secao(
      'As subestações de fronteira do ONS (todos os estados)',
      'Entrada real: o conjunto `subestacao` do ONS (1.689 registros, **909** subestações únicas em 27 UF, **522** com transformação de fronteira com a distribuição, secundário ≤ 138 kV em `capacidade-transformacao`).',
      sub('KPIs'),
      tabela(
        ['KPI', 'Como ler'],
        [
          ['**Subestações de fronteira**', 'no estado, e quantas foram analisadas'],
          ['**Classe dominante no estado**', 'classe predominante no conjunto analisado, com a distribuição'],
          ['**Penetração de MMGD**', 'distribuição dos três níveis'],
          ['**MMGD cadastrada nas SEs**', 'soma do cadastro da ANEEL nas SEDs associadas às SEs de fronteira do estado (sem a base real: F1 do detector no banco sintético)'],
        ],
      ),
      sub('Área de influência (sem BDGD)'),
      formula('área_km² = MVA_fronteira / 9        r_km = √(área / π), limitado a [0,8 ; 6,0]'),
      'Dimensionada pela capacidade que **desce** para a distribuição, não pela total. Mediana do raio nas 522: 3,34 km (âncora da escala do alimentador em [[clm]]).',
      sub('Pergunta 1 — perfil de consumo'),
      lista(
        '**Dado real** — energia faturada por classe das subestações de distribuição associadas à SE pela correlação fronteira T–D ([[fronteira]]): BDGD (MT/AT, por unidade consumidora) + SAMP (BT, rateado por município). A "confiança" exibida é a parcela da energia medida por UC.',
        '**Desvio em relação ao subsistema** — distância entre essa composição e a da curva de carga do subsistema decomposta nos perfis canônicos ([[classes]]): onde a área difere da média regional.',
        'SE sem nenhuma SED associada aparece como **Sem dado** — nunca com um número da amostra sintética.',
      ),
      sub('Pergunta 2 — presença de GD'),
      formula('razão = MMGD cadastrada nas SEDs (ANEEL) ÷ carga média da SE        nível = razão ÷ (43,5 GWp ÷ carga média do SIN)'),
      tabela(
        ['Nível', '× a razão do SIN'],
        [
          ['Baixa', '< 0,5'],
          ['Média', '0,5 a 1,5'],
          ['Alta', '> 1,5'],
        ],
      ),
      'Comparar com a carga, e não com a área, deixa SEs de porte diferente comparáveis: nenhuma base pública traz a área efetivamente servida. Sem a base real da fronteira (modo demo ou base em construção), a tela cai para o indicador da amostra sintética abaixo, com o aviso na faixa do topo.',
      sub('Indicador da amostra sintética (só demonstração do detector)'),
      codigo(
        [
          'pixel → lat/lon (geo-transformação local plana)',
          'área conexa × área do pixel          → m² de painel',
          '× calibração de área (1,19, medida)  → m² corrigido',
          '× 200 W/m² de módulo                 → kWp',
          '÷ área amostrada                     → kWp/km² → nível',
        ].join('\n'),
      ),
      tabela(
        ['Nível', 'kWp/km²'],
        [
          ['Baixa', '< 200'],
          ['Média', '200 a 800'],
          ['Alta', '> 800'],
        ],
      ),
      aviso(
        'premissa',
        'Amostragem, não cobertura total',
        'A detecção roda em 2 janelas de 230 m a 0,30 m/pixel (0,106 km²). O **nível usa a densidade medida, sem extrapolação**; só o total absoluto é extrapolado pela fração construída típica (comercial 0,80 · residencial 0,60 · industrial 0,40 · misto 0,55).',
      ),
      sub('Detalhe da subestação de fronteira'),
      lista(
        '**Desempenho do detector nesta amostra** — precisão, revocação, F1 e IoU nesta cena (medições do detector contra a verdade fundamental da ortoimagem sintética). Não entra na composição nem na MMGD.',
        '**Desvio em relação ao subsistema** — composição local × prior regional.',
        '**Insumo proposto ao Modelo de Carga Composta** — composição por classe, fração de motor (residencial 0,22 · comercial 0,38 · industrial 0,62 · rural 0,55), MMGD, sinalização de GD e confiança. **Não são parâmetros prontos para simulação** (campo `aviso`).',
        '**Detecções georreferenciadas** — lat/lon, área e confiança de cada detecção.',
      ),
      'Fecham a tela o **Pipeline replicável** (as etapas, na ordem: com as bases atualizadas, a metodologia reproduz o mapa) e as **Faixas do indicador de MMGD**.',
    ),
    secao(
      'O que esta tela não afirma',
      aviso(
        'limite',
        'Limites',
        lista(
          '**R1** — a cena amostrada das subestações de fronteira é ortoimagem sintética e só demonstra o detector; os números da SE vêm da BDGD e da ANEEL. A detecção em imagem real está em [[visao]].',
          '**R2** — subestação de distribuição exige BDGD: só o RJ tem a rede real.',
          '**R3** — não existe curva de carga por subestação em dado aberto; a decomposição roda por subsistema.',
          '**R4** — a associação SED → SE é inferida (modelo gravitacional, [[fronteira]]); a composição herda essa incerteza.',
          '**R5** — variância de amostragem alta onde as edificações são poucas e grandes (`sample_adequacy`).',
          'Excedente: fator de geração único na área RJ e perfil de carga plano no mês; algumas subestações que exportam na medição não aparecem com excedente na previsão.',
        ),
      ),
    ),
  ],
}

export const VISAO: PaginaDoc = {
  id: 'visao',
  titulo: 'Visão computacional (detector por subestação)',
  grupo: GRUPO,
  resumo: 'O detector de painéis do protótipo: desempenho medido contra verdade fundamental e detecção em imagem de satélite real.',
  pergunta: 'O detector de painéis fotovoltaicos funciona? Com que precisão, medida contra o quê?',
  rotas: ['GET /api/mapa/vision', 'GET /api/mapa/vision/real?lat=&lon=', 'GET /api/mapa/bench.png'],
  secoes: [
    secao(
      'Duas soluções de visão',
      'Esta tela é a solução do **protótipo** (detector clássico por subestação). A solução do time, **YOLOv8-seg + BDGD + ANEEL**, está em [[auditoria]]. Publicar o indicador de MMGD sem publicar o desempenho do detector seria pedir confiança sem oferecer evidência.',
    ),
    secao(
      'Banco de ensaio: os KPIs',
      'Agregados sobre **4 classes urbanas × 3 sementes = 12 cenas** sintéticas com verdade fundamental conhecida.',
      tabela(
        ['KPI', 'Como ler'],
        [
          ['**Precisão**', 'das detecções, quantas eram painel de verdade (precisão baixa = contar telhado ou asfalto como painel)'],
          ['**Revocação**', 'dos painéis existentes, quantos foram encontrados; o rodapé traz o F1'],
          ['**IoU de máscara**', 'sobreposição da máscara detectada com a verdadeira: mede **geometria**; o rodapé traz a AP'],
          ['**Erro de área**', 'erro relativo da área total **após calibração**: é o que importa para o kWp'],
        ],
      ),
      aviso(
        'nota',
        'Por que a AP é bem menor que o F1',
        'O F1 é medido no ponto de operação escolhido; a *average precision* integra toda a curva precisão × revocação. A diferença indica que o detector é bom **no limiar calibrado** e degrada fora dele, e é por isso que a curva está na tela.',
      ),
    ),
    secao(
      'Detecção em imagem de satélite real',
      'O cartão principal abre em **Imagem real (satélite)**: o backend baixa a imagem Esri World Imagery do ponto (zoom 19, ~0,28 m/pixel), roda o **mesmo** detector do banco de ensaio e devolve cada painel com o polígono em lat/lon.',
      lista(
        '**clique no mapa** para analisar outro local; `voltar ao ponto de referência` retorna ao centro da cena;',
        'painel = bounding box só com contorno; o selecionado fica com borda âmbar grossa; a tabela abaixo do mapa seleciona e localiza;',
        'a dica mostra quantos painéis e quantos kWp foram detectados; a nota traz a fonte da imagem, o zoom, o GSD e a atribuição;',
        '`cena` / `entorno` alterna o enquadramento; a roda do mouse dá zoom.',
      ),
      aviso(
        'limite',
        'Em imagem real não há verdade fundamental',
        'Os painéis detectados numa imagem real não têm gabarito: não há precisão nem revocação medidas ali. As métricas desta tela são do banco de ensaio sintético e são um **teto**; em imagem real, esperar degradação. O aviso também vem no payload.',
      ),
      'Em **Imagem sintética (banco de ensaio)** a cena de referência aparece sobreposta ao satélite, com vistas alternáveis: detecções, verdade fundamental + ladrilhos + falsos negativos (carmim), e os canais de característica (excesso de azul, densidade de borda, luminância) que mostram *por que* o detector decidiu.',
    ),
    secao(
      'Backends de detecção',
      tabela(
        ['Backend', 'Implementação'],
        [
          ['**Detector clássico**', 'índice espectral de excesso de azul + luminância (suavizados), densidade de borda por Sobel, morfologia binária, componentes conexas, filtro de forma, refinamento em duas etapas'],
          ['**YOLOv8-seg**', 'letterbox e inversa, decodificação das saídas, NMS, recorte de máscara por protótipos, transformação de coordenadas; ativo só com runtime e pesos'],
        ],
      ),
      'O cartão mostra o estado de cada backend como a API o declara (`available` e o motivo). Sem runtime, o adaptador YOLO cede o lugar ao clássico; ladrilhamento, NMS, deduplicação na costura e georreferência são compartilhados.',
      sub('Etapas do detector ativo'),
      passos(
        'índices espectrais (excesso de azul e luminância), suavizados em 5 px;',
        'densidade de borda (Sobel), normalizada pelo tamanho físico do módulo;',
        'limiarização conjunta dos três canais;',
        'morfologia binária — fechamento **antes** da abertura;',
        'componentes conexas e filtro de forma (retangularidade, razão de aspecto, área mínima e máxima);',
        'refinamento em duas etapas, relaxando o limiar na vizinhança da detecção;',
        'NMS e deduplicação na costura entre ladrilhos, por IoU e contenção;',
        'geo-transformação de pixel para lat/lon.',
      ),
      aviso(
        'medido',
        'Duas correções que definiram os parâmetros',
        'O detector marcava a **malha viária inteira** (precisão 0,33): o excesso de azul do asfalto (0,021) passava do limiar arbitrado (0,012). Recalibrado para 0,090 e luminância máxima 74. Depois, a **revocação despencou para 0,17**: as juntas entre módulos fragmentavam a máscara. Corrigido suavizando os índices em 5 px e reordenando a morfologia.',
      ),
    ),
    secao(
      'Curva, tabela por classe e calibração',
      lista(
        '**Curva precisão × revocação** — varredura do limiar de confiança na cena de referência.',
        '**Desempenho por classe urbana e semente** — as 12 cenas, uma por linha. A média esconde o pior caso; as linhas mostram que o viés de área é **sistemático entre classes**, o que autoriza corrigi-lo por constante.',
        '**Calibração de área** — erro bruto de −15,4%, fator **1,19**, erro calibrado de +0,7%. A borda do painel é um gradiente e qualquer limiar corta parte dela. O valor bruto continua na API e o teste exige erro calibrado abaixo de 8%.',
        '**Parâmetros do YOLOv8-seg** — dimensão de entrada, `nc`, `nm`, limiares de confiança e de NMS.',
      ),
      aviso(
        'medido',
        'Um erro de decodificação que o teste pegou',
        'A decodificação do YOLO retornava zero caixas: a heurística `arr.shape[0] < arr.shape[1]` para a orientação do tensor falha com poucas âncoras. Substituída pela verificação determinística `expected_c = 4 + nc + nm`.',
      ),
    ),
    secao(
      'O que esta tela não afirma',
      aviso(
        'limite',
        'Limites',
        lista(
          '**R1** — as métricas são do banco de ensaio sintético: um teto, não promessa de campo.',
          '**R6** — a calibração de área foi medida em imagem sintética; precisa ser remedida contra conjunto rotulado real.',
          'O detector encontra **painel em telhado**: não classifica tecnologia, não estima orientação, inclinação nem sombreamento.',
          'O fundo de satélite (Esri) é o único serviço externo além do OpenStreetMap; sem rede, o mapa avisa.',
        ),
      ),
    ),
  ],
}

export const AUDITORIA: PaginaDoc = {
  id: 'auditoria',
  titulo: 'Auditoria da MMGD em 3 camadas',
  grupo: GRUPO,
  resumo: 'Painéis detectados em satélite (YOLOv8-seg) × BDGD × cadastro ANEEL: desempate e fator de correção por área.',
  pergunta: 'Quanto da MMGD que existe fisicamente está na BDGD e no cadastro da ANEEL, e qual o fator que corrige a capacidade cadastrada?',
  rotas: ['GET /api/auditoria/mmgd'],
  secoes: [
    secao(
      'A solução de visão do time',
      'Pipeline em `Backend/pipeline/auditoria_camada1.py` e `auditoria_camadas_2_3.py`, parâmetros em `Backend/config/visao.yaml`. A rota **só lê** as saídas do pipeline; rodar o modelo é trabalho do pipeline (extra `[visao]`: ultralytics + earthengine-api).',
      tabela(
        ['Camada', 'Pergunta', 'Fonte', 'Cadência'],
        [
          ['1 · realidade física', 'o painel existe e onde está?', 'imagem de satélite + YOLOv8-seg', 'periódica'],
          ['2 · topologia', 'a que alimentador/transformador está ligado?', 'BDGD', 'anual'],
          ['3 · cadastro', 'foi homologado, e quando?', 'cadastro de GD da ANEEL', 'diária'],
        ],
      ),
    ),
    secao(
      'Os KPIs',
      tabela(
        ['KPI', 'Como ler'],
        [
          ['**Painéis detectados (Camada 1)**', 'contagem, área total em m² e origem (modelo ou mock)'],
          ['**Capacidade auditada**', 'área × kWp/m² (premissa de `visao.yaml`), **sem** as não homologadas'],
          ['**Capacidade na BDGD**', 'o cadastrado nas áreas, e o fator agregado auditada ÷ BDGD'],
          ['**Exceções não homologadas**', 'detecções sem BDGD nem ANEEL, escaladas'],
        ],
      ),
    ),
    secao(
      'O desempate (camadas 2 e 3)',
      'Cada painel detectado é casado com o cadastro por distância (raio na dica do cartão, um para um) e classificado:',
      tabela(
        ['Classe', 'Regra', 'Entra no fator?'],
        [
          ['**Cadastrada**', 'casou com unidade com GD na BDGD', 'sim'],
          ['**Lag de Sistema**', 'fora da BDGD, homologado na ANEEL **depois** da data de referência da BDGD: o ciclo anual ainda não absorveu', 'sim'],
          ['**Divergência cadastral**', 'fora da BDGD, homologado **antes**: divergência entre bases, vai para revisão', 'sim'],
          ['**Não homologada**', 'nem BDGD nem ANEEL: exceção escalada, **nunca** incorporada em silêncio', 'não'],
        ],
      ),
      formula('fator de correção (por área) = capacidade auditada ÷ capacidade cadastrada na BDGD'),
      'O cartão **Fator de correção por mancha** traz, por área: BDGD (kW), auditada (kWp), fator (ou o motivo de não haver), capacidade não homologada, contagem por classe e as unidades da BDGD sem detecção.',
    ),
    secao(
      'Os cartões',
      lista(
        '**Camada 1 · painéis detectados** — polígonos coloridos pela classificação; clique para ver o desempate daquele painel. Fundo OpenStreetMap ou esquemático.',
        '**Desempate BDGD × ANEEL** — as quatro classes com contagem e explicação; a dica traz as datas da BDGD e da extração da ANEEL.',
        '**Detecções** — id, classe, área, m², kWp e confiança; clique para selecionar.',
        '**Modelo, imagem e reprodução** — caminho dos pesos (presente ou ausente), confiança mínima, GSD máximo aceito, coleção e janela de satélite, bounding box da área piloto e quando foi gerado.',
      ),
    ),
    secao(
      'Estado atual',
      aviso(
        'limite',
        'Quando a tela mostra DADOS MOCK',
        'Sem imagem da área piloto nem pesos do modelo na máquina, a Camada 1 usa painéis sintéticos declarados à mão (`pipeline/mock/`), que passam pela mesma geometria do modo real, e a tela exibe a faixa **DADOS MOCK**: nenhum número é medição.',
      ),
      aviso(
        'limite',
        'Modelo e imagem',
        'O modelo configurado é uma versão antiga do treinamento do time (YOLOv8s-seg), ainda sem ajuste com imagens da área piloto; a validação (`validar_modelo.py`) só o declara adequado com um gabarito da área. Sentinel-2 (10 m) não enxerga painel residencial: é preciso imagem submétrica. O fator ainda **não é consumido** pelos modelos de carga.',
      ),
      'O desempate equivalente sobre a rede **real** da BDGD do RJ (sem a camada de satélite) já roda na espacialização e aparece no mapa de [[mapa]] como **lag de cadastro**.',
    ),
  ],
}

export const CLASSES: PaginaDoc = {
  id: 'classes',
  titulo: 'Classes de consumo e assinatura da curva',
  grupo: GRUPO,
  resumo: 'Perfis horários MEDIDOS por classe (ANEEL CTR), composição real de cada subsistema pela energia faturada (BDGD + SAMP) e validação contra a curva de carga do ONS.',
  pergunta: 'Como cada classe de consumo usa energia ao longo do dia, quanto cada classe pesa em cada subsistema, e isso explica a curva que o ONS observa?',
  rotas: ['GET /api/mapa/classes'],
  secoes: [
    secao(
      'Três peças, todas de dado real',
      tabela(
        ['Peça', 'Fonte', 'O que dá'],
        [
          ['**Forma**', 'ANEEL · CTR – Curva de Carga Consumidor Tipo', 'curva de 15 min de cada classe, medida nas campanhas das revisões tarifárias (dia útil, sábado, domingo)'],
          ['**Composição**', 'BDGD (UCMT/UCAT por SED) + SAMP (BT por distribuidora), via [[fronteira]]', 'energia faturada por classe em cada subsistema'],
          ['**Validação**', 'ONS · carga global do subsistema', 'a curva real contra a qual a curva montada é comparada'],
        ],
      ),
      formula('curva_montada(h) = Σ_c  e_c · forma_c(h),     e_c = energia de dia útil da classe c'),
      'A energia é anual; a forma é de dia útil. O peso de cada classe no dia útil é corrigido pelo fim de semana MEDIDO dela: e_c ∝ energia_c / (5 + sábado_c + domingo_c). A razão domingo/dia útil montada sai da mesma conta.',
      aviso(
        'medido',
        'A curva do ONS deixou de ser a fonte da composição',
        'Antes, a composição era adivinhada encaixando a curva do ONS em perfis desenhados à mão (NNLS). Agora a composição vem da energia faturada e a curva do ONS só **valida**: se a curva montada bate com a observada, composição e formas se confirmam uma à outra.',
      ),
    ),
    secao(
      'As classes seguem o que a ANEEL mede',
      tabela(
        ['Classe', 'Subgrupos', 'Assinatura medida'],
        [
          ['**Residencial**', 'B1', 'ponta às 19h, vale de madrugada; domingo ≈ dia útil'],
          ['**Rural**', 'B2', 'pico também às 19h — o "bombeamento de madrugada" dos perfis antigos não aparece'],
          ['**Comercial, serviços e demais BT**', 'B3', 'platô 9h–16h, domingo ~0,70 do dia útil'],
          ['**Média tensão**', 'A4, AS', 'platô diurno, domingo ~0,64'],
          ['**Alta tensão**', 'A1, A2, A3, A3a', 'quase plana; grande indústria'],
        ],
      ),
      aviso(
        'premissa',
        'Por que não "comercial × industrial"',
        'A ANEEL mede por subgrupo tarifário. O B3 junta comércio, serviços e pequena indústria de BT; separá-los exigiria um critério que o dado não traz. A indústria aparece pela tensão (MT e AT).',
      ),
    ),
    secao(
      'Como os perfis são calculados',
      lista(
        'Só o processo tarifário **mais recente** de cada distribuidora (campanhas de 2016 a 2026).',
        'Cada curva vira p.u. da **sua própria** média de dia útil; o perfil da classe é a média simples das curvas. O arquivo não diz quantos consumidores cada curva representa, então não há peso honesto a aplicar.',
        'Domingo do CTR = dia-tipo domingo/feriado do projeto.',
        'Parâmetros em `Backend/config/perfis_classe.yaml`; código em `Backend/oraculo/profiles/medidos.py`.',
      ),
    ),
    secao(
      'Os cartões',
      lista(
        '**Perfis medidos por classe** — dia útil em p.u.; **Fim de semana e amostra** — sábado e domingo relativos, número de curvas, distribuidoras e anos.',
        '**Cartões por subsistema** — carga global do ONS × curva montada, R², qualidade e cobertura; barras da composição.',
        '**Composição por subsistema** — participações, GWh/ano, cobertura, SED mista, R² e domingo/dia útil observado × montado.',
        '**Limiares de área de telhado** — rotulado **PREMISSA**: é da evidência morfológica de [[mapa]], não é medição.',
      ),
      aviso(
        'nota',
        'Por que comparar com a carga GLOBAL',
        'O CTR mede consumo. A carga supervisionada do ONS desconta a MMGD, o que achata o meio-dia; comparar com ela faria a curva montada "errar" por um efeito que não é de classe. Com a carga global, o R² sobe de 0,57 para 0,93 no Sul e de 0,32 para 0,77 no Sudeste.',
      ),
    ),
    secao(
      'Quando não valida',
      'A **cobertura** é a energia da distribuição associada às SEs de fronteira dividida pela energia do ONS. No Norte ela é ~39% e no Nordeste ~62%: o restante são consumidores ligados direto na rede básica (eletrointensivos) e perdas, carga quase plana que não está na composição. Ali a curva montada sai mais ondulada que a observada e o R² é negativo — e a tela diz isso em vez de ajustar pesos para esconder.',
      aviso(
        'limite',
        'Limites',
        lista(
          'Perfis nacionais: o CTR não traz subsistema, e mapear distribuidora → subsistema pelas siglas antigas do arquivo seria frágil.',
          'SEDs com UCs de MT e de AT: a base agregada não separa a energia; vai toda para a MT e a fração aparece na tabela.',
          'Iluminação pública (B4) não é classe própria: no SAMP ela já soma na comercial.',
          'Composição vem da base da [[fronteira]]; no modo demonstrativo ou com a base em construção, não é mostrada.',
          'O prior regional de [[mapa]] (desvio da SE em relação ao subsistema) ainda usa a decomposição NNLS sobre os perfis estilizados de `classes.py`.',
        ),
      ),
    ),
  ],
}

export const CLM: PaginaDoc = {
  id: 'clm',
  titulo: 'Parametrização do Modelo de Carga Composta',
  grupo: GRUPO,
  resumo: 'CMPLDW segundo a especificação do WECC: estrutura, equações e cartão de 124 parâmetros com procedência campo a campo.',
  pergunta: 'Que parâmetros usar no Modelo de Carga Composta para esta subestação — e em quais deles é possível confiar?',
  rotas: ['GET /api/clm/spec', 'GET /api/clm/cartao', 'GET /api/clm/curvas', 'GET /api/clm/validacao'],
  secoes: [
    secao(
      'Destino e fontes',
      'Destino: **parametrização do CLM no ORGANON**. O cartão é **neutro**, porque os campos do CMPLDW são os mesmos em PSS/E (`CMLDxxU2`), PSLF (`cmpldw`), PowerWorld, DSATools e ORGANON.',
      tabela(
        ['Rótulo', 'Fonte'],
        [
          ['**WECC**', '*WECC Composite Load Model Specification*, MVS, abril de 2021: estrutura, campos, equações, o exemplo resolvido e os números que o texto fixa'],
          ['**REF**', 'Huang, Jin, Diao, Palmer et al., *A Reference Implementation of WECC Composite Load Model in Matlab and GridPACK*, arXiv:1708.00939: todo valor numérico de referência'],
        ],
      ),
      aviso(
        'nota',
        'Nenhum número sem procedência',
        'O CMPLDW tem mais de cem campos e quase nenhum é observável a partir de dado aberto — exatamente onde a tentação de inventar é maior. Rótulos: **derivado**, **premissa**, **WECC**/**referência** e **a calibrar** (não afirmado).',
      ),
    ),
    secao(
      'Os quatro KPIs',
      tabela(
        ['KPI', 'Valor', 'Como ler'],
        [
          ['**Campos do modelo**', '124', 'tamanho do registro completo do CMPLDW'],
          ['**Derivados de dado nosso**', '5 a 6', 'as cinco frações e, com subestação real, a base MVA'],
          ['**Premissa versionada**', '2', '`Rfdr` e `Xfdr`, escalados pelo comprimento equivalente'],
          ['**A calibrar**', '29', '**não afirmados**: o número mais honesto da tela'],
        ],
      ),
      'Dado aberto brasileiro não determina nem um quinto do CMPLDW. A tela existe para deixar essa fronteira explícita.',
    ),
    secao(
      'Estrutura do modelo',
      codigo(
        [
          'Barramento          Barramento              Barramento',
          'do sistema           de baixa                de carga',
          '    │                   │                       │',
          '    ├── jXxf, 1:T ──────┤── Rfdr + jXfdr ───────┤── M  Motor A   3φ',
          '    │     (LTC)         │                       │── M  Motor B   3φ',
          '    │                   ⊥ Bss                   │── M  Motor C   3φ',
          '    │                   ⊥ Fb·Bfdr  (1−Fb)·Bfdr ⊥│── M  Motor D   1φ',
          '    │                                           │── ▭  Eletrônica',
          '  UVLS                                          │── ▭  Estática',
          '  UFLS                                          └── Pdg + jQdg (MMGD)',
        ].join('\n'),
      ),
      'Os barramentos de baixa e de carga não existem no fluxo de potência: são criados na inicialização. Metade do efeito dinâmico vem da **rede entre** a transmissão e o uso final — é a impedância que faz a tensão no uso final cair mais que a medida na subestação e leva o compressor a travar. As ferramentas reajustam `Rfdr`/`Xfdr` para manter o barramento de carga acima de 0,95 pu.',
    ),
    secao(
      'Composição da carga',
      'Seletor de subestação (as 522 de fronteira) ou composição livre, mais o cursor do motor D. Também recebe a composição pela BDGD enviada da tela [[fronteira]] (`fonte=bdgd`).',
      tabela(
        ['Classe', 'Fma', 'Fmb', 'Fmc', 'Fmd', 'Fel', 'estática', 'motora'],
        [
          ['Residencial', '0,05', '0,03', '0,02', '**0,12**', '0,20', '0,58', '0,22'],
          ['Comercial', '0,12', '0,10', '0,06', '0,10', '0,22', '0,40', '0,38'],
          ['Industrial', '0,20', '0,12', '**0,28**', '0,02', '0,10', '0,28', '0,62'],
          ['Rural', '0,06', '0,04', '**0,43**', '0,02', '0,08', '0,37', '0,55'],
        ],
      ),
      lista(
        '**Residencial** — motor pequeno e quase todo monofásico (compressor de geladeira e ar-condicionado = motor D); eletrônica alta; chuveiro é parcela relevante e puramente estática.',
        '**Comercial** — climatização central reparte entre compressores (A) e ventilação (B).',
        '**Industrial** — bombas e alta inércia (C), pouca carga monofásica.',
        '**Rural** — irrigação e bombeamento, quase tudo C.',
      ),
      aviso('medido', 'A coluna "motora" não é coincidência', 'Reproduz exatamente a fração motora que [[mapa]] publica; há teste que exige desvio zero.'),
      aviso(
        'premissa',
        'O cursor do motor D',
        'A penetração de ar-condicionado no Brasil não é a do sudoeste norte-americano de onde vem o modelo do motor D, e o motor D governa a recuperação lenta de tensão. O cursor escala `Fmd` e devolve o delta à carga estática (a soma continua 1, com teste). Expor a sensibilidade é mais honesto que fixar um número que não temos.',
      ),
    ),
    secao(
      'Contexto, aplicabilidade e escala do alimentador',
      tabela(
        ['Critério de aplicabilidade', 'Limite'],
        [
          ['Carga', '> 5 MW'],
          ['Tensão', '> 0,98 pu'],
          ['Relação P/Q', '> 1,61'],
        ],
      ),
      'Abaixo desses valores a inicialização falha; a tela diz **qual** critério reprovou.',
      formula('escala = r_km / 3,34  (limitada a [0,35 ; 2,20])        Rfdr = Xfdr = 0,04 × escala'),
      'O raio de influência é o único proxy de comprimento em dado aberto; a subestação mediana recebe exatamente o valor de referência.',
    ),
    secao(
      'Cartão de parâmetros e componentes',
      'Os 124 campos, navegáveis por bloco (transformador, alimentador, frações, estática, eletrônica, quatro motores): valor sugerido, referência, unidade, **procedência** e significado.',
      tabela(
        ['Motor', 'H', 'Etrq', 'Desligamento por subtensão', 'Leitura convencional'],
        [
          ['A', '0,3 s', '0 — conjugado constante', 'não', 'compressores'],
          ['B', '0,5 s', '2 — ∝ velocidade²', '0,80 pu / 2 s · 0,60 pu / 0,16 s', 'ventiladores'],
          ['C', '1,0 s', '2 — ∝ velocidade²', 'idem B', 'bombas, alta inércia'],
        ],
      ),
      'Não existe campo "tipo de equipamento": a diferença entre A, B e C está inteiramente em `H` e `Etrq`. A leitura de equipamento é a convencional da literatura, rotulada como tal.',
      sub('Carga estática'),
      formula('P = Po · (P1c·V^P1e + P2c·V^P2e + P3) · (1 + Pfrq·Δf),     P3 = 1 − P1c − P2c'),
      'Em V = 1 e Δf = 0 o fator é exatamente 1; senão o CLM deslocaria o ponto de operação na inicialização. Há teste.',
      sub('Motor D — compressor monofásico'),
      formula(
        [
          'V > 0,86:            P = Po·(1 + Δf)                        Q = [Q\'o + 6·(V − 0,86)²]·(1 − 3,3·Δf)',
          'V\'stall < V < 0,86:  P = [Po + 12·(0,86 − V)^3,2]·(1 + Δf)   Q = [Q\'o + 11·(0,86 − V)^2,5]·(1 − 3,3·Δf)',
          'V < V\'stall:         P = Gstall·V²                           Q = −Bstall·V²',
        ].join('\n'),
      ),
      '`Vstallbrk` é onde a curva de rotor bloqueado cruza a de regime. Implementamos o laço publicado pela especificação **e** uma bissecção independente, exigindo que concordem dentro de um passo (referência: laço 0,5500 pu, bissecção 0,544942 pu). Se `Vstall` < `Vstallbrk`, o compressor trava antes de a curva de regime encontrar a de rotor bloqueado; travado, absorve reativo e **retém a tensão deprimida** depois da falta.',
      sub('Carga eletrônica e proteções'),
      'A variável interna `Vmin` guarda a menor tensão já vista: com `Frcel = 0`, a carga desligada não volta sozinha (descida ≠ subida). A varredura começa no topo, porque o modelo tem memória. Proteção térmica unitária até `Th1t` e decrescente até `Th2t`; contatores com histerese `Vc1off`/`Vc2off` na descida e `Vc2on`/`Vc1on` na subida.',
    ),
    secao(
      'O que prova que a implementação está correta',
      'A especificação resolve um exemplo de 100 MW e publica a tabela de resultado. A tela reproduz as 12 comparações com **desvio máximo 0,0**:',
      tabela(
        ['Componente', 'MW', 'Mvar', 'B calc.', 'B publ.', 'rem. calc.', 'rem. publ.'],
        [
          ['Motor A', '40', '9', '0,1440', '0,144', '0,0288', '0,0288'],
          ['Motor B', '20', '6', '0,0720', '0,072', '0,0504', '0,0504'],
          ['Motor C', '5', '4', '0,0180', '0,018', '0,0072', '0,0072'],
          ['Motor D', '15', '1', '0,0540', '0,054', '0,0540', '0,0540'],
          ['Eletrônica', '10', '−2', '0,0360', '0,036', '0,0288', '0,0288'],
          ['Estática', '10', '−2', '0,0360', '0,036', '0,0360', '0,0360'],
          ['**total**', '100', '16', '**0,3600**', '0,360', '**0,2052**', '0,2052'],
        ],
      ),
      aviso(
        'medido',
        'Um detalhe que quase virou erro',
        'Os reativos extras do exemplo são −36 Mvar, e a soma dos reativos dos componentes é +16: o montante vem do balanço de rede da inicialização. A primeira versão derivava um do outro; o teste `test_reativos_extras_nao_sao_a_soma_dos_componentes` impede a volta.',
      ),
      'Também na tela: conferências independentes (fator 1,000000 da estática em 1 pu, laço × bissecção, normalização das frações, admitância de rotor bloqueado), coerência com o Mapa Inteligente, a MMGD como injeção `Pdg + jQdg` e o **cartão em texto**, neutro de propósito, com a procedência em cada linha.',
    ),
    secao(
      'O que esta tela não afirma',
      aviso(
        'limite',
        'Limites',
        lista(
          '**C1** — nada simula o CLM no tempo; a resposta transitória é do ORGANON.',
          '**C2** — a composição por classe é premissa versionada.',
          '**C3** — 29 campos não são afirmados.',
          '**C4** — a penetração de ar-condicionado brasileira é desconhecida aqui.',
          '**C5** — `Rfdr`/`Xfdr` saem de um proxy de comprimento.',
          '**C7** — o CMPLDW não representa dinâmica de inversor (exige DER_A em paralelo).',
          '**C8** — o cartão não é caso pronto para simulação.',
        ),
      ),
      'Próximos passos: guia de composição da NERC, Pesquisa de Posse e Hábitos, BDGD para `Rfdr`/`Xfdr` reais, oscilografia da perturbação de 15/08/2023 e DER_A em paralelo.',
    ),
  ],
}

export const PAGINAS_MAPA: PaginaDoc[] = [MAPA, VISAO, AUDITORIA, CLASSES, CLM]
