/**
 * Grupo "Dashboard do contrato": as oito telas que leem a publicação do run_heavywork.py pela API
 * de Backend/src/api (formato do contrato, docs/schema_contrato.json). Estas telas não tinham
 * página na documentação Sphinx; o texto vem de docs/visao_geral_sistema.md (§5–§7),
 * docs/real_vs_mock.md, docs/metodo_espacial.md e dos comentários de cabeçalho de src/pages/*.tsx.
 *
 * Situação real × mock de cada recurso: escrita UMA vez em SITUACAO_RECURSOS e reusada nas
 * páginas (atualizar aqui quando docs/real_vs_mock.md mudar).
 */
import { aviso, formula, lista, passos, secao, tabela, type PaginaDoc } from '../modelo'
import { CODIGOS_RAZAO } from './analise'

const GRUPO = 'Dashboard do contrato'

/** Rota → situação, conforme docs/real_vs_mock.md (2026-09-26). */
const SITUACAO_RECURSOS: Record<string, [string, string]> = {
  carga: ['`GET /api/carga/snapshot`', '**real** — carga e MMGD do ONS na última semi-hora com os 4 subsistemas completos, capacidade da ANEEL até a data'],
  previsao: ['`GET /api/previsao`', 'pontos P10/P50/P90 e rampa **reais** (previsões fora da amostra); fatores climáticos **reais** (Open-Meteo, ECMWF IFS, média das UFs ponderada pela MMGD)'],
  riscos: ['`GET /api/riscos`', 'usina, razão, probabilidade, montante, severidade e ação **reais**; `distribuidora` = ponto de conexão publicado pelo ONS; posição = coordenada do SIGA/ANEEL (a usina sem coordenada no SIGA, ~18%, fica na sede da UF)'],
  alertas: ['`GET /api/alertas/{id}`', '**real** — mesmo classificador; SHAP exato do LightGBM agrupado em rótulos legíveis'],
  excedentes: ['`GET /api/excedentes`', '**real (estimativa)** — excedente previsto por subestação de fronteira do RJ (BDGD × ANEEL × carga da área RJ)'],
  densidade: ['`GET /api/mmgd/densidade`', '**real** — capacidade de MMGD por área de influência do RJ; fora do RJ o calor fica vazio'],
  areas: ['`GET /api/areas-influencia`', '**real** — polígonos das áreas de influência (BDGD 2025) com MMGD e excedente'],
  validacao: ['`GET /api/validacao`', '**real** — backtest fora da amostra (SIN, D+1), histórico diário, metadados do treino e status das fontes'],
}

/** Seção "Dados e situação" de uma tela, com as rotas que ela usa. */
const situacao = (...chaves: (keyof typeof SITUACAO_RECURSOS)[]) =>
  secao(
    'Dados e situação',
    tabela(
      ['Rota', 'Situação'],
      chaves.map((k) => SITUACAO_RECURSOS[k]),
    ),
    'Todos os recursos vêm da última publicação do `run_heavywork.py` no banco. Sem banco publicado, a API responde 503 com a instrução para rodar `python run_heavywork.py`.',
  )

export const VISAO_GERAL: PaginaDoc = {
  id: 'visao-geral',
  titulo: 'Visão Geral',
  grupo: GRUPO,
  resumo: 'Panorama do SIN: KPIs de carga, risco de curtailment, curva D+1 e alertas ativos.',
  pergunta: 'Qual o estado do sistema agora e o que exige atenção nas próximas horas?',
  rotas: ['GET /api/carga/snapshot', 'GET /api/previsao', 'GET /api/riscos'],
  secoes: [
    secao(
      'O que a tela mostra',
      lista(
        '**Carga supervisionada** e **MMGD estimada** — o retrato do "agora" publicado.',
        '**Risco de curtailment** — risco agregado das usinas, média das probabilidades ponderada pelo montante (MW).',
        '**Montante em risco** — soma do corte esperado das usinas listadas.',
        '**Carga supervisionada prevista · D+1 · P10/P50/P90** — com os patamares destacados.',
        '**Composição da carga global** — supervisionada + MMGD.',
        '**Alertas ativos** — coluna à direita; cada alerta abre o [[detalhe-alerta]].',
      ),
      aviso(
        'nota',
        'Só o que existe em fonte do projeto',
        'O protótipo de design também mostrava frequência do SIN, margem até o mínimo técnico e ciclo DESSEM. Esses números não existem em nenhuma fonte do projeto e por isso **não aparecem** (regra "nunca inventar dados").',
      ),
      aviso(
        'limite',
        'Limiares de severidade diferentes',
        'O KPI agregado usa limiares de 25/50/75% (`src/data/derivados.ts`); a lista de riscos usa os do Backend (40/60/80%). O mesmo valor pode aparecer como "Alto" no KPI e "Médio" na lista. Unificar está nas pendências.',
      ),
    ),
    secao(
      'Filtros de severidade (topbar)',
      'NORMAL / LOADING / CRITICAL / NO-RISK escondem itens nas **listas** (alto e crítico ficam sob CRITICAL), e cada tela diz quantos ficaram ocultos. Os KPIs de sistema não são filtrados.',
    ),
    situacao('carga', 'previsao', 'riscos'),
  ],
}

export const MAPA_HIBRIDO: PaginaDoc = {
  id: 'mapa-hibrido',
  titulo: 'Mapa Híbrido',
  grupo: GRUPO,
  resumo: 'Usinas em risco, excedentes TSO-DSO, áreas de influência e densidade de MMGD sobre o Brasil.',
  pergunta: 'Onde estão, no território, as usinas em risco de corte, os excedentes da distribuição e a MMGD?',
  rotas: ['GET /api/riscos', 'GET /api/excedentes', 'GET /api/areas-influencia', 'GET /api/mmgd/densidade'],
  secoes: [
    secao(
      'Camadas',
      tabela(
        ['Camada', 'Leitura'],
        [
          ['usinas (círculos)', 'cor = severidade, tamanho = MW esperado de corte; usinas com a mesma coordenada aparecem em anel ligadas ao ponto real'],
          ['excedentes (losangos)', 'cor = prioridade do excedente TSO-DSO'],
          ['áreas de influência', 'polígonos da área piloto (RJ): violeta mais forte = mais MMGD; contorno laranja = subestação de fronteira com excedente previsto, tracejado nas satélites'],
          ['densidade de MMGD', 'mapa de calor opcional (só RJ com dado real)'],
        ],
      ),
    ),
    secao(
      'Interação',
      lista(
        'clicar num marcador ou num item do painel **seleciona**: zoom no item e cartão de detalhe, com botões para o [[detalhe-alerta]] ou os [[excedentes]]; `Esc` limpa a seleção;',
        'a seleção fica na URL (`?sel=risco:<id>`): "ver no mapa" nas outras telas abre o mapa já focado, e o link pode ser compartilhado;',
        'passar o mouse numa UF mostra o resumo; clicar dá zoom e filtra o painel pela UF;',
        'filtros de razão e horizonte (usinas) e os de severidade da topbar valem para mapa e painel;',
        '**Enquadrar** ajusta o zoom a tudo que está visível; **Área piloto** enquadra as áreas de influência; **Brasil** volta à vista inicial.',
      ),
      aviso(
        'nota',
        'Fundo 100% local',
        'Contorno do Brasil (Natural Earth) e divisas das UFs (IBGE) estão no próprio pacote: o mapa funciona offline e na rede do ONS. Um teste impede a volta de camada de tiles remota.',
      ),
      aviso('limite', 'Posição das usinas', 'A posição vem do **SIGA/ANEEL** (média das usinas do conjunto, ponderada pela potência). Cerca de 18% das usinas não têm coordenada no SIGA: essas ficam na **sede da UF**.'),
    ),
    situacao('riscos', 'excedentes', 'areas', 'densidade'),
  ],
}

export const DESPACHO_PREDITIVO: PaginaDoc = {
  id: 'despacho-preditivo',
  titulo: 'Despacho Preditivo',
  grupo: GRUPO,
  resumo: 'Previsão da carga supervisionada (P10/P50/P90) nos horizontes 30 min, 3 h e D+1 — o produto do Desafio 2.',
  pergunta: 'Qual será a carga supervisionada, com que incerteza, e onde estão a rampa e os patamares críticos?',
  rotas: ['GET /api/carga/snapshot', 'GET /api/previsao'],
  secoes: [
    secao(
      'Decompor, projetar, quantificar incerteza',
      passos(
        '**Decompor** — a equação com o snapshot real: carga global − MMGD = carga supervisionada.',
        '**Projetar** — a curva P50 por horizonte, com a rampa e os patamares destacados.',
        '**Quantificar incerteza** — a banda P10–P90.',
      ),
      formula('carga supervisionada = carga global − MMGD estimada   (30 min, por subsistema e SIN)'),
    ),
    secao(
      'O modelo',
      lista(
        'Séries SE, S, NE, N e **SIN** (modelado direto: soma de quantis de subsistemas não é quantil do SIN).',
        'Um modelo **direto** por série × horizonte × quantil (30 min, 3 h e D+1 = 1, 6 e 48 passos).',
        'Entradas: defasagens da carga supervisionada e da MMGD **conhecidas na emissão**, médias móveis e calendário do alvo. Sem meteorologia por enquanto.',
        'LightGBM quantílico que aprende o **desvio** em relação a uma referência (persistência no 30 min; mesmo horário do dia anterior no 3 h e D+1). Banda calibrada por conformal (CQR) com os últimos 182 dias do treino.',
        'Split cronológico: treino com alvos de mar/2019 a jun/2025; teste com emissões de jul/2025 a set/2026. Baselines: persistência, sazonal e climatologia.',
      ),
      tabela(
        ['Horizonte (SIN)', 'MAE LightGBM', 'Melhor baseline', 'MAPE', 'Cobertura P10–P90'],
        [
          ['30 min', '555 MW', '1.631 MW (persistência)', '0,76%', '74,8%'],
          ['3 h', '1.559 MW', '3.172 MW (sazonal semanal)', '2,32%', '73,8%'],
          ['D+1', '1.685 MW', '3.176 MW (sazonal semanal)', '2,51%', '74,4%'],
        ],
      ),
      'Fonte: `docs/reports/baseline_carga.md`. O LightGBM ganha do melhor baseline nas 15 combinações série × horizonte; a cobertura fica abaixo dos 80% ideais (banda um pouco estreita).',
    ),
    secao(
      'Patamares e fatores climáticos',
      'O cartão **Patamares · o erro que custa mais** usa os horários de `Backend/config/processamento.yaml` (ver [[como-ler]]): a faixa desenhada nunca discorda da métrica por patamar.',
      aviso('nota', 'Fatores climáticos', 'Temperatura, radiação, vento e nuvens do painel lateral vêm do **Open-Meteo** (modelo ECMWF IFS) nas sedes das UFs: média na janela da curva, ponderada pela MMGD cadastrada em cada UF; a radiação é a média só das horas de sol. São exibidos para contexto: **não entram** nos modelos.'),
      'O **Temporal Fusion Transformer com perda assimétrica por patamar** (pesos em `Backend/config/modelos_tft.yaml`) roda no pipeline e entra no backtest ao lado do LightGBM (`docs/reports/baseline_carga.md`). O modelo exibido nesta tela é o de `curva.modelo` em `Backend/config/modelos_carga.yaml`. A versão do protótipo com perda assimétrica está em [[operacao]].',
    ),
    situacao('carga', 'previsao'),
  ],
}

export const LISTA_RISCOS: PaginaDoc = {
  id: 'lista-riscos',
  titulo: 'Lista de Riscos',
  grupo: GRUPO,
  resumo: 'Usinas e conjuntos ordenados por risco e montante previsto de corte — o produto do Desafio 1.',
  pergunta: 'Quais usinas vão ser cortadas, por qual razão, quando e quanto?',
  rotas: ['GET /api/riscos'],
  secoes: [
    secao(
      'Triagem',
      lista(
        'busca por nome, UF, ponto de conexão e ação (sem acento, vários termos);',
        'filtros de razão, fonte e horizonte, mais os de severidade da topbar;',
        'ordenação por coluna (padrão: severidade → probabilidade → montante);',
        'resumo do que está na tela (por severidade e MW) e **CSV** do mesmo recorte (separador `;`, abre direto no Excel);',
        'por linha: abrir o [[detalhe-alerta]] (clique ou Enter) ou ver a usina no [[mapa-hibrido]].',
      ),
    ),
    secao(
      'O modelo',
      lista(
        'Unidade: cada usina/conjunto (~290) × semi-hora × horizonte (30 min, 3 h, D+1).',
        'Entradas (todas até a emissão): histórico de corte da própria usina, **estado do sistema** (fração de usinas cortando no subsistema e no SIN), carga supervisionada e MMGD, calendário e faixa horária do alvo, fonte, subsistema, UF e a usina.',
        'Por razão (ENE; CNF opcional): classificador LightGBM → P(corte); regressor LightGBM → E[MW | corte].',
        'Split: treino abr/2023 → dez/2025 (inclui o regime em que a razão energética passou a dominar); teste em 2026. Baselines: persistência e frequência recente.',
      ),
      formula('montante esperado = P(corte) × E[MW | corte]'),
      tabela(
        ['Severidade', 'Probabilidade'],
        [
          ['crítico', '≥ 80%'],
          ['alto', '≥ 60%'],
          ['médio', '≥ 40%'],
        ],
      ),
      'Publicadas as 10 usinas de maior montante esperado. A ação recomendada é regra de texto por razão e faixa horária.',
    ),
    secao('Códigos de razão', tabela(['Código', 'Significado'], CODIGOS_RAZAO)),
    secao(
      'O que esta tela não afirma',
      aviso(
        'limite',
        'Limites',
        lista(
          'REL não é modelada; o CNF roda sem os limites de exportação NE e N/NE, que não existem no portal.',
          '`distribuidora` mostra o ponto de conexão (usinas da rede básica não têm distribuidora); usina sem coordenada no SIGA fica na sede da UF.',
          'O rótulo é a decisão operativa observada, não o potencial físico.',
        ),
      ),
    ),
    situacao('riscos'),
  ],
}

export const DETALHE_ALERTA: PaginaDoc = {
  id: 'detalhe-alerta',
  titulo: 'Detalhe do Alerta',
  grupo: GRUPO,
  resumo: 'Drill-down de um alerta: texto, decomposição SHAP, motivos por razão, ação e rastreabilidade até o dado.',
  pergunta: 'Por que o modelo acha que esta usina vai ser cortada, e de onde veio esse número?',
  rotas: ['GET /api/alertas/{id}', 'GET /api/riscos'],
  secoes: [
    secao(
      'Explicabilidade glass box',
      lista(
        '**Texto do alerta** — gerado no Backend por uma função só (`pipeline/explicabilidade.py::gerar_texto_alerta`), com botão para copiar e enviar à distribuidora.',
        '**Decomposição SHAP · peso por variável** — SHAP exato do próprio LightGBM (`pred_contrib`), agrupado em rótulos legíveis ("velocidade do vento", "carga supervisionada prevista"…). Barras à direita empurram o risco para cima; à esquerda, para baixo.',
        '**Motivos por razão** — a probabilidade de cada razão (ENE, CNF).',
        '**Ação recomendada** — por razão e faixa horária.',
        '**Rastreabilidade** — conjunto de dados, hora da previsão e horário previsto: do alerta até o dado de origem.',
      ),
      'A rota é `/detalhe-alerta/:id`; aberta pelo menu, sem id, a tela lista os alertas para escolher.',
      aviso('nota', 'Nenhum alerta sem evidência rastreável', 'Um alerta que o operador não consegue auditar até o dado de origem não é acionável.'),
    ),
    situacao('alertas', 'riscos'),
  ],
}

export const EXCEDENTES: PaginaDoc = {
  id: 'excedentes',
  titulo: 'Excedentes TSO-DSO',
  grupo: GRUPO,
  resumo: 'Excedente de geração distribuída previsto por subestação, visto pela distribuidora e pelo ONS: antecipar → priorizar → coordenar.',
  pergunta: 'Onde a MMGD vai gerar mais do que a carga local consome, quando, e o que coordenar com a distribuidora?',
  rotas: ['GET /api/excedentes'],
  secoes: [
    secao(
      'O que é o excedente',
      formula('excedente = max(0, geração de MMGD − carga)   por subestação de fronteira e semi-hora'),
      'Positivo = **fluxo reverso** para a rede básica, justamente o que o ONS não vê. Calculado para as subestações de fronteira do RJ (área piloto) a partir da BDGD × cadastro da ANEEL e da carga da área RJ do ONS; método em [[mapa]] e `docs/metodo_espacial.md`. Previsão por persistência sazonal de 1 dia, sem usar dado posterior ao "agora".',
    ),
    secao(
      'A tela',
      lista(
        '**Payload da interface ONS–DSO** — o que esta tela troca entre ONS e distribuidora.',
        'KPIs (excedente projetado total, prioridade alta) e barras **Excedente por área · MW**.',
        'Tabela com busca, filtro de horizonte, ordenação por coluna e **CSV**.',
        '**Executar** registra a ação no **registro de coordenação** da sessão, marcado como **simulado**: nada é enviado a sistema nenhum e o registro some ao recarregar.',
        '**Ver no mapa** abre o [[mapa-hibrido]] com a área selecionada.',
      ),
      'Publicação: por subestação, o pico de excedente nas próximas 24 h e o menor horizonte cuja janela contém o pico; prioridade por limiares em MW (`Backend/config/espacial.yaml`).',
      aviso(
        'limite',
        'Hipóteses do método',
        'Fator de geração único na área RJ (ainda sem irradiância por área) e perfil de carga plano no mês. Algumas subestações que exportam na medição da BDGD não aparecem com excedente na previsão: é o próximo ponto a melhorar.',
      ),
    ),
    situacao('excedentes'),
  ],
}

export const VALIDACAO_CONTRATO: PaginaDoc = {
  id: 'validacao-contrato',
  titulo: 'Validação (dashboard do contrato)',
  grupo: GRUPO,
  resumo: 'Métricas fora da amostra do modelo publicado, com split cronológico, contra os baselines.',
  pergunta: 'O modelo publicado erra menos que o baseline, e em quantos dias?',
  rotas: ['GET /api/validacao'],
  secoes: [
    secao(
      'A tela',
      lista(
        '**KPIs** — MAE, RMSE, MAPE e *skill*: os do Backend, na janela fixa publicada.',
        '**MAE diário** e **RMSE diário** — modelo × baseline no período escolhido (7, 14 ou 30 dias).',
        '**Resumo do período** — em quantos dias o modelo venceu o baseline e o pior dia; recalculado do histórico diário ao trocar o período.',
        '**Status das fontes de dados** — a partir do manifesto de download.',
        '**Metadados do modelo** — modelo avaliado, períodos do split, versão (hash da config).',
        '**Limitações declaradas** e **CSV** do histórico.',
      ),
    ),
    secao(
      'Garantias contra vazamento temporal',
      lista(
        'toda defasagem passa por `src/features/defasagens.py`, que recusa olhar depois da emissão; testes perturbam todo o futuro e exigem features idênticas;',
        'um único split (`src/models/split.py`); um teste treina duas vezes mudando o período de teste e exige modelos idênticos;',
        'a previsão só emite pontos fora da amostra e recusa modelo salvo com outro split.',
      ),
      'O backtest do protótipo, com perda assimétrica e calibração do classificador, está em [[validacao]].',
    ),
    situacao('validacao'),
  ],
}

export const METODOLOGIA: PaginaDoc = {
  id: 'metodologia',
  titulo: 'Metodologia',
  grupo: GRUPO,
  resumo: 'Como o O.R.A.C.U.L.O. chega aos números: fontes, os dois produtos, a auditoria da MMGD, a validação e os limites.',
  pergunta: 'De onde vêm os números das outras telas, e em que estado está cada parte do método?',
  rotas: ['GET /api/validacao'],
  secoes: [
    secao(
      'A tela',
      'Texto de produto fixo, com o que é dado vindo de fonte rastreável: patamares e faixas horárias de `Backend/config/processamento.yaml`, horizontes do schema do contrato, modelo avaliado e períodos do split da API. Cada bloco diz em que estado está (**em operação** / **em desenvolvimento**), conforme `docs/FASES.md`.',
      lista(
        '**Cinco fontes · três evidências · dois produtos** — o encadeamento do método.',
        '**Produto 1 · Carga supervisionada** e **Produto 2 · Risco de curtailment** — série alvo, modelos, baselines e rótulo.',
        '**Conciliação da MMGD por transformador** (satélite × BDGD × ANEEL) — ver [[auditoria]].',
        '**Patamares**, **Validação**, **Limitações declaradas** e **Fontes técnicas**.',
      ),
      aviso(
        'nota',
        'O que não veio do protótipo de design',
        'A tela "Extrapolação de tendências" (perfil horário e fatores de crescimento sem fonte) não foi implementada: mostrá-la seria apresentar número inventado como do ONS. Os números do PAR/PEL 2025 aparecem só com a fonte ao lado.',
      ),
    ),
    secao(
      'Onde está o detalhe',
      'Esta documentação aprofunda cada peça: [[despacho-preditivo]] e [[lista-riscos]] (os dois produtos), [[auditoria]] e [[mapa]] (a MMGD por área), [[validacao-contrato]] (o backtest) e [[limitacoes]].',
    ),
  ],
}

export const PAGINAS_CONTRATO: PaginaDoc[] = [
  VISAO_GERAL,
  MAPA_HIBRIDO,
  DESPACHO_PREDITIVO,
  LISTA_RISCOS,
  DETALHE_ALERTA,
  EXCEDENTES,
  VALIDACAO_CONTRATO,
  METODOLOGIA,
]
