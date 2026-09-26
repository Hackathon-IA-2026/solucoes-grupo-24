/**
 * Grupo Operação (telas do protótipo): Despacho preditivo, Risco e excedentes, Curva do pato.
 * Texto revisado a partir de docs/oraculo/documentacao_sphinx/source/modulos/operacao/*.rst,
 * conferido contra os rótulos das telas em src/oraculo/pages/{Operacao,Risco,Pato}.tsx.
 */
import { aviso, formula, lista, passos, secao, sub, tabela, type PaginaDoc } from '../modelo'

const GRUPO = 'Operação'

export const OPERACAO: PaginaDoc = {
  id: 'operacao',
  titulo: 'Despacho preditivo',
  grupo: GRUPO,
  resumo: 'Carga global − MMGD estimada = carga supervisionada, com banda P10–P90 em três horizontes.',
  pergunta: 'Quanto de carga o ONS vai enxergar nas próximas horas, e quanto a MMGD está escondendo agora?',
  rotas: ['GET /api/decomposition?area=SE&hours=72', 'GET /api/forecast?area=SE&horizon=3h&asymmetric=1'],
  secoes: [
    secao(
      'Controles',
      lista(
        '**Área** (topbar) — subsistema: SE, S, NE ou N.',
        '**Horizonte** — 30 min, 3 h ou D+1.',
        '**Assimetria** — liga e desliga a perda assimétrica por patamar. É o controle que transforma o argumento em evidência: desligado, o mesmo conjunto de teste mostra o desempenho sem os pesos.',
      ),
    ),
    secao(
      'Os quatro KPIs',
      tabela(
        ['KPI', 'Unidade', 'Como ler'],
        [
          ['**Carga supervisionada (último ponto)**', 'MWmed', 'o que o ONS mede: a carga global **menos** a MMGD estimada'],
          ['**MMGD estimada — pico na janela**', 'MWmed', 'maior valor estimado da geração distribuída nas 72 h, perto do meio-dia solar; **é estimativa, com viés conservador**'],
          ['**Mínima supervisionada**', 'MWmed', 'o vale da carga supervisionada e a hora em que ocorreu; em áreas de alta penetração o vale migra da madrugada para o meio-dia, a assinatura da MMGD'],
          ['**Maior rampa horária**', 'MW/h', 'maior variação entre horas consecutivas; dimensiona a flexibilidade exigida no fim da tarde'],
        ],
      ),
    ),
    secao(
      'Decomposição da carga · últimas 72 h',
      'Área empilhada de **carga supervisionada** e **MMGD estimada**, somando a carga global. A dica do cartão mostra o resíduo da identidade:',
      formula('carga global = carga supervisionada + MMGD estimada'),
      'Há teste que exige resíduo nulo: a identidade é exata por construção, não aproximada.',
      aviso(
        'premissa',
        'Como a MMGD é estimada',
        'A MMGD **não existe** como série horária por área no Portal. O estimador combina:',
        passos(
          '**Geometria solar** — declinação e equação do tempo de Spencer (1971) e céu claro de Haurwitz: a forma da curva de irradiância para a latitude e o dia.',
          '**Capacidade instalada declarada** por área.',
          '**Fator de nebulosidade pelo método do envelope** — o percentil 90 da carga em horas comparáveis do mês aproxima a carga global, porque o dia de maior carga observada é o de menor geração distribuída.',
        ),
        '**Viés declarado:** mesmo os dias de maior carga contêm alguma geração distribuída. A estimativa é **um piso, não um valor central**.',
      ),
    ),
    secao(
      'Fator de nebulosidade e irradiância',
      'Duas séries no mesmo eixo: a irradiância de céu claro calculada e o fator de nebulosidade estimado. Serve para inspecionar o estimador: fator perto de 1 em dia claro, deprimido em dia encoberto. É o fator que separa a geração potencial de céu claro da geração provável.',
    ),
    secao(
      'Previsão da carga supervisionada',
      'Série observada, mediana prevista (P50) e **banda P10–P90**. A dica mostra o período de treino; as métricas são sobre todo o conjunto de teste, e o gráfico mostra a janela recente.',
      aviso(
        'nota',
        'A banda não é enfeite',
        'Uma previsão pontual esconde o que o operador precisa: **quanto** o valor pode se afastar. A banda sai de três regressões quantílicas independentes, não de um intervalo simétrico suposto em torno da média.',
      ),
    ),
    secao(
      'Desempenho no teste e erro por patamar',
      'MAE, RMSE, cobertura da banda e *skill score* contra o melhor baseline, **fora da amostra**. *Skill* positivo = erro menor que o baseline; negativo = o baseline ganhou, e aparece em vermelho.',
      'O erro decomposto por patamar é onde a perda assimétrica se justifica, ou não. Pesos do protótipo (`ASYMMETRIC_WEIGHTS` em `Backend/oraculo/config.py`):',
      tabela(
        ['Patamar', 'Subestimar', 'Superestimar', 'Por que o peso é assim'],
        [
          ['Mínima diurna (09–15 h)', '1,0', '**2,2**', 'superestimar a carga no vale leva a subestimar o excedente renovável, o erro que produz curtailment inesperado'],
          ['Rampa (16–19 h)', '**2,0**', '1,2', 'subestimar a rampa deixa o sistema sem flexibilidade quando a solar sai'],
          ['Ponta noturna (18–22 h)', '**2,8**', '1,0', 'o erro mais caro: subestimar a ponta é risco de atendimento'],
          ['Base', '1,0', '1,0', 'nenhuma direção é mais custosa'],
        ],
      ),
      'Implementação em `Backend/oraculo/models/quantile.py`: perda *pinball* assimétrica suavizada por Huber, otimizada por L-BFGS-B.',
    ),
    secao(
      'Peso por grupo de variável',
      'Barras com a contribuição relativa de cada grupo (calendário, defasagens, geometria solar, meteorologia, memória operativa): coeficientes da mediana escalados pelo desvio de cada variável.',
      aviso(
        'medido',
        'Um erro que este cartão revelou',
        'Numa versão anterior todos os pesos vinham nulos: `np.std` propagava `NaN` das colunas de defasagem. Corrigido com `np.nanstd` e `nan_to_num`, com teste de regressão. O cartão é útil justamente porque um peso obviamente errado salta aos olhos.',
      ),
    ),
    secao(
      'O que esta tela não afirma',
      aviso(
        'limite',
        'Limites',
        lista(
          'A MMGD é **estimada**, não medida, e o viés é conservador por construção.',
          'A previsão é da **carga supervisionada**, não da carga global.',
          'A tela **não substitui o PREVCARGA**: é camada complementar focada na parcela não supervisionada.',
          'O desempenho é do conjunto de teste cronológico corrente; a auditoria do procedimento está em [[validacao]].',
          'A previsão oficial do contrato (LightGBM quantílico, SIN e subsistemas) está em [[despacho-preditivo]].',
        ),
      ),
    ),
  ],
}

export const RISCO: PaginaDoc = {
  id: 'risco',
  titulo: 'Risco de curtailment e excedentes',
  grupo: GRUPO,
  resumo: 'Onde há risco de corte nas próximas horas, quanto e por qual razão, com evidência rastreável.',
  pergunta: 'Onde há risco de curtailment nas próximas horas, qual o montante esperado e por qual razão?',
  rotas: ['GET /api/risk?horizon=d1&level=estado&asymmetric=0'],
  secoes: [
    secao(
      'Os quatro KPIs',
      tabela(
        ['KPI', 'Unidade', 'Como ler'],
        [
          ['**Áreas com risco ≥ 50%**', 'contagem', 'quantas áreas têm probabilidade calibrada de restrição acima de 50%'],
          ['**Potência esperada de corte**', 'MW', 'soma de E[corte] sobre as áreas; é o valor **esperado**, não o pior caso'],
          ['**Predominância de razão energética**', 'áreas', 'em quantas áreas a razão **ENE** predomina, o recorte do eixo (ii)'],
          ['**AUC fora da amostra (mediana)**', '—', 'desempenho do classificador: mediana entre as áreas, em teste cronológico'],
        ],
      ),
    ),
    secao(
      'O montante esperado',
      formula('E[corte] = P(restrição) × mediana condicional do corte'),
      'Dois fatores independentes: a probabilidade de haver restrição e, **dado que haja**, a mediana histórica do montante. Multiplicá-los evita reportar o pior caso como se fosse o esperado.',
    ),
    secao(
      'Mapa esquemático · severidade por área',
      'Representação por UF, colorida por severidade. É **esquemático** de propósito: arranjo geográfico aproximado, não mapa georreferenciado. Clicar numa área troca a série de probabilidade horária.',
      'A granularidade-alvo em produção é área de concessão e transformação de fronteira, que exige a BDGD (ver [[mapa]]).',
    ),
    secao(
      'Eventos priorizados por severidade',
      formula('severidade = 0,45·P + 0,35·E[corte] + 0,20·criticidade'),
      'Tabela ordenada. Cada alerta traz área e horizonte, probabilidade calibrada, montante esperado em MW, **razão decomposta** (ENE, CNF, REL, PAR), **evidências** e **ações recomendadas**. A ponderação de criticidade é premissa declarada, não medição.',
      aviso(
        'nota',
        'Nenhum alerta sem evidência rastreável',
        'Um alerta que não pode ser auditado até o dado de origem não é acionável: o operador não tem como avaliá-lo e por isso não o usará.',
      ),
    ),
    secao(
      'Probabilidade horária · área selecionada',
      'Série da probabilidade calibrada hora a hora para a área escolhida. A calibração é por binning monotônico no conjunto de validação.',
    ),
    secao(
      'Como o classificador funciona',
      'Regressão logística regularizada, ajustada por IRLS, sobre os registros reais de constrained-off. Probabilidade calibrada por binning monotônico; AUC por postos de Mann-Whitney.',
      aviso(
        'medido',
        '1. Sem vazamento',
        'Uma versão inicial atingiu AUC 0,99 com probabilidade 1,00 — número bonito e falso: o alvo `corte_mw` colocava a defasagem de 1 h do próprio rótulo entre as variáveis. A memória operativa legítima é o histórico de restrição defasado em **24 h ou mais**, o que o operador conhece ao prever D+1 (`occurrence_memory(y, min_lag=24, window=7*24)`). **A AUC caiu para 0,902** e passou a significar algo.',
      ),
      aviso(
        'medido',
        '2. Só na janela solar',
        'Fora da janela solar a resposta é trivialmente "não haverá restrição fotovoltaica", e incluir essas horas infla a AUC sem informar. O limiar de rótulo era 2% da capacidade e rotulava ruído. Correções: limiar de **10%** (`RISK_LABEL_THRESHOLD_FRACTION`) e janela solar (`RISK_DAYLIGHT_ONLY`), em `Backend/oraculo/config.py`.',
      ),
    ),
    secao(
      'O que esta tela não afirma',
      aviso(
        'limite',
        'Limites',
        lista(
          '**O rótulo é a decisão operativa observada**, não o potencial físico de geração.',
          'A agregação é **por área**, não por usina. O risco por usina, do modelo do contrato, está em [[lista-riscos]].',
          'A tela **não automatiza despacho**: produz indicador com evidência; a decisão é do operador.',
        ),
      ),
    ),
  ],
}

export const PATO: PaginaDoc = {
  id: 'pato',
  titulo: 'Curva do pato prevista pelo tempo',
  grupo: GRUPO,
  resumo: 'Radiação prevista por modelos de IA e físicos × onde está a MMGD → carga supervisionada dos próximos dias.',
  pergunta: 'Como será a carga supervisionada dos próximos dias — a barriga do meio-dia e a rampa do fim da tarde — dado o tempo previsto e onde está instalada a MMGD?',
  rotas: ['GET /api/tempo/status', 'GET /api/tempo/pato'],
  secoes: [
    secao(
      'Os KPIs',
      tabela(
        ['KPI', 'Como ler'],
        [
          ['**Barriga do pato**', 'mínimo da carga supervisionada entre 10 h e 15 h no dia'],
          ['**Rampa do fim da tarde**', 'da barriga ao pico das 17 h às 21 h: a subida que os recursos flexíveis precisam cobrir'],
          ['**MMGD no pico**', 'geração prevista da MMGD no seu máximo'],
          ['**Ganho sobre a persistência**', 'quanto a previsão com tempo erra menos que a persistência sem tempo, no backtest'],
        ],
      ),
      'Na primeira abertura o servidor baixa as previsões; o cartão **Progresso** mostra a etapa até os dados chegarem.',
    ),
    secao(
      'Cartões',
      lista(
        '**Carga supervisionada prevista** — média dos modelos, faixa entre modelos e cada modelo. A faixa é a divergência entre AIFS, IFS e GFS: quando os modelos discordam sobre as nuvens, a barriga fica incerta.',
        '**Semana** — barriga + rampa = pico da noite, em GW, dia a dia. No fim de semana a carga é menor com a mesma MMGD: a barriga afunda.',
        '**MMGD prevista na semana** — geração da MMGD por hora, média dos modelos, em MW.',
        '**Backtest · últimos 14 dias do teste · SIN** — observado × persistência × média dos modelos, com as previsões **arquivadas** (o que cada modelo de fato previu).',
        '**Validação fora da amostra** — erro da barriga e da rampa por modelo, contra persistência e ERA5.',
        '**O tempo mexe nos dois lados**, **Modelos de tempo** e **Calibração e premissas** — as notas de método abaixo.',
      ),
    ),
    secao(
      'Modelos de tempo',
      tabela(
        ['Modelo', 'Tipo', 'Situação'],
        [
          ['ECMWF AIFS', 'IA', 'em uso (Open-Meteo), previsão e previsões arquivadas'],
          ['ECMWF IFS', 'físico', 'em uso'],
          ['NOAA GFS', 'físico', 'em uso'],
          ['NVIDIA Earth-2 (FourCastNet, CorrDiff)', 'IA', 'provedor plugável: o contrato é o mesmo, falta o runtime (GPU e `earth2studio`, ou NIM com chave)'],
          ['GraphCast (DeepMind)', 'IA', 'disponível no Open-Meteo, mas não produz radiação solar'],
        ],
      ),
    ),
    secao(
      'Método',
      passos(
        '**Onde está a MMGD** — capacidade por município (cadastro ANEEL) agrupada em células de ~2,5° por subsistema.',
        '**Geração prevista** em cada célula, com G a radiação global horizontal e T a temperatura previstas.',
        '**Carga supervisionada prevista** a partir do dia-tipo, corrigida pela MMGD e pela temperatura.',
      ),
      formula('P = C · PR · (G / 1000) · (1 − 0,004 · (T + 0,03·G − 25))'),
      formula('sup(d) = sup_tipo(d) − β · ΔMMGD + γ · ΔT'),
      'O dia-tipo é a média do mesmo dia da semana nas duas últimas semanas, sem feriados. β e γ são estimados por subsistema numa janela de treino **anterior** ao teste. O PR é calibrado por subsistema com o ERA5 para reproduzir a MMGD média oficial de 2026 (2ª RQ do PLAN 2026-2030); os valores (0,64 a 0,83) são os de sistemas fotovoltaicos reais.',
      aviso(
        'medido',
        'O tempo mexe nos dois lados da curva',
        'Sem controlar a temperatura, a sensibilidade da carga à MMGD sai perto de zero (R² 0,02 no Sudeste): dia de sol aumenta a MMGD, mas também aquece e aumenta a refrigeração. Com a temperatura, β volta a ~0,8 no Sudeste, γ fica em ~830 MW/°C e o R² sobe para 0,30.',
      ),
    ),
    secao(
      'Validação',
      'Backtest com as previsões arquivadas de cada modelo contra a carga supervisionada do ONS. Comparações:',
      lista(
        '**persistência** — o mesmo dia da semana das duas últimas semanas, sem tempo;',
        'cada modelo e a **média dos modelos**;',
        '**ERA5 (tempo perfeito)** — o teto: o erro que sobra ali não é do tempo, é do dia-tipo.',
      ),
      'Nenhum modelo é o melhor em tudo (o AIFS acerta bem a barriga, mas erra mais a rampa): a média dos modelos é a escolha equilibrada.',
      sub('Limites'),
      passos(
        'O dia-tipo não prevê mudanças de regime (feriados longos, eventos); dias de feriado ficam fora do backtest.',
        'O PR é um só por subsistema: orientação, sombreamento e limitação de inversores entram só em média.',
        'A MMGD é a do cadastro atual; o crescimento dentro da semana é desprezível.',
      ),
    ),
  ],
}

export const PAGINAS_OPERACAO: PaginaDoc[] = [OPERACAO, RISCO, PATO]
