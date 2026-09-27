/**
 * Páginas gerais da documentação: o que é o sistema, como ler as telas, proveniência,
 * limitações e glossário. Origem do texto: a documentação Sphinx do protótipo
 * (docs/oraculo/documentacao_sphinx/source/visao-geral, limitacoes.rst, glossario.rst) e
 * docs/visao_geral_sistema.md, revisados para o estado atual das telas React.
 *
 * O que é dado de configuração NÃO é reescrito aqui: patamares e faixas horárias vêm de
 * content/calendario.ts (Backend/config/processamento.yaml), as limitações do dashboard do
 * contrato de content/limitacoes.ts e a lista de telas de src/modules.ts. Assim a ajuda nunca
 * discorda do que as telas usam.
 */
import { FAIXAS_CURTAILMENT, PATAMARES, formatIntervalo } from '../../../content/calendario'
import { LIMITACOES, LIMITES_SOLUCAO } from '../../../content/limitacoes'
import { MODULES } from '../../../modules'
import { aviso, codigo, lista, passos, secao, sub, tabela, type PaginaDoc } from '../modelo'

const GRUPO = 'Geral'

/** Tabela "grupo · tela · o que mostra", gerada do registro de módulos (fonte única do menu). */
const tabelaDeTelas = () =>
  tabela(
    ['Grupo', 'Tela', 'O que mostra'],
    MODULES.map((m) => [m.grupo ?? '—', m.ajuda ? `[[${m.ajuda}|${m.label}]]` : m.label, m.description]),
  )

export const INICIO: PaginaDoc = {
  id: 'inicio',
  titulo: 'O que é o O.R.A.C.U.L.O.',
  grupo: GRUPO,
  resumo: 'O problema, o que a solução entrega, como as telas se organizam e o que ela não faz.',
  secoes: [
    secao(
      'O problema',
      'O ONS supervisiona o Sistema Interligado Nacional com alta observabilidade sobre os recursos centralizados: telemetria, previsão e controlabilidade. Na **fronteira com a distribuição** essa visão muda de natureza e passa a depender de informação agregada e de estimativa.',
      'A micro e minigeração distribuída (**MMGD**), sobretudo solar em telhados, está nas redes das distribuidoras. Ela:',
      lista(
        'não tem telemetria em tempo real por área;',
        'não aparece no Portal de Dados Abertos como série horária por área: manifesta-se como **redução da carga verificada**;',
        'chega ao operador com cadastro atrasado (a BDGD da distribuidora é anual; o cadastro da ANEEL é diário);',
        'responde a distúrbios de forma que os modelos de estudo não reproduzem, como a perturbação de 15/08/2023 evidenciou.',
      ),
      'Essa é a tese central do projeto: o **gap TSO–DSO**. A MMGD é pouco visível ao ONS, e isso afeta os dois desafios do hackathon.',
    ),
    secao(
      'Os dois desafios e o que a solução entrega',
      tabela(
        ['Desafio', 'Pergunta', 'Entrega'],
        [
          [
            '**2 — Demanda**',
            'prever a carga que o ONS de fato opera',
            '**carga supervisionada** (carga global − MMGD estimada), a cada 30 min, por subsistema, com quantis P10/P50/P90 nos horizontes 30 min, 3 h e D+1',
          ],
          [
            '**1 — Curtailment**',
            'antecipar cortes de geração eólica e solar (constrained-off)',
            '**risco de corte por razão** (ENE = energética, CNF = confiabilidade) por usina, com montante esperado em MW, explicação por variável e ação recomendada',
          ],
        ],
      ),
      'Os dois produtos dependem da mesma grandeza hoje pouco visível: **quanta MMGD existe e onde**. Por isso existe um terceiro bloco, a **auditoria da MMGD em 3 camadas** (satélite + BDGD + cadastro da ANEEL), que estima um fator de correção da capacidade instalada por área de influência de subestação.',
    ),
    secao(
      'As telas',
      'O menu lateral tem dois conjuntos de telas. Os grupos **Operação → Confiança** são as telas do protótipo O.R.A.C.U.L.O. (API em `Backend/oraculo`). O grupo **Dashboard do contrato** lê a publicação do trabalho pesado (`run_heavywork.py`) pela API FastAPI de `Backend/src/api`, no formato do contrato (`docs/schema_contrato.json`).',
      tabelaDeTelas(),
    ),
    secao(
      'Por que o nome',
      '**O**bservabilidade de **R**edes e **A**nálise de **C**urtailment em **U**sinas e **L**imites **O**peracionais.',
      'Não é um oráculo que adivinha: é uma camada que **torna observável** o que hoje é estimado e que declara a incerteza de cada estimativa.',
    ),
    secao(
      'O que a solução não faz',
      aviso(
        'limite',
        'Fronteiras de escopo, declaradas',
        lista(
          '**Não executa fluxo de potência.** Não calcula tensão, carregamento nem estabilidade. O destino natural dos seus produtos são as ferramentas que fazem isso, e por isso existe a tela [[clm]].',
          '**Não substitui o PREVCARGA/PMO.** É camada complementar, focada na parcela não supervisionada.',
          '**Não automatiza despacho.** Produz indicador e evidência rastreável; a decisão é do operador.',
          '**Não mede a MMGD.** Estima, com viés declarado.',
        ),
      ),
      'A lista completa está em [[limitacoes]].',
    ),
    secao(
      'Por onde começar',
      passos(
        '[[como-ler]] — a chave de leitura que vale para todas as telas.',
        '[[operacao]] e [[risco]] — os dois eixos, na visão do protótipo.',
        '[[visao-geral]] — o resumo do dashboard do contrato.',
        '[[proveniencia]] e [[limitacoes]] — de onde vem cada número e o que ele não afirma.',
      ),
    ),
  ],
}

export const COMO_LER: PaginaDoc = {
  id: 'como-ler',
  titulo: 'Como ler os painéis',
  grupo: GRUPO,
  resumo: 'Anatomia de uma tela, cores, rótulos de procedência, unidades, patamares e atalhos.',
  secoes: [
    secao(
      'Anatomia de uma tela',
      codigo(
        [
          '┌─ título e subtítulo (topbar) ─────────────────────────────┐',
          '│  o que a tela responde, em uma frase                      │',
          '├───────────────────────────────────────────────────────────┤',
          '│  faixa de nota (quando há): o aviso que muda a leitura    │',
          '├──────────┬──────────┬──────────┬──────────────────────────┤',
          '│   KPI    │   KPI    │   KPI    │   KPI                    │',
          '├──────────┴──────────┴──────────┴──────────────────────────┤',
          '│  cartões: gráfico, tabela ou lista de estatísticas        │',
          '│  cada um com dica (canto direito) e nota (ao pé)          │',
          '├───────────────────────────────────────────────────────────┤',
          '│  ▸ Proveniência e notas (N)                               │',
          '└───────────────────────────────────────────────────────────┘',
        ].join('\n'),
      ),
      sub('KPI'),
      'Número de cabeceira, com **rótulo**, **valor**, **unidade** e um **rodapé** que explica a origem ou o contexto. A cor de acento tem significado: âmbar para atenção, vermelho para desfavorável, verde para medição favorável.',
      sub('Dica do cartão'),
      'Texto curto no canto direito do cabeçalho do cartão. Em geral traz o **método** ou o **parâmetro** usado (`método: NNLS`, `R² 0,91`, `clique para abrir o detalhe`).',
      sub('Nota do cartão'),
      'Texto ao pé do cartão, com a **advertência metodológica**: por que o número é o que é, ou o que ele não significa. É a parte da tela que costuma ser ignorada e a que mais protege de conclusão errada.',
      sub('Faixa de nota'),
      'Barra no topo da tela, com borda à esquerda. Quando **âmbar**, contém uma ressalva que altera a leitura de toda a tela.',
      sub('Bloco de proveniência'),
      'Recolhível, ao pé das telas do protótipo. Uma linha por recurso de dado usado naquela tela. Ver [[proveniencia]].',
    ),
    secao(
      'Cores',
      tabela(
        ['Cor', 'Significado'],
        [
          ['verde', 'medido, confere, favorável, baixa penetração'],
          ['âmbar', 'premissa declarada, atenção, média penetração'],
          ['vermelho', 'não afirmado, falha, alta penetração, desfavorável'],
          ['azul-petróleo', 'normativo, vindo de fonte externa'],
        ],
      ),
      'Os avisos desta documentação usam a mesma convenção: **Importante** (azul), **Premissa declarada** (âmbar), **Medido / corrigido** (verde) e **Limite** (vermelho).',
    ),
    secao(
      'As quatro convenções que evitam erro de leitura',
      sub('1. Todo número tem procedência declarada'),
      'Nas telas do Mapa Inteligente e do CLM a procedência é explícita em rótulo:',
      tabela(
        ['Rótulo', 'Significado'],
        [
          ['**derivado**', 'calculado com dado que a ferramenta observa'],
          ['**premissa**', 'hipótese versionada no código, com o motivo escrito'],
          ['**WECC** / **referência**', 'vem de fonte externa normativa ou publicada'],
          ['**a calibrar**', '**não afirmado**: exibido com o valor de referência; exige ensaio, medição de campo ou base cadastral'],
        ],
      ),
      sub('2. Estimativa nunca é apresentada como medição'),
      'A MMGD é **estimada**, com viés declarado. A cena do banco de ensaio da visão computacional é **sintética** (com verdade fundamental conhecida) e isso está na tela; a detecção em **imagem real** não tem verdade fundamental, e isso também está na tela.',
      sub('3. Modelo aparece sempre ao lado do baseline'),
      'Nenhum desempenho é publicado sozinho. Persistência e sazonal-ingênuo são avaliados no mesmo conjunto de teste, e o *skill score* negativo aparece em vermelho em vez de ser omitido.',
      sub('4. A origem do dado está sempre visível'),
      'Nas telas do protótipo, o selo `live`, `cache` ou `demo` acompanha a resposta. No dashboard do contrato a topbar diz **DADOS DE dd/mm HH:MM** (o "agora" publicado) ou **API INDISPONÍVEL**.',
    ),
    secao(
      'Unidades, tempo e patamares',
      tabela(
        ['Convenção', 'Detalhe'],
        [
          ['Potência', '`MWmed` para média no intervalo, `MW` para instantânea, `MW/h` para rampa, `MWp`/`kWp` para capacidade fotovoltaica instalada'],
          ['Tempo', 'horário de Brasília na tela (UTC−3 fixo); cada timestamp marca o **início** da semi-hora (19:00 = 19:00–19:30); UTC nos campos de proveniência (`fetched_at`)'],
          ['Dia-tipo', 'útil, sábado, domingo e feriado; **feriado é tratado como domingo**'],
          ['Quantis', 'P10, P50 (mediana) e P90; a banda nos gráficos é P10–P90'],
        ],
      ),
      sub('Patamares da curva de carga (dashboard do contrato)'),
      'Lidos de `Backend/config/processamento.yaml`: são os mesmos que o gráfico do Despacho Preditivo desenha e que o backtest usa.',
      tabela(
        ['Patamar', 'Horas', 'O erro que custa mais'],
        PATAMARES.map((pt) => [pt.nome, formatIntervalo(pt.horas), pt.errarPior]),
      ),
      sub('Faixas horárias de curtailment'),
      tabela(
        ['Faixa', 'Intervalos'],
        FAIXAS_CURTAILMENT.map((f) => [f.rotulo, f.intervalos.map(formatIntervalo).join(' e ')]),
      ),
      aviso(
        'nota',
        'Os patamares do protótipo são outros',
        'As telas [[operacao]] e [[validacao]] vêm do protótipo e usam os patamares dos pesos da perda assimétrica dele (`ASYMMETRIC_WEIGHTS` em `Backend/oraculo/config.py`): mínima diurna 09–15 h, rampa 16–19 h, ponta noturna 18–22 h e base. As faixas se sobrepõem de propósito; vale o peso do patamar mais crítico. Não compare números por patamar entre as duas famílias de telas sem olhar essa diferença.',
      ),
    ),
    secao(
      'Ajuda (F1) e exportação',
      tabela(
        ['Atalho', 'O que faz'],
        [
          ['`F1`', 'abre a página desta documentação **correspondente à tela aberta**; pressionar de novo fecha'],
          ['`Esc`', 'fecha a ajuda'],
          ['botão `?` da topbar', 'o mesmo que F1'],
        ],
      ),
      'O quadro de ajuda tem um índice com busca (título e texto de todas as páginas), links entre páginas e o botão **Abrir a tela** para ir à tela documentada.',
      'Em **Exportar** é possível baixar a página aberta ou a documentação completa em **Markdown** ou **HTML** autocontido (abre em qualquer navegador, sem servidor), e **imprimir / salvar em PDF** pelo diálogo de impressão do navegador.',
      aviso(
        'nota',
        'A documentação vive no frontend',
        'O texto está em `Frontend/oraculo-dashboard/src/oraculo/documentacao/`, uma página por tela. Não depende do backend nem de script de geração: a ajuda funciona mesmo com a API fora do ar. Um teste exige que **toda tela do menu tenha página** e que todo link interno aponte para uma página existente.',
      ),
    ),
    secao(
      'A primeira carga',
      'O primeiro acesso a uma tela do protótipo pode demorar: é a ingestão real no Portal de Dados Abertos do ONS (e, na [[fronteira]], a construção da base agregada da ANEEL). As respostas seguintes vêm do cache. O campo `mode` do bloco de proveniência diz se a origem foi `live` ou `cache`.',
    ),
  ],
}

export const PROVENIENCIA: PaginaDoc = {
  id: 'proveniencia',
  titulo: 'Proveniência de cada número',
  grupo: GRUPO,
  resumo: 'O envelope que acompanha cada resposta da API, campo por campo, e o manifesto de cache.',
  secoes: [
    secao(
      'A regra',
      aviso(
        'nota',
        'Obrigatório, não opcional',
        'Toda resposta da API do protótipo carrega o envelope `provenance`. Ele é montado pela camada de API, não pelo autor da rota: não há como publicar número sem origem.',
      ),
    ),
    secao(
      'Forma do envelope',
      codigo(
        [
          '{',
          '  "ok": true,',
          '  "mode": "live",',
          '  "data": { "...": "o conteúdo da rota" },',
          '  "provenance": [',
          '    {',
          '      "dataset": "balanco-energia-subsistema",',
          '      "resource": "BALANCO_ENERGIA_SUBSISTEMA_2026_09.csv",',
          '      "mode": "live",',
          '      "rows": 17544,',
          '      "bytes_read": 2841600,',
          '      "fetched_at": "2026-09-14T11:22:05Z",',
          '      "lag_note": "publicação com defasagem típica de 1 dia"',
          '    }',
          '  ],',
          '  "notes": ["..."]',
          '}',
        ].join('\n'),
      ),
      'Exemplo ilustrativo da forma (os valores de uma resposta real aparecem no bloco de proveniência de cada tela).',
    ),
    secao(
      'Campo por campo',
      tabela(
        ['Campo', 'O que significa'],
        [
          ['`dataset`', 'identificador do conjunto no Portal de Dados Abertos do ONS'],
          ['`resource`', 'recurso específico, em geral o arquivo de um ano/mês'],
          ['`mode`', '`live`, `cache` ou `demo`, **por recurso**: uma resposta pode misturar carga do cache com restrição ao vivo'],
          ['`rows`', 'linhas efetivamente lidas; uma queda brusca é o primeiro sinal de que a publicação mudou de formato'],
          ['`bytes_read`', 'volume lido; o protótipo usa requisições HTTP `Range` para não baixar arquivos inteiros'],
          ['`fetched_at`', 'instante da extração, em UTC'],
          ['`lag_note`', '**defasagem conhecida da publicação**: impede confundir "o dado não existe" com "ainda não foi publicado"; vazio quando não é conhecida (nunca estimada)'],
        ],
      ),
    ),
    secao(
      'Os três modos',
      tabela(
        ['Modo', 'Origem', 'Quando ocorre'],
        [
          ['`live`', 'Portal de Dados Abertos do ONS, agora', 'rede disponível'],
          ['`cache`', '`.cache/` local, com hash registrado', 'sem rede, com extração anterior'],
          ['`demo`', 'gerador determinístico', 'sem rede e sem cache, ou `ORACULO_OFFLINE=1`'],
        ],
      ),
      aviso('limite', 'Modo demo', 'Em modo `demo` nenhum número da sessão deve ser citado como resultado.'),
    ),
    secao(
      'O manifesto de cache',
      'Todo recurso baixado entra em `.cache/` e é registrado em `manifest.json` com hash SHA-256 do conteúdo, tamanho em bytes, instante de extração e URL de origem. A tela [[dados]] mostra o manifesto completo.',
      aviso(
        'medido',
        'Por que o hash importa',
        'Responde a uma pergunta que costuma ficar sem resposta: *este número mudou porque o modelo mudou, ou porque o dado mudou?* Se o hash do recurso é o mesmo, o dado é o mesmo, e a diferença está no código.',
      ),
    ),
    secao(
      'No dashboard do contrato',
      'As telas do grupo Dashboard do contrato não usam o envelope: leem a última publicação do `run_heavywork.py` no banco (tabelas `execucao` e `recurso`). A origem aparece na topbar (data do "agora" publicado). A rastreabilidade de um alerta até o conjunto de dados de origem está em [[detalhe-alerta]].',
    ),
    secao(
      'Os conjuntos do ONS usados pelo protótipo',
      tabela(
        ['Conjunto', 'Granularidade', 'Uso'],
        [
          ['`balanco-energia-subsistema`', 'horária, por subsistema', 'carga verificada e geração por fonte, a espinha dorsal'],
          ['`curva-carga`', 'horária, por subsistema', 'conferência cruzada da carga'],
          ['`restricao_coff_fotovoltaica`', 'semi-horária, por usina', 'rótulo do risco de curtailment'],
          ['`restricao_coff_eolica_usi`', 'semi-horária, por usina', 'rótulo, fonte eólica'],
          ['`subestacao`', 'cadastral, por subestação', 'subestações georreferenciadas, entrada do Mapa Inteligente'],
          ['`capacidade-transformacao`', 'cadastral, por transformador', 'área de influência e identificação da fronteira T–D'],
          ['`modalidade-usina`', 'cadastral, por usina', 'usinas Tipo III conectadas à distribuição'],
        ],
      ),
    ),
  ],
}

export const LIMITACOES_PAGINA: PaginaDoc = {
  id: 'limitacoes',
  titulo: 'Limitações declaradas',
  grupo: GRUPO,
  resumo: 'Tudo o que a solução não faz ou não afirma, com a consequência de cada limite.',
  secoes: [
    secao(
      'Por que esta página existe',
      aviso(
        'nota',
        'Todo limite é declarado antes de ser perguntado',
        'Uma limitação descoberta pelo avaliador custa credibilidade; a mesma limitação declarada pelo autor demonstra domínio do problema. Cada limite desta página também aparece na tela correspondente (nota de cartão ou faixa de aviso) e no payload da API (`aviso`, `nota`, `sample_adequacy`, `available`).',
      ),
    ),
    secao(
      'Fronteiras de escopo',
      tabela(
        ['Limite', 'Consequência'],
        LIMITES_SOLUCAO.map((l) => [`**${l.titulo}**`, l.detalhe]),
      ),
    ),
    secao(
      'Limites dos dados',
      tabela(
        ['Limite', 'Consequência'],
        LIMITACOES.map((l) => [`**${l.titulo}**`, l.detalhe]),
      ),
    ),
    secao(
      'Núcleo analítico (telas do protótipo)',
      tabela(
        ['#', 'Limitação', 'Consequência'],
        [
          ['L1', '**A MMGD é estimada, não medida.** O método do envelope usa o percentil 90 da carga em horas comparáveis como aproximação da carga global.', 'a estimativa é **um piso, não um valor central**: mesmo os dias de maior carga contêm alguma geração distribuída'],
          ['L2', '**Não existe série horária de MMGD por área** no Portal.', 'não há como validar a estimativa contra medição; a validação é indireta, por coerência com a capacidade instalada declarada'],
          ['L3', '**Os perfis por dia-tipo são por subsistema.**', 'granularidade abaixo disso exige BDGD'],
          ['L4', '**O rótulo de curtailment é a decisão operativa observada**, não o potencial físico.', 'a ferramenta aprende quando houve restrição registrada, não quanta energia teria sido gerada'],
          ['L5', '**O classificador do protótipo opera só na janela solar**, com limiar de rótulo de 10% da capacidade.', 'fora dela a resposta é trivial, e incluí-la inflaria a AUC sem informar'],
          ['L6', '**O desempenho publicado é do conjunto de teste corrente.**', 'janela de dados diferente, número diferente'],
          ['L7', '**A severidade embute ponderação de criticidade de área**, que é premissa.', 'não é medição; está declarada em `Backend/oraculo/config.py`'],
        ],
      ),
    ),
    secao(
      'Mapa Inteligente e visão computacional',
      tabela(
        ['#', 'Limitação', 'Consequência'],
        [
          ['R1', '**O banco de ensaio usa ortoimagem sintética** (com verdade fundamental). Na imagem de satélite real não há verdade fundamental.', 'as métricas do banco de ensaio são um **teto**, não promessa de campo; em imagem real, esperar degradação'],
          ['R2', '**Subestação de distribuição exige BDGD.** O dado aberto do ONS cobre a rede de operação.', 'fora da área piloto (RJ) o recorte é a fronteira T–D'],
          ['R3', '**Não existe curva de carga por subestação em dado aberto.**', 'a decomposição por classe roda por subsistema e entra como prior regional'],
          ['R4', '**Industrial não é afirmado pelo cadastro.**', 'o rótulo industrial vem só da morfologia; exige BDGD ou a Pesquisa de Posse e Hábitos de Consumo'],
          ['R5', '**Variância de amostragem alta** onde as edificações são poucas e grandes.', 'o payload reporta `sample_adequacy` (boa / limitada / insuficiente)'],
          ['R6', '**A calibração de área foi medida em imagem sintética.**', 'precisa ser remedida contra conjunto rotulado real'],
          ['R7', '**O backend YOLOv8-seg depende de runtime e pesos.**', 'sem eles, o adaptador declara a ausência na API e na tela e o detector clássico assume'],
        ],
      ),
    ),
    secao(
      'Modelo de Carga Composta',
      tabela(
        ['#', 'Limitação', 'Consequência'],
        [
          ['C1', '**Nada simula o CLM no tempo.** São as relações algébricas e a lógica de proteção.', 'a resposta transitória é do ORGANON'],
          ['C2', '**A composição por classe é premissa versionada**, não medição de uso final.', 'calibração pede o guia da NERC e a Pesquisa de Posse e Hábitos'],
          ['C3', '**29 dos 124 campos não são afirmados.**', 'aparecem com o valor de referência publicado e o rótulo *a calibrar*'],
          ['C4', '**A penetração de ar-condicionado brasileira é desconhecida aqui.**', 'a tela expõe a sensibilidade de `Fmd` em vez de fixar um número'],
          ['C5', '**`Rfdr`/`Xfdr` saem de um proxy de comprimento.**', 'ponto de partida; as ferramentas reajustam na inicialização'],
          ['C7', '**O CMPLDW não representa dinâmica de inversor.**', 'a MMGD entra como injeção; o comportamento dinâmico exige DER_A'],
          ['C8', '**O cartão não é caso pronto para simulação.**', 'está escrito no próprio cartão, na tela e no payload'],
        ],
      ),
    ),
    secao(
      'Fontes que resolveriam o que falta',
      tabela(
        ['Fonte', 'Resolve', 'Como obter'],
        [
          ['BDGD de outras distribuidoras', 'R2, R3, R4, C5 fora do RJ', 'dado aberto da ANEEL, ingestão por área piloto'],
          ['IBGE — Pesquisa de Posse e Hábitos de Consumo', 'R4, C2, C4', 'citada no próprio enunciado do desafio'],
          ['NERC — guia de composição de carga', 'C2', 'acesso manual ao PDF (o servidor nega acesso automatizado)'],
          ['Ortoimagem submétrica rotulada e pesos YOLO ajustados', 'R1, R6, R7', 'contrato de imagem e gabarito da área piloto'],
          ['Oscilografia de perturbação real', 'C3', 'a perturbação de 15/08/2023 é o caso natural'],
        ],
      ),
    ),
  ],
}

export const GLOSSARIO: PaginaDoc = {
  id: 'glossario',
  titulo: 'Glossário',
  grupo: GRUPO,
  resumo: 'Termos técnicos, siglas e códigos usados nas telas.',
  secoes: [
    secao(
      'Termos',
      tabela(
        ['Termo', 'Significado'],
        [
          ['average precision (AP)', 'área sob a curva precisão × revocação; integra todos os limiares, por isso é mais severa que o F1 medido num único ponto de operação'],
          ['backtest', 'avaliação do modelo em dados posteriores ao treino, com corte estritamente cronológico; ver [[validacao]]'],
          ['baseline', 'modelo simples de referência (persistência, sazonal-ingênuo, climatologia) avaliado no mesmo conjunto de teste; um modelo que não o supera não é promovido'],
          ['BDGD', 'Base de Dados Geográfica da Distribuidora (ANEEL): topologia, transformadores, alimentadores, unidades consumidoras e geradoras; publicada uma vez por ano'],
          ['BESS', '*Battery Energy Storage System*, armazenamento em baterias; ver [[bess]]'],
          ['carga global', 'toda a demanda, inclusive a atendida por geração que o ONS não supervisiona'],
          ['carga supervisionada', 'carga global − MMGD estimada: a carga que o ONS opera; resolução de 30 min, por subsistema'],
          ['CKAN', 'plataforma de catálogo usada pelo Portal de Dados Abertos do ONS; a ingestão consulta sua API'],
          ['CLM / CMPLDW', '*Composite Load Model*, o Modelo de Carga Composta; CMPLDW é a designação no GE PSLF (`CMLDxxU2` no PSS/E); ver [[clm]]'],
          ['constrained-off / curtailment', 'redução de geração determinada pelo Operador; termos equivalentes na regulação brasileira'],
          ['DER_A', 'família de modelos dinâmicos de recurso distribuído (resposta de inversor a subtensão e frequência, anti-ilhamento): o que o CMPLDW não faz'],
          ['dia-tipo', 'útil, sábado, domingo ou feriado; feriado é tratado como domingo'],
          ['embargo', 'intervalo descartado entre treino e teste no backtest, para que variáveis defasadas não cruzem a fronteira'],
          ['ENE, CNF, REL, PAR', 'códigos de razão do constrained-off no ONS; ver [[curtailment]]'],
          ['envelope (método do)', 'estimador do fator de nebulosidade: o percentil 90 da carga em horas comparáveis aproxima a carga global; produz estimativa conservadora (um piso)'],
          ['área de influência', 'polígono de atendimento de uma subestação da BDGD (antes chamado de "mancha"); juntos cobrem o estado sem sobreposição'],
          ['fator de carga', 'razão entre carga média e carga de pico; perto de 1, curva plana (assinatura industrial)'],
          ['fronteira T–D', 'transformação cujo secundário é de tensão de distribuição (≤ 138 kV); recorte que o dado aberto do ONS permite identificar'],
          ['IoU', '*Intersection over Union*: sobreposição entre máscara detectada e verdadeira; mede geometria, não só existência'],
          ['lag de sistema', 'MMGD homologada na ANEEL e ainda ausente da BDGD (base anual): atraso administrativo, não irregularidade'],
          ['MMGD', 'micro e minigeração distribuída, sobretudo solar em telhados'],
          ['modo replay', 'a demo publica previsões de um "agora" passado já conhecido, para mostrar o que o sistema teria dito'],
          ['MWmed', 'megawatt médio no intervalo de integração'],
          ['NMS', '*Non-Maximum Suppression*: elimina detecções redundantes'],
          ['NNLS', '*Non-Negative Least Squares*: usado na decomposição da curva em classes, porque peso negativo não tem interpretação'],
          ['ORGANON', 'ferramenta de avaliação de segurança dinâmica usada pelo ONS; destino declarado da parametrização do CLM'],
          ['P10, P50, P90', 'quantis da previsão; 80% dos valores reais devem cair entre P10 e P90'],
          ['patamar', 'faixa horária com custo de erro distinto; ver [[como-ler]]'],
          ['perda assimétrica', 'perda *pinball* com pesos diferentes para subestimar e superestimar, por patamar'],
          ['pinball loss', 'perda da regressão quantílica'],
          ['SED', 'subestação de distribuição (na BDGD); ver [[fronteira]]'],
          ['SHAP', 'decomposição da previsão em contribuições por variável; ver [[detalhe-alerta]]'],
          ['skill score', 'ganho relativo de erro frente ao melhor baseline; negativo aparece em vermelho'],
          ['Tipo III', 'usina conectada à rede de distribuição, no conjunto `modalidade-usina` do ONS'],
          ['TSO / DSO', 'operador da transmissão (ONS) / operador da distribuição'],
          ['UVLS, UFLS', 'corte de carga por subtensão e por subfrequência, representados no CLM'],
          ['Vstall / Vstallbrk', 'tensão de travamento do compressor monofásico / tensão em que a curva de rotor bloqueado cruza a de regime; a posição relativa das duas muda o resultado'],
          ['YOLOv8-seg', 'modelo de detecção e segmentação usado na visão computacional'],
          ['ZIP', 'carga estática como combinação de impedância, corrente e potência constantes'],
        ],
      ),
    ),
  ],
}

export const PAGINAS_GERAIS: PaginaDoc[] = [INICIO, COMO_LER, PROVENIENCIA, LIMITACOES_PAGINA, GLOSSARIO]
