/**
 * Metodologia: como o O.R.A.C.U.L.O. chega aos números das outras telas — fontes, os dois
 * produtos (carga supervisionada e risco de curtailment), a auditoria da MMGD em 3 camadas,
 * a validação e os limites declarados.
 *
 * Conteúdo alinhado aos PDFs do time (planejamento v2 e pitch final). Decisões:
 * - Texto de produto é fixo (não é dado). O que É dado vem de fonte rastreável: patamares e
 *   faixas horárias de Backend/config/processamento.yaml (content/calendario.ts), horizontes do
 *   schema do contrato, modelo avaliado e períodos do split da API (getValidacao).
 * - Os números do PAR/PEL 2025 aparecem só com a fonte citada ao lado.
 * - NÃO veio do Figma a tela "Extrapolação de tendências" (perfil horário e fatores de
 *   crescimento por ano sem fonte): mostrá-la seria apresentar número inventado como do ONS.
 * - Cada bloco diz em que estado está (em operação / em desenvolvimento), para a tela nunca
 *   prometer o que ainda não roda (pitch, slide 11: "nenhuma promessa de desempenho sem teste").
 *   Fonte do estado: docs/FASES.md — atualizar ESTADO abaixo quando uma fase fechar.
 */
import type { ReactNode } from 'react'
import { ExternalLink } from 'lucide-react'
import { Card } from '../components/ui/Card'
import { ListaLimitacoes } from '../components/ui/ListaLimitacoes'
import { MockTag } from '../components/ui/MockTag'
import { RazaoBadge } from '../components/ui/RazaoBadge'
import { FAIXAS_CURTAILMENT, formatIntervalo, PATAMARES } from '../content/calendario'
import { LIMITACOES, LIMITES_SOLUCAO } from '../content/limitacoes'
import { getValidacao } from '../data/dataSource'
import { HorizonteSchema } from '../data/types'
import { useDados } from '../data/useDados'
import { RAZAO_INFO } from '../theme/razao'

/** Estado de implementação de cada peça (espelho de docs/FASES.md em 2026-09-26). */
type Estado = 'em operação' | 'em desenvolvimento'
const ESTILO_ESTADO: Record<Estado, string> = {
  'em operação': 'border-risk-low/40 bg-risk-low/10 text-risk-low',
  'em desenvolvimento': 'border-risk-medium/40 bg-risk-medium/10 text-risk-medium',
}

/** Pitch, slide 8: cinco fontes → três evidências → dois produtos. */
const FONTES: readonly [string, string][] = [
  ['ONS', 'séries operativas, carga verificada e constrained-off (bases tm)'],
  ['Medições', 'fronteiras e séries elétricas'],
  ['Meteorologia', 'ERA5 para treino e backtest; previsão numérica em operação'],
  ['Satélite', 'presença física e distribuição espacial dos painéis'],
  ['BDGD + ANEEL', 'topologia da distribuição e cadastro de MMGD'],
]
const EVIDENCIAS: readonly [string, string][] = [
  ['Realidade física', 'satélite + visão computacional: o painel existe e onde está?'],
  ['Topologia', 'BDGD: a que alimentador e transformador a unidade se liga?'],
  ['Cadastro', 'ANEEL (atualização diária): foi homologada, e quando?'],
]

/**
 * PAR/PEL 2025 (ONS), projeção 2026–2029, base PEN/PMO + MMGD 4MD: % do tempo com corte e
 * maior corte por faixa horária — a mesma divisão das faixas do projeto. Chave = rótulo da
 * faixa em processamento.yaml; faixa sem correspondência mostra "—" (nunca um número chutado).
 */
const PARPEL_POR_FAIXA: Record<string, { tempoPct: string; maiorGw: string }> = {
  '00-07': { tempoPct: '2,9%', maiorGw: '10 GW' },
  '07-09|16-18': { tempoPct: '37,6%', maiorGw: '42 GW' },
  '09-16': { tempoPct: '74,9%', maiorGw: '52 GW' },
  '18-24': { tempoPct: '2,4%', maiorGw: '8 GW' },
}

const REFERENCIAS: readonly { nome: string; url?: string }[] = [
  { nome: 'ONS · PAR/PEL 2025 — Sumário Executivo', url: 'https://www.ons.org.br/Paginas/energia-no-futuro/suprimentoeletrico/parpel2025/sumario-executivo/index.aspx' },
  { nome: 'ONS · Portal de Dados Abertos', url: 'https://dados.ons.org.br/' },
  { nome: 'ONS · FAQ Curtailment', url: 'https://www.ons.org.br/Paginas/faq_curtailment.aspx' },
  { nome: 'WECC · Composite Load Model Specification' },
  { nome: 'ANEEL · AIR nº 2022-002/SRG (curtailment ≡ constrained-off)' },
]

export default function Metodologia() {
  return (
    <div className="space-y-4">
      <FaixaResumo />
      <Triangulacao />
      <div className="grid gap-4 xl:grid-cols-2">
        <ProdutoCarga />
        <ProdutoCurtailment />
      </div>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Auditoria />
        <Validacao />
      </div>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Card title="Limites declarados">
          <div className="grid gap-6 md:grid-cols-2">
            <div>
              <p className="rotulo mb-3 text-[10px]">Dos dados</p>
              <ListaLimitacoes itens={LIMITACOES} />
            </div>
            <div>
              <p className="rotulo mb-3 text-[10px]">Do escopo</p>
              <ListaLimitacoes itens={LIMITES_SOLUCAO} inicio={LIMITACOES.length + 1} />
            </div>
          </div>
        </Card>
        <Referencias />
      </div>
    </div>
  )
}

/** Faixa de fatos da solução (horizontes do schema; cadência do planejamento v2). */
function FaixaResumo() {
  const fatos: [string, string][] = [
    ['Horizontes', HorizonteSchema.options.join(' · ')],
    ['Quantis', 'P10 · P50 · P90'],
    ['Resolução e cadência', '30 min'],
    ['Recorte', 'subsistema + área de concessão'],
  ]
  return (
    <section aria-label="Resumo" className="grid border border-line bg-surface sm:grid-cols-2 xl:grid-cols-4">
      {fatos.map(([k, v]) => (
        <div key={k} className="border-b border-line/60 px-4 py-3 last:border-b-0 sm:border-r xl:border-b-0 xl:last:border-r-0">
          <p className="rotulo text-[10px]">{k}</p>
          <p className="kpi mt-1 text-[15px] font-semibold text-accent">{v}</p>
        </div>
      ))}
    </section>
  )
}

function Triangulacao() {
  return (
    <Card title="Cinco fontes · três evidências · dois produtos">
      <div className="grid items-stretch gap-4 lg:grid-cols-[1fr_auto_1fr_auto_1fr]">
        <Coluna titulo="Fontes integradas">
          {FONTES.map(([k, v]) => (
            <Item key={k} titulo={k} texto={v} />
          ))}
        </Coluna>
        <Seta />
        <Coluna titulo="Triangulação">
          {EVIDENCIAS.map(([k, v], i) => (
            <Item key={k} titulo={`${i + 1} · ${k}`} texto={v} />
          ))}
        </Coluna>
        <Seta />
        <Coluna titulo="Produtos">
          <Item destaque titulo="Produto 1 · Carga supervisionada e MMGD estimada" texto="Desafio 2 — demanda, clima e operação" />
          <Item destaque titulo="Produto 2 · Risco de curtailment por razão" texto="Desafio 1 — curtailment (foco na razão energética)" />
        </Coluna>
      </div>
      <p className="mt-4 border-t border-line pt-3 text-xs text-ink-muted">
        O ganho não vem de uma base isolada, mas do cruzamento: os dois produtos dependem da mesma grandeza hoje pouco
        visível ao ONS — quanto a MMGD gera, em que ponto da rede de distribuição, na próxima meia hora.
      </p>
    </Card>
  )
}

function Coluna({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div>
      <p className="rotulo mb-2 text-[10px]">{titulo}</p>
      <ul className="space-y-2">{children}</ul>
    </div>
  )
}

function Item({ titulo, texto, destaque = false }: { titulo: string; texto: string; destaque?: boolean }) {
  return (
    <li className={`border px-3 py-2 ${destaque ? 'border-accent/40 bg-accent/5' : 'border-line bg-fundo'}`}>
      <p className={`text-body font-medium ${destaque ? 'text-accent' : 'text-ink'}`}>{titulo}</p>
      <p className="text-xs text-ink-muted">{texto}</p>
    </li>
  )
}

function Seta() {
  return (
    <div className="hidden items-center font-mono text-lg text-ink-faint lg:flex" aria-hidden>
      →
    </div>
  )
}

function Etapa({ titulo, estado, children }: { titulo: string; estado?: Estado; children: ReactNode }) {
  return (
    <li className="border-l-2 border-line pl-3">
      <p className="flex flex-wrap items-center gap-2 text-body font-medium text-ink">
        {titulo}
        {estado && (
          <span className={`border px-1.5 font-mono text-[10px] uppercase tracking-wider ${ESTILO_ESTADO[estado]}`}>{estado}</span>
        )}
      </p>
      <div className="mt-0.5 text-xs text-ink-muted">{children}</div>
    </li>
  )
}

function ProdutoCarga() {
  return (
    <Card title="Produto 1 · Carga supervisionada (Desafio 2)" accent="border-t-chart-1">
      <p className="kpi mb-4 border border-line bg-fundo px-3 py-2 text-center text-sm text-ink">
        carga global − MMGD estimada = <span className="text-accent">carga supervisionada</span>
      </p>
      <ol className="space-y-3">
        <Etapa titulo="Série alvo" estado="em operação">
          Carga global e MMGD estimada do ONS, 30 min, por subsistema e SIN. Feriados tratados como domingo; Dia dos Pais
          com marcação própria.
        </Etapa>
        <Etapa titulo="Baselines obrigatórios" estado="em operação">
          Persistência, sazonal-naïve (mesmo horário do dia e da semana anteriores) e climatologia — sem baseline, nenhum
          número de acurácia significa nada.
        </Etapa>
        <Etapa titulo="Gradient boosting quantílico" estado="em operação">
          LightGBM por quantil (P10/P50/P90) com banda calibrada por conformal (CQR), um modelo por série e horizonte.
        </Etapa>
        <Etapa titulo="Temporal Fusion Transformer com perda assimétrica" estado="em desenvolvimento">
          Pinball ponderada por patamar: penaliza mais subestimar a ponta e superestimar a mínima.
        </Etapa>
      </ol>

      <p className="rotulo mt-5 mb-2 text-[10px]">Patamares da curva (config do Backend)</p>
      <table className="w-full text-xs">
        <tbody>
          {PATAMARES.map((p) => (
            <tr key={p.chave} className="border-t border-line/60 align-top">
              <td className="py-1.5 pr-3 text-body text-ink">{p.nome}</td>
              <td className="kpi py-1.5 pr-3 whitespace-nowrap text-ink-muted">{formatIntervalo(p.horas)}</td>
              <td className="py-1.5 text-ink-muted">pior erro: {p.errarPior}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

function ProdutoCurtailment() {
  return (
    <Card title="Produto 2 · Risco de curtailment (Desafio 1)" accent="border-t-chart-2">
      <p className="mb-4 flex flex-wrap items-center gap-2 text-xs text-ink-muted">
        Razões do dicionário do ONS:
        {(Object.keys(RAZAO_INFO) as (keyof typeof RAZAO_INFO)[]).map((r) => (
          <span key={r} className="inline-flex items-center gap-1.5">
            <RazaoBadge razao={r} /> {RAZAO_INFO[r].nome.toLowerCase()}
          </span>
        ))}
      </p>
      <ol className="space-y-3">
        <Etapa titulo="Rótulo" estado="em operação">
          Bases tm de constrained-off do ONS (eólica e fotovoltaica), chave composta fonte + id. Curtailment e
          constrained-off são equivalentes na regulação brasileira.
        </Etapa>
        <Etapa titulo="Classificação probabilística por razão" estado="em operação">
          ENE e CNF separadas: pedem respostas operativas diferentes. Desde abr/2025 a razão energética supera as demais
          (PAR/PEL 2025) e não é ressarcida.
        </Etapa>
        <Etapa titulo="Montante esperado" estado="em operação">
          P(corte) × E[MW | corte], por usina/conjunto e horizonte.
        </Etapa>
        <Etapa titulo="Explicabilidade glass box" estado="em operação">
          Contribuição de cada variável (SHAP do LightGBM), peso por razão e dataset de origem em cada alerta.
        </Etapa>
      </ol>

      <p className="rotulo mt-5 mb-2 text-[10px]">Faixas horárias de curtailment · projeção ONS 2026–2029</p>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-ink-faint">
            <th className="py-1 pr-3 font-normal">Faixa</th>
            <th className="py-1 pr-3 text-right font-normal">% do tempo com corte</th>
            <th className="py-1 text-right font-normal">Maior corte</th>
          </tr>
        </thead>
        <tbody>
          {FAIXAS_CURTAILMENT.map((f) => {
            const parpel = PARPEL_POR_FAIXA[f.rotulo]
            return (
              <tr key={f.rotulo} className="kpi border-t border-line/60">
                <td className="py-1.5 pr-3 text-ink">{f.intervalos.map(formatIntervalo).join(' e ')}</td>
                <td className="py-1.5 pr-3 text-right text-ink">{parpel?.tempoPct ?? '—'}</td>
                <td className="py-1.5 text-right text-ink-muted">{parpel?.maiorGw ?? '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="mt-2 text-[11px] text-ink-faint">Fonte: ONS, PAR/PEL 2025 (base PEN/PMO + MMGD 4MD).</p>
    </Card>
  )
}

function Auditoria() {
  return (
    <Card
      title="Auditoria da MMGD em 3 camadas · fator de correção"
      actions={<span className={`border px-1.5 font-mono text-[10px] uppercase tracking-wider ${ESTILO_ESTADO['em desenvolvimento']}`}>em desenvolvimento</span>}
    >
      <ol className="grid gap-3 md:grid-cols-3">
        {[
          ['1 · Realidade física', 'Segmentação de painéis em imagem de satélite (YOLOv8-seg) dentro das manchas da rede.', 'periódica (meses)'],
          ['2 · Topologia', 'BDGD liga a unidade ao alimentador/transformador.', 'anual'],
          ['3 · Cadastro', 'Planilha de empreendimentos de GD da ANEEL: homologação e data.', 'diária'],
        ].map(([t, d, c]) => (
          <li key={t} className="border border-line bg-fundo px-3 py-2">
            <p className="text-body font-medium text-ink">{t}</p>
            <p className="mt-0.5 text-xs text-ink-muted">{d}</p>
            <p className="kpi mt-1.5 text-[10px] uppercase tracking-wider text-ink-faint">atualização {c}</p>
          </li>
        ))}
      </ol>
      <p className="rotulo mt-4 mb-2 text-[10px]">Desempate de um painel detectado que não está na BDGD</p>
      <ul className="space-y-1.5 text-xs">
        <li className="flex gap-2">
          <span className="kpi shrink-0 text-risk-low">→ Lag de sistema</span>
          <span className="text-ink-muted">consta na ANEEL com homologação recente: MMGD legítima com defasagem administrativa; entra no fator de correção.</span>
        </li>
        <li className="flex gap-2">
          <span className="kpi shrink-0 text-risk-high">→ Não homologada</span>
          <span className="text-ink-muted">ausente nas duas bases: escalada como exceção, fora do fator (não é incorporada em silêncio à previsão).</span>
        </li>
      </ul>
      <p className="kpi mt-3 border-t border-line pt-3 text-xs text-ink">
        fator de correção (mancha) = capacidade auditada ÷ capacidade cadastrada na BDGD
      </p>
    </Card>
  )
}

/** Validação: princípios fixos + o modelo e o split que a API está servindo agora. */
function Validacao() {
  const v = useDados(getValidacao)
  return (
    <Card title="Validação" actions={v.status === 'ok' ? <MockTag mock={v.data.mock} /> : undefined}>
      <ul className="space-y-2 text-xs text-ink-muted">
        <li>
          <span className="text-ink">Split sempre cronológico</span>, nunca aleatório, com testes que provam ausência de
          vazamento temporal.
        </li>
        <li>
          <span className="text-ink">Backtest fora da amostra</span> contra os baselines, por horizonte e por patamar.
        </li>
        <li>
          <span className="text-ink">Carga:</span> MAE, RMSE, MAPE, pinball, cobertura P10–P90, erro de pico, vale e rampa.
        </li>
        <li>
          <span className="text-ink">Curtailment:</span> ROC-AUC, PR-AUC, Brier, precisão/recall e erro de montante.
        </li>
      </ul>
      {v.status === 'ok' && (
        <dl className="kpi mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 border-t border-line pt-3 text-xs">
          <dt className="text-ink-faint">modelo avaliado</dt>
          <dd className="text-ink">{v.data.modelo.nome} · {v.data.modelo.versao}</dd>
          <dt className="text-ink-faint">treino</dt>
          <dd className="text-ink">{v.data.modelo.periodoTreino.inicio} → {v.data.modelo.periodoTreino.fim}</dd>
          <dt className="text-ink-faint">teste</dt>
          <dd className="text-ink">{v.data.modelo.periodoTeste.inicio} → {v.data.modelo.periodoTeste.fim}</dd>
        </dl>
      )}
      {v.status === 'erro' && <p className="mt-4 text-xs text-risk-critical">Modelo atual indisponível: {v.erro.message}</p>}
    </Card>
  )
}

function Referencias() {
  return (
    <Card title="Fontes técnicas">
      <ul className="space-y-2 text-body">
        {REFERENCIAS.map((r) => (
          <li key={r.nome}>
            {r.url ? (
              <a href={r.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-accent hover:underline">
                {r.nome} <ExternalLink className="size-3" aria-hidden />
              </a>
            ) : (
              <span className="text-ink-muted">{r.nome}</span>
            )}
          </li>
        ))}
      </ul>
    </Card>
  )
}
