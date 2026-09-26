/**
 * Grupo Confiança (telas do protótipo): Validação do método e Dados abertos.
 * Origem: docs/oraculo/documentacao_sphinx/source/modulos/confianca/*.rst, conferido contra
 * src/oraculo/pages/{ValidacaoMetodo,DadosAbertos}.tsx.
 */
import { aviso, lista, secao, tabela, type PaginaDoc } from '../modelo'

const GRUPO = 'Confiança'

export const VALIDACAO: PaginaDoc = {
  id: 'validacao',
  titulo: 'Validação do método',
  grupo: GRUPO,
  resumo: 'Backtest cronológico, baselines obrigatórios, métricas por patamar e calibração probabilística.',
  pergunta: 'O método supera os baselines? Onde ele erra?',
  rotas: ['GET /api/validation?area=SE&asymmetric=1'],
  secoes: [
    secao(
      'Por que esta tela existe',
      aviso(
        'nota',
        'Desempenho fora da amostra, contra um baseline honesto',
        'É fácil mostrar um gráfico bonito. O que distingue uma solução operável é responder *qual o desempenho fora da amostra, contra um baseline honesto* — incluindo os casos em que o modelo perde. A validação do modelo do contrato (LightGBM) está em [[validacao-contrato]].',
      ),
    ),
    secao(
      'Os quatro KPIs',
      tabela(
        ['KPI', 'Como ler'],
        [
          ['**Corte cronológico**', 'se o teste é **estritamente posterior** ao treino; verificado por teste automatizado'],
          ['**Instante do corte**', 'onde o treino termina e o teste começa'],
          ['**Melhor MAE**', 'menor erro absoluto médio entre os horizontes, em MW'],
          ['**Função de perda**', 'assimétrica ou simétrica, conforme o seletor'],
        ],
      ),
    ),
    secao(
      'Os cartões',
      lista(
        '**Desempenho por horizonte** — MAE, RMSE, cobertura P10–P90 e *skill score* contra o melhor baseline, em 30 min, 3 h e D+1. *Skill* negativo aparece em vermelho, não omitido.',
        '**Métricas por patamar operativo** — onde se verifica se a perda assimétrica entregou o que promete: erro menor **na direção que importa** em cada patamar.',
        '**Calibração probabilística** — probabilidade prevista × frequência observada; a diagonal é a calibração perfeita.',
        '**Efeito da perda assimétrica (3 h)** — com e sem os pesos, no mesmo conjunto de teste, erro por direção em cada patamar.',
        '**Série de teste · horizonte 3 h** — observado, previsto e banda ao longo do teste: **onde** o modelo erra, não só quanto.',
        '**Baselines avaliados no mesmo conjunto de teste** — persistência, sazonal-ingênuo diário e semanal.',
      ),
      aviso(
        'nota',
        'Por que calibração e não só AUC',
        'Um classificador pode ordenar bem (AUC alta) e ainda dizer "70% de chance" em situações que ocorrem 30% das vezes. Para uso operativo o **valor** da probabilidade tem de significar algo. Calibração por binning monotônico; AUC por postos de Mann-Whitney.',
      ),
      aviso(
        'nota',
        'Baselines não são formalidade',
        'Em série de carga o sazonal-ingênuo semanal é **difícil de superar**. Um modelo que não o supera não é promovido.',
      ),
    ),
    secao(
      'O procedimento de backtest',
      lista(
        'corte **estritamente cronológico**, com **embargo** entre treino e teste para impedir vazamento por defasagens;',
        'baselines avaliados **no mesmo conjunto de teste**;',
        'métricas por horizonte e por patamar;',
        'verificação automatizada da ausência de vazamento.',
      ),
    ),
    secao(
      'Dois erros que esta tela revelou',
      aviso(
        'medido',
        'Sazonalidade anual não identificada',
        'O *skill score* veio **−0,49** em 30 min: o treino usava um recorte parcial de 2026 e a sazonalidade anual não era identificável. Correção: carregar dois anos; o *skill* passou a **+0,575**. A tela reprovou o modelo, e isso levou à correção.',
      ),
      aviso(
        'medido',
        'Vazamento no classificador de risco',
        'AUC 0,99 com probabilidade 1,00, porque a defasagem de 1 h do próprio rótulo estava entre as variáveis. Com `occurrence_memory(min_lag=24)`: **AUC 0,902**.',
      ),
    ),
    secao(
      'O que esta tela não afirma',
      aviso(
        'limite',
        'Limites',
        lista(
          'O desempenho é do **conjunto de teste corrente**: janela diferente, número diferente.',
          'A cobertura da banda é medida no agregado; por isso existe a tabela por patamar.',
          'Cobre os modelos de carga e de risco do protótipo. O detector tem validação própria em [[visao]] e o CLM em [[clm]].',
        ),
      ),
    ),
  ],
}

export const DADOS: PaginaDoc = {
  id: 'dados',
  titulo: 'Dados abertos e proveniência',
  grupo: GRUPO,
  resumo: 'Catálogo do Portal de Dados Abertos do ONS, estado do cache e rastro de cada número exibido.',
  pergunta: 'De onde veio cada número, quando foi extraído, e o que mais existe no Portal que ainda não usamos?',
  rotas: ['GET /api/catalog', 'GET /api/catalog/{pkg}', 'GET /api/provenance', 'POST /api/ingest'],
  secoes: [
    secao(
      'Os quatro KPIs',
      tabela(
        ['KPI', 'Como ler'],
        [
          ['**Conjuntos no Portal**', 'tamanho do catálogo CKAN do ONS'],
          ['**Recursos em cache**', 'quantos recursos estão em `.cache/` com hash registrado'],
          ['**Modo corrente**', '`live`, `cache` ou `demo`: origem predominante na sessão'],
          ['**Fontes externas mapeadas**', 'fontes de fora do ONS, com o estado de cada uma'],
        ],
      ),
    ),
    secao(
      'Os cartões',
      lista(
        '**Conjuntos usados na solução** — os conjuntos consumidos, com granularidade e uso (lista em [[proveniencia]]).',
        '**Catálogo completo do Portal** — todos os conjuntos, navegáveis; clicar carrega o detalhe. Mostra que os conjuntos usados foram **escolhidos**, e torna verificável o que ainda não foi usado.',
        '**Detalhe do conjunto** — descrição, dicionário de campos e recursos por ano/mês com tamanho e data.',
        '**Relatório de ingestão** — por operação: conjunto, recurso, linhas, bytes, instante, modo e avisos. O campo `bytes_read` mostra o efeito das requisições `Range`.',
        '**Previsto para a fase presencial** — conjuntos e fontes a incorporar, com a justificativa: a lista honesta do que falta.',
        '**Fontes externas e seu estado** — BDGD e cadastro de GD da ANEEL, IBGE, meteorologia, com a acessibilidade atual. Uma fonte inacessível é informação (o guia da NERC retorna HTTP 403 a acesso automatizado; nenhum número se apoia nele).',
        '**Manifesto de cache · auditoria** — recurso, conjunto, hash SHA-256, tamanho, instante e URL de origem.',
      ),
      aviso(
        'nota',
        'Única rota de escrita',
        'Os controles disparam ingestão (`POST /api/ingest`, com opção de forçar reextração), limpam o cache do cliente e atualizam o catálogo. A ingestão é a única rota de escrita da API do protótipo.',
      ),
    ),
    secao(
      'O que esta tela não afirma',
      aviso(
        'limite',
        'Limites',
        lista(
          'O catálogo é o que o CKAN do ONS publica: conjunto novo aparece aqui quando aparece lá.',
          'A defasagem de publicação é informada quando conhecida (`lag_note`); quando não, o campo vem vazio, nunca estimado.',
          'O cache é local à execução: não é repositório compartilhado nem substitui ingestão programada.',
          'A ingestão do dashboard do contrato (`run_heavywork.py`) é outra: baixa Parquet do CKAN, a API de carga do ONS e a ANEEL para `Backend/data/raw/`.',
        ),
      ),
    ),
  ],
}

export const PAGINAS_CONFIANCA: PaginaDoc[] = [VALIDACAO, DADOS]
