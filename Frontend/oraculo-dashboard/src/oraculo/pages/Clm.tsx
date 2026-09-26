/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * Parametrização do Modelo de Carga Composta (CMPLDW). Porte de 02-PROTOTIPO/web/js/views/clm.js.
 * Estrutura, equações e cartão de parâmetros com procedência campo a campo.
 *
 * Entrega vinda da Fronteira T–D (o STATE.clmHandoff do protótipo): {subId, name, fonte: 'bdgd'}
 * lida de location.state ({clmHandoff} ou o próprio objeto) ou de usePersistido('oraculo.clmHandoff').
 */
import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Api, type Envelope } from '../api'
import { lineChart } from '../charts'
import { usePersistido } from '../estado'
import { esc, num, pct } from '../format'
import { BarRow, Chip, Conteudo, Grafico, Html, Kpi, OCard, Pagina, Proveniencia, StatLines, useApi } from '../ui'

type Dado = any

export interface ClmHandoff {
  subId: string
  name?: string
  fonte?: string
}

const ORIGIN_STYLE: Record<string, string> = {
  WECC: 'teal',
  REF: '',
  DERIVADO: 'green',
  PREMISSA: 'amber',
  A_CALIBRAR: 'crimson',
}
const ORIGIN_LABEL: Record<string, string> = {
  WECC: 'WECC',
  REF: 'referência',
  DERIVADO: 'derivado',
  PREMISSA: 'premissa',
  A_CALIBRAR: 'a calibrar',
}
const COMP_COLOR: Record<string, string> = {
  Fma: 'navy-2',
  Fmb: 'teal',
  Fmc: 'green',
  Fmd: 'crimson',
  Fel: 'purple',
  estatica: 'muted',
}

// Parâmetros que o protótipo mantinha fixos no estado local (sem controle na tela).
const MIX: Record<string, number> = { residencial: 0.55, comercial: 0.25, industrial: 0.12, rural: 0.08 }
const VD1 = 0.8
const VD2 = 0.7

function OriginChip({ origem }: { origem: string }) {
  const c = ORIGIN_STYLE[origem] === undefined ? '' : ORIGIN_STYLE[origem]
  return (
    <span className={'chip' + (c ? ' ' + c : '')} title={origem}>
      {ORIGIN_LABEL[origem] || origem}
    </span>
  )
}

function fmtVal(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v !== 'number') return String(v)
  if (v === 0) return '0'
  if (Math.abs(v) >= 100) return num(v, 2)
  if (Math.abs(v) >= 1) return num(v, 4)
  return num(v, 6)
}

// ------------------------------------------------------------- topologia
/* O ponto que costuma passar em branco: metade do efeito dinâmico do CLM vem da rede ENTRE o
   barramento de transmissão e o uso final. Vale um desenho, não um parágrafo. */
function topologyDiagram(topo: Dado): string {
  const comps: Dado[] = (topo && topo.componentes) || []
  const rowH = 26,
    top = 34
  const h = top + comps.length * rowH + 26
  let s = '<svg viewBox="0 0 640 ' + h + '" width="100%" height="' + h + '" role="img" aria-label="Topologia do CMPLDW" style="overflow:visible">'

  const xSys = 56,
    xLow = 232,
    xLoad = 392,
    xComp = 470
  const yBus0 = top - 14,
    yBus1 = top + comps.length * rowH - 6
  const mid = (yBus0 + yBus1) / 2

  function bus(x: number, label: string, sub: string) {
    let o = '<line x1="' + x + '" y1="' + yBus0 + '" x2="' + x + '" y2="' + yBus1 + '" stroke="var(--o-ink-2)" stroke-width="3"/>'
    o += '<text x="' + x + '" y="' + (yBus0 - 16) + '" text-anchor="middle" font-size="10.5" font-weight="600" fill="var(--o-ink)">' + esc(label) + '</text>'
    if (sub) {
      o += '<text x="' + x + '" y="' + (yBus0 - 5) + '" text-anchor="middle" font-size="9" fill="var(--o-muted)">' + esc(sub) + '</text>'
    }
    return o
  }

  s += bus(xSys, 'Barramento do sistema', '230 · 115 · 69 kV')
  s += bus(xLow, 'Barramento de baixa', 'criado na inicialização')
  s += bus(xLoad, 'Barramento de carga', 'extremidade do alimentador')

  // Transformador com comutação em carga.
  s += '<line x1="' + xSys + '" y1="' + mid + '" x2="' + xLow + '" y2="' + mid + '" stroke="var(--o-line-2)" stroke-width="1.6"/>'
  s += '<rect x="' + (xSys + 46) + '" y="' + (mid - 11) + '" width="42" height="22" rx="3" fill="var(--o-panel-2)" stroke="var(--o-teal)" stroke-width="1.4"/>'
  s += '<text x="' + (xSys + 67) + '" y="' + (mid + 4) + '" text-anchor="middle" font-size="9.5" fill="var(--o-teal)">jXxf</text>'
  s += '<text x="' + (xSys + 126) + '" y="' + (mid - 6) + '" text-anchor="middle" font-size="9" fill="var(--o-muted)">1:T</text>'
  s += '<text x="' + (xSys + 126) + '" y="' + (mid + 8) + '" text-anchor="middle" font-size="8.5" fill="var(--o-amber)">LTC</text>'

  // Alimentador.
  s += '<line x1="' + xLow + '" y1="' + mid + '" x2="' + xLoad + '" y2="' + mid + '" stroke="var(--o-line-2)" stroke-width="1.6"/>'
  s += '<rect x="' + (xLow + 44) + '" y="' + (mid - 11) + '" width="72" height="22" rx="3" fill="var(--o-panel-2)" stroke="var(--o-green)" stroke-width="1.4"/>'
  s += '<text x="' + (xLow + 80) + '" y="' + (mid + 4) + '" text-anchor="middle" font-size="9.5" fill="var(--o-green)">Rfdr + jXfdr</text>'

  // Shunts: Bss na baixa, Bfdr repartido pelas duas pontas.
  function shunt(x: number, label: string, cor: string) {
    let o = '<line x1="' + x + '" y1="' + (yBus1 + 2) + '" x2="' + x + '" y2="' + (yBus1 + 12) + '" stroke="' + cor + '" stroke-width="1.3"/>'
    o += '<line x1="' + (x - 7) + '" y1="' + (yBus1 + 12) + '" x2="' + (x + 7) + '" y2="' + (yBus1 + 12) + '" stroke="' + cor + '" stroke-width="1.8"/>'
    o += '<line x1="' + (x - 7) + '" y1="' + (yBus1 + 16) + '" x2="' + (x + 7) + '" y2="' + (yBus1 + 16) + '" stroke="' + cor + '" stroke-width="1.8"/>'
    o += '<text x="' + x + '" y="' + (yBus1 + 27) + '" text-anchor="middle" font-size="8.5" fill="' + cor + '">' + esc(label) + '</text>'
    return o
  }
  s += shunt(xLow, 'Bss', 'var(--o-amber)')
  s += shunt(xLow + 92, 'Fb·Bfdr', 'var(--o-muted)')
  s += shunt(xLoad - 16, '(1−Fb)·Bfdr', 'var(--o-muted)')

  // Os seis componentes.
  comps.forEach((c, i) => {
    const y = top + i * rowH
    const cor = c.tipo === 'monofasico' ? 'var(--o-crimson)' : c.tipo === 'trifasico' ? 'var(--o-navy-2)' : 'var(--o-purple)'
    s += '<line x1="' + xLoad + '" y1="' + y + '" x2="' + xComp + '" y2="' + y + '" stroke="var(--o-line-2)" stroke-width="1.2"/>'
    if (c.tipo === 'trifasico' || c.tipo === 'monofasico') {
      s += '<circle cx="' + (xComp + 10) + '" cy="' + y + '" r="9" fill="var(--o-panel-2)" stroke="' + cor + '" stroke-width="1.4"/>'
      s += '<text x="' + (xComp + 10) + '" y="' + (y + 3.5) + '" text-anchor="middle" font-size="9" fill="' + cor + '">M</text>'
    } else {
      s += '<rect x="' + (xComp + 1) + '" y="' + (y - 8) + '" width="18" height="16" rx="2" fill="var(--o-panel-2)" stroke="' + cor + '" stroke-width="1.4"/>'
    }
    s += '<text x="' + (xComp + 26) + '" y="' + (y + 3.5) + '" font-size="10" fill="var(--o-ink)">' + esc(c.nome) + '</text>'
    s += '<text x="' + (xComp + 26) + '" y="' + (y + 13) + '" font-size="8.5" fill="var(--o-muted)">' + esc(c.tipo) + '</text>'
  })

  // Injeção de geração distribuída no barramento de carga.
  s += '<text x="' + (xLoad - 4) + '" y="' + (yBus1 + 40) + '" text-anchor="end" font-size="9" fill="var(--o-green)">Pdg + jQdg (MMGD)</text>'
  s += '</svg>'
  return s
}

// -------------------------------------------------------------- tabelas
function ParamTable({ params }: { params: Dado[] }) {
  return (
    <div className="table-wrap scroll-y">
      <table>
        <thead>
          <tr>
            <th>campo</th>
            <th>valor</th>
            <th>referência</th>
            <th>un.</th>
            <th>procedência</th>
            <th>o que é</th>
          </tr>
        </thead>
        <tbody>
          {(params || []).map((p, i) => (
            <tr key={p.nome + '-' + i}>
              <td>
                <code>{p.nome}</code>
              </td>
              <td className="num">{fmtVal(p.valor)}</td>
              <td className="num muted small">{fmtVal(p.referencia)}</td>
              <td>{p.unidade}</td>
              <td>
                <OriginChip origem={p.origem} />
              </td>
              <td className="small muted">
                {p.descricao}
                {p.nota ? <span className="muted"> · {p.nota}</span> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function WecTable({ ex }: { ex: Dado }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>componente</th>
            <th>MW</th>
            <th>Mvar</th>
            <th>peso</th>
            <th>B calc.</th>
            <th>B publ.</th>
            <th>em serviço</th>
            <th>rem. calc.</th>
            <th>rem. publ.</th>
          </tr>
        </thead>
        <tbody>
          {(ex.linhas || []).map((l: Dado, i: number) => (
            <tr key={l.componente + '-' + i}>
              <td>{l.componente}</td>
              <td className="num">{num(l.mw, 0)}</td>
              <td className="num">{num(l.mvar, 0)}</td>
              <td className="num">{num(l.peso, 2)}</td>
              <td className="num">{num(l.admitancia_calculada, 4)}</td>
              <td className="num muted">{num(l.admitancia_publicada, 4)}</td>
              <td className="num">{num(l.fracao_em_servico, 2)}</td>
              <td className="num">{num(l.remanescente_calculada, 4)}</td>
              <td className="num muted">{num(l.remanescente_publicada, 4)}</td>
            </tr>
          ))}
          <tr>
            <td>
              <strong>total</strong>
            </td>
            <td />
            <td />
            <td />
            <td className="num">
              <strong>{num(ex.total_calculado, 4)}</strong>
            </td>
            <td className="num muted">{num(ex.total_publicado, 4)}</td>
            <td />
            <td className="num">
              <strong>{num(ex.remanescente_calculado, 4)}</strong>
            </td>
            <td className="num muted">{num(ex.remanescente_publicado, 4)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}

function CoherenceTable({ co }: { co: Dado }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>classe</th>
            <th>motora · CLM</th>
            <th>motora · Mapa</th>
            <th>desvio</th>
          </tr>
        </thead>
        <tbody>
          {((co && co.linhas) || []).map((l: Dado, i: number) => (
            <tr key={l.classe + '-' + i}>
              <td>{l.classe}</td>
              <td className="num">{pct(l.motora_clm, 1)}</td>
              <td className="num">{pct(l.motora_mapa, 1)}</td>
              <td className="num">{l.desvio === 0 ? '0' : num(l.desvio, 8)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CheckList({ items }: { items: Dado[] }) {
  return (
    <>
      {(items || []).map((c, i) => (
        <div key={c.nome + '-' + i}>
          <div className="stat-line">
            <span className="k">
              <span className={'chip ' + (c.ok ? 'green' : 'crimson')}>{c.ok ? 'confere' : 'falha'}</span> {c.nome}
            </span>
            <span className="v">{c.obtido}</span>
          </div>
          <div className="small muted" style={{ margin: '-2px 0 8px' }}>
            {c.porque}
          </div>
        </div>
      ))}
    </>
  )
}

const FR_KEYS = ['Fma', 'Fmb', 'Fmc', 'Fmd', 'Fel', 'estatica']
const FR_NOMES: Record<string, string> = {
  Fma: 'Motor A · trifásico',
  Fmb: 'Motor B · trifásico',
  Fmc: 'Motor C · trifásico',
  Fmd: 'Motor D · monofásico',
  Fel: 'Eletrônica',
  estatica: 'Estática',
}

function FractionBars({ fr }: { fr: Dado }) {
  return (
    <>
      {FR_KEYS.map((k) => (
        <BarRow key={k} label={FR_NOMES[k]} frac={fr[k] || 0} value={pct(fr[k] || 0, 1)} color={COMP_COLOR[k]} />
      ))}
    </>
  )
}

function ContributionTable({ fr }: { fr: Dado }) {
  const mix = fr.mix || {}
  const classes = Object.keys(mix).filter((c) => mix[c] > 0)
  const comps = ['Fma', 'Fmb', 'Fmc', 'Fmd', 'Fel']
  const contrib = fr.contribuicao || {}
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>componente</th>
            {classes.map((c) => (
              <th key={c}>{c}</th>
            ))}
            <th>total</th>
          </tr>
        </thead>
        <tbody>
          {comps.map((k) => (
            <tr key={k}>
              <td>
                <code>{k}</code>
              </td>
              {classes.map((c) => (
                <td key={c} className="num muted">
                  {pct((contrib[k] || {})[c] || 0, 1)}
                </td>
              ))}
              <td className="num">{pct(fr[k] || 0, 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Cursor: o valor exibido acompanha o arraste; a leitura só é refeita ao soltar (evento change). */
function Cursor({ rotulo, min, max, step, valor, largura, onCommit }: { rotulo: string; min: number; max: number; step: number; valor: number; largura: number; onCommit: (v: number) => void }) {
  const [v, setV] = useState(valor)
  const ref = useRef<HTMLInputElement>(null)
  const commit = useRef(onCommit)
  useEffect(() => {
    commit.current = onCommit
  }, [onCommit])
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const h = () => commit.current(parseFloat(el.value))
    el.addEventListener('change', h)
    return () => el.removeEventListener('change', h)
  }, [])
  return (
    <label className="chip" style={{ gap: 6 }}>
      {rotulo}
      <input ref={ref} type="range" min={min} max={max} step={step} value={v} style={{ width: largura }} onChange={(e) => setV(parseFloat(e.target.value))} />
      <span>{num(v, 2)}</span>
    </label>
  )
}

const vfmt = (v: unknown) => Number(v).toFixed(2)

// ----------------------------------------------------------------- tela
export default function Clm() {
  const [persistido, setHandoff] = usePersistido<ClmHandoff | null>('oraculo.clmHandoff', null)
  const location = useLocation()
  const navigate = useNavigate()
  const st = location.state as any
  const doLocal: ClmHandoff | null = st && (st.clmHandoff || (st.subId ? st : null))
  const handoff: ClmHandoff | null = doLocal || persistido
  const [subId, setSubId] = usePersistido('oraculo.clm.subId', '')
  const [subName, setSubName] = usePersistido('oraculo.clm.subName', '')
  const [fonte, setFonte] = usePersistido('oraculo.clm.fonte', '')
  const [acFactor, setAcFactor] = usePersistido('oraculo.clm.acFactor', 1)
  const [vstall, setVstall] = usePersistido('oraculo.clm.vstall', 0.6)
  const [frcel, setFrcel] = usePersistido('oraculo.clm.frcel', 0)
  const [block, setBlock] = usePersistido('oraculo.clm.block', 'fracoes')

  /* Entrega vinda da seção Fronteira T–D: SE escolhida lá, composição pela BDGD/ANEEL. */
  useEffect(() => {
    if (!handoff) return
    setSubId(handoff.subId)
    setSubName(handoff.name || handoff.subId)
    setFonte(handoff.fonte || '')
    setHandoff(null)
    // consome a entrega: não reaplicar ao voltar pelo histórico
    if (doLocal) navigate(location.pathname + location.search, { replace: true, state: null })
  }, [handoff, doLocal, location.pathname, location.search, navigate, setSubId, setSubName, setFonte, setHandoff])

  const estado = useApi(async () => {
    const [specBody, subsBody] = await Promise.all([Api.get('clm/spec'), Api.get('mapa/substations', { limit: 60 }).catch(() => null)])
    const q: Record<string, string | number> = {}
    if (subId) q.sub_id = subId
    if (subId && fonte) q.fonte = fonte
    q.ac_factor = acFactor
    if (!subId) Object.keys(MIX).forEach((k) => (q[k] = MIX[k]))
    const [cardBody, curvesBody, valBody] = await Promise.all([
      Api.get('clm/cartao', q),
      Api.get('clm/curvas', { vstall, vd1: VD1, vd2: VD2, frcel }),
      Api.get('clm/validacao'),
    ])
    return { specBody, subsBody, cardBody, curvesBody, valBody }
  }, [subId, fonte, acFactor, vstall, frcel])

  return (
    <Pagina>
      {handoff ? null : (
        <Conteudo estado={estado} texto="Montando o registro de parâmetros e as curvas do modelo…">
          {(r) => (
            <Corpo
              {...r}
              subId={subId}
              subName={subName}
              fonte={fonte}
              acFactor={acFactor}
              vstall={vstall}
              frcel={frcel}
              block={block}
              setBlock={setBlock}
              setSub={(id, nome) => {
                setSubId(id)
                setSubName(nome)
              }}
              setFonte={setFonte}
              setAcFactor={setAcFactor}
              setVstall={setVstall}
              setFrcel={setFrcel}
            />
          )}
        </Conteudo>
      )}
    </Pagina>
  )
}

function Corpo(p: {
  specBody: Envelope
  subsBody: Envelope | null
  cardBody: Envelope
  curvesBody: Envelope
  valBody: Envelope
  subId: string
  subName: string
  fonte: string
  acFactor: number
  vstall: number
  frcel: number
  block: string
  setBlock: (b: string) => void
  setSub: (id: string, nome: string) => void
  setFonte: (f: string) => void
  setAcFactor: (v: number) => void
  setVstall: (v: number) => void
  setFrcel: (v: number) => void
}) {
  const sp = p.specBody.data as Dado
  const card = p.cardBody.data as Dado
  const cv = p.curvesBody.data as Dado
  const val = p.valBody.data as Dado
  const lista: Dado[] = p.subsBody ? [...(((p.subsBody.data as Dado) || {}).rows || [])] : []
  /* A SE pode não estar entre as 60 do Mapa. */
  if (p.subId && !lista.some((s) => s.sub_id === p.subId)) {
    lista.unshift({ sub_id: p.subId, name: p.subName || p.subId, uf: '—' })
  }
  const fr = card.fracoes || {}
  const cob = card.cobertura || {}
  const blocos: Record<string, string> = card.blocos || {}
  const byBlock: Record<string, Dado[]> = {}
  ;(card.parametros || []).forEach((x: Dado) => {
    ;(byBlock[x.bloco] = byBlock[x.bloco] || []).push(x)
  })
  const blockKeys = Object.keys(blocos).filter((b) => byBlock[b])
  const blocoAtivo = byBlock[p.block] ? p.block : blockKeys[0]
  const sub = card.subestacao || {}
  const apl = card.aplicabilidade || {}
  const gd = card.geracao_distribuida || {}
  const ex = val.exemplo_wecc || {}
  const md = cv.motor_d || {}
  const fontes = card.fontes || {}

  return (
    <>
      <div className="note-strip">
        Cartão de parâmetros <strong>com procedência</strong>, não caso pronto para simulação. Destino: parametrização do CLM no <strong>ORGANON</strong> — os campos do CMPLDW são os mesmos em PSS/E,
        PSLF, PowerWorld e DSATools, e por isso o cartão é neutro. Os {cob.A_CALIBRAR || 0} campos marcados <em>a calibrar</em> trazem o valor do conjunto de referência publicado e{' '}
        <strong>não são afirmação desta ferramenta</strong>.
      </div>

      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Kpi label="Campos do modelo" value={num(sp.total_parametros, 0)} foot="registro completo do CMPLDW" />
        <Kpi label="Derivados de dado nosso" value={num(cob.DERIVADO || 0, 0)} foot="composição de classe e capacidade de fronteira" accent="green" />
        <Kpi label="Premissa versionada" value={num(cob.PREMISSA || 0, 0)} foot="hipótese declarada, com o motivo escrito" accent="amber" />
        <Kpi label="A calibrar" value={num(cob.A_CALIBRAR || 0, 0)} foot="exigem ensaio ou base cadastral" accent="crimson" />
      </div>

      <OCard
        title="Estrutura do modelo"
        note={
          <>
            Metade do efeito dinâmico do CLM vem da <strong>rede entre</strong> o barramento de transmissão e o uso final: é a impedância do transformador e do alimentador que faz a tensão no uso final
            cair mais do que a medida na subestação — e é o que leva o compressor a travar.
          </>
        }
      >
        <Html html={topologyDiagram(sp.topologia)} />
      </OCard>

      <div className="grid g-2-1" style={{ margin: '14px 0' }}>
        <OCard
          title="Composição da carga"
          hint={card.fonte_composicao}
          note={
            <>
              A soma das quatro frações de motor reproduz exatamente a fração motora que o Mapa Inteligente publica — as duas telas não podem divergir sobre a mesma grandeza. O cursor do{' '}
              <strong>motor D</strong> existe porque é o parâmetro mais consequente e o menos conhecido aqui: a penetração de ar condicionado no Brasil não é a do sudoeste norte-americano de onde vem o
              modelo.
            </>
          }
        >
          <div className="chips" style={{ marginBottom: 12 }}>
            <select
              className="chip clickable"
              style={{ minWidth: 220 }}
              value={p.subId}
              onChange={(e) => {
                const sel = e.target
                const opt = sel.options[sel.selectedIndex]
                p.setSub(sel.value, sel.value && opt ? (opt.textContent || '').split(' · ')[0] : '')
              }}
            >
              <option value="">Composição livre</option>
              {lista.map((s) => (
                <option key={s.sub_id} value={s.sub_id}>
                  {s.name} · {s.uf}
                </option>
              ))}
            </select>
            <Cursor key={'ac' + p.acFactor} rotulo="motor D ×" min={0} max={2} step={0.05} valor={p.acFactor} largura={92} onCommit={p.setAcFactor} />
          </div>
          {p.subId ? (
            <div className="chips" style={{ margin: '-4px 0 12px' }}>
              <span className="small muted" style={{ alignSelf: 'center' }}>
                composição por
              </span>
              <Chip on={!p.fonte} onClick={() => p.setFonte('')}>
                Mapa Inteligente
              </Chip>
              <Chip on={p.fonte === 'bdgd'} onClick={() => p.setFonte('bdgd')}>
                BDGD + SAMP (ANEEL)
              </Chip>
            </div>
          ) : null}
          <FractionBars fr={fr} />
          <div style={{ marginTop: 12 }}>
            <ContributionTable fr={fr} />
          </div>
        </OCard>

        <OCard title="Contexto e aplicabilidade" note="O CLM não deve ser aplicado a qualquer barra: carga pequena, tensão baixa ou relação P/Q desfavorável produzem erro de inicialização.">
          <StatLines
            pares={[
              ['subestação', sub.nome],
              ['UF · subsistema', String(sub.uf ?? '') + ' · ' + String(sub.subsistema ?? '')],
              ['MVA de fronteira', num(sub.mva_fronteira, 1)],
              ['secundário', num(sub.kv_secundario, 1) + ' kV'],
              ['raio de influência', num(sub.raio_km, 2) + ' km'],
              ['escala do alimentador', '×' + num(card.escala_alimentador, 3)],
              ['confiança da classe', sub.confianca],
              ['adequação da amostra', sub.adequacao_amostra],
            ]}
          />
          <div style={{ marginTop: 10 }}>
            {(apl.testes || []).map((t: Dado, i: number) => (
              <div className="stat-line" key={t.criterio + '-' + i}>
                <span className="k">
                  <span className={'chip ' + (t.ok ? 'green' : 'amber')}>{t.ok ? 'ok' : 'atenção'}</span> {t.criterio}
                </span>
                <span className="v">
                  {num(t.valor, 2)} · {t.limite}
                </span>
              </div>
            ))}
          </div>
        </OCard>
      </div>

      <OCard
        title="Cartão de parâmetros"
        hint="procedência campo a campo"
        note={
          <>
            <strong>derivado</strong> vem de dado que esta ferramenta observa · <strong>WECC</strong> está fixado na especificação · <strong>referência</strong> é o conjunto publicado em
            arXiv:1708.00939 · <strong>premissa</strong> é hipótese nossa, declarada · <strong>a calibrar</strong> não é afirmado.
          </>
        }
      >
        <div className="chips" style={{ marginBottom: 10 }}>
          {blockKeys.map((b) => (
            <Chip key={b} on={b === blocoAtivo} onClick={() => p.setBlock(b)}>
              {blocos[b]} · {byBlock[b].length}
            </Chip>
          ))}
        </div>
        <ParamTable params={blocoAtivo ? byBlock[blocoAtivo] : []} />
      </OCard>

      <div className="grid g2" style={{ margin: '14px 0' }}>
        <OCard
          title="Motor A, B e C: o que de fato os distingue"
          note={
            <>
              Não existe campo “tipo de equipamento” no CMPLDW. A diferença entre os três motores trifásicos está <strong>inteiramente</strong> em H e Etrq. A leitura de equipamento é a convencional da
              literatura, e está rotulada como tal — não é dado.
            </>
          }
        >
          <Grafico
            deps={[cv]}
            desenhar={(el) => {
              if (!cv.conjugado) return
              lineChart(el, {
                index: cv.conjugado.velocidade,
                height: 190,
                digits: 2,
                yLabel: 'Tm (pu)',
                zeroBase: true,
                xTicks: 7,
                formatTime: (w) => Number(w).toFixed(2),
                series: [
                  { label: 'Etrq = 0 · motor A', values: cv.conjugado.etrq_0, color: 'navy-2' },
                  { label: 'Etrq = 2 · motores B e C', values: cv.conjugado.etrq_2, color: 'green' },
                ],
              })
            }}
          />
          <div style={{ marginTop: 10 }}>
            {Object.keys(sp.motores_3f || {}).map((k) => {
              const m = sp.motores_3f[k]
              return (
                <div key={k}>
                  <div className="stat-line">
                    <span className="k">{blocos[k] || k}</span>
                    <span className="v">
                      H = {num(m.h, 1)} s · Etrq = {num(m.etrq, 0)}
                    </span>
                  </div>
                  <div className="small muted" style={{ margin: '-2px 0 6px' }}>
                    leitura convencional: {m.leitura}
                    {m.trip_uv ? ' · com desligamento por subtensão' : ' · sem desligamento por subtensão'}
                  </div>
                </div>
              )
            })}
          </div>
        </OCard>

        <OCard title="Carga estática" hint={'P1c=' + num((cv.estatica || {}).p1c, 2) + ' · P1e=' + num((cv.estatica || {}).p1e, 2)} note={(cv.estatica || {}).nota}>
          <Grafico
            deps={[cv]}
            desenhar={(el) => {
              if (!cv.estatica) return
              lineChart(el, {
                index: cv.tensao,
                height: 220,
                digits: 2,
                yLabel: 'fator de P e Q',
                formatTime: vfmt,
                xTicks: 9,
                series: [
                  { label: 'P / Po', values: cv.estatica.p, color: 'teal' },
                  { label: 'Q / Qo', values: cv.estatica.q, color: 'amber' },
                ],
              })
            }}
          />
        </OCard>
      </div>

      <OCard
        title="Motor D · compressor monofásico"
        hint="modelo por desempenho, obtido em ensaio de laboratório"
        note="É este o componente que governa a recuperação lenta de tensão: travado, o compressor vira um rotor bloqueado e passa a absorver reativo em vez de produzir trabalho."
      >
        <div className="grid g-2-1">
          <div>
            {/* Motor D: as duas características no mesmo eixo. O que importa é onde uma cruza a outra — é ali que o compressor trava. */}
            <Grafico
              deps={[cv]}
              desenhar={(el) => {
                if (!cv.motor_d) return
                const vs: number[] = cv.tensao || []
                const iBrk = vs.findIndex((v) => v >= md.vstallbrk)
                const iStall = vs.findIndex((v) => v >= md.vstall)
                lineChart(el, {
                  index: vs,
                  height: 250,
                  digits: 2,
                  yLabel: 'P (pu)',
                  formatTime: vfmt,
                  xTicks: 9,
                  zeroBase: true,
                  spans: [
                    { from: 0, to: Math.max(iBrk, 0), color: 'crimson', opacity: 0.07, label: 'abaixo de Vstallbrk' },
                    { from: Math.max(iStall, 0), to: Math.max(iStall, 0) + 1, color: 'amber', opacity: 0.9, label: 'Vstall' },
                  ],
                  series: [
                    { label: 'regime', values: md.regime_p, color: 'teal' },
                    { label: 'rotor bloqueado', values: md.travado_p, color: 'crimson', style: 'dash' },
                  ],
                })
              }}
            />
            <Grafico
              style={{ marginTop: 10 }}
              deps={[cv]}
              desenhar={(el) => {
                if (!cv.motor_d) return
                lineChart(el, {
                  index: cv.tensao,
                  height: 200,
                  digits: 2,
                  yLabel: 'Q (pu)',
                  formatTime: vfmt,
                  xTicks: 9,
                  series: [
                    { label: 'regime', values: md.regime_q, color: 'teal' },
                    { label: 'rotor bloqueado', values: md.travado_q, color: 'crimson', style: 'dash' },
                  ],
                })
              }}
            />
          </div>
          <div>
            <StatLines
              pares={[
                ['Vstallbrk · bissecção', num(md.vstallbrk_bisseccao, 4) + ' pu'],
                ['Vstallbrk · laço publicado', num(md.vstallbrk_laco_publicado, 4) + ' pu'],
                ['Vstall ajustado', num(md.vstall, 3) + ' pu'],
                ['tensão de quebra', num(md.v_quebra, 2) + ' pu'],
                ['Gstall', num(md.gstall, 4)],
                ['Bstall', num(md.bstall, 4)],
                ["Q'o inicial", num(md.qo, 4)],
              ]}
            />
            <div className="chips" style={{ marginTop: 10 }}>
              <Cursor key={'vs' + p.vstall} rotulo="Vstall" min={0.4} max={0.75} step={0.01} valor={p.vstall} largura={86} onCommit={p.setVstall} />
            </div>
            <div className="small muted" style={{ marginTop: 10 }}>
              {md.nota}
            </div>
          </div>
        </div>
      </OCard>

      <div className="grid g2" style={{ margin: '14px 0' }}>
        <OCard title="Carga eletrônica: descida ≠ subida" note={(cv.eletronica || {}).nota}>
          <Grafico
            deps={[cv]}
            desenhar={(el) => {
              if (!cv.eletronica) return
              lineChart(el, {
                index: cv.tensao,
                height: 200,
                digits: 2,
                yLabel: 'fração em serviço',
                formatTime: vfmt,
                xTicks: 9,
                zeroBase: true,
                series: [
                  { label: 'descida', values: cv.eletronica.descida, color: 'teal' },
                  { label: 'recuperação', values: cv.eletronica.subida, color: 'amber', style: 'dash' },
                ],
              })
            }}
          />
          <div className="chips" style={{ marginTop: 8 }}>
            <Cursor key={'fr' + p.frcel} rotulo="Frcel" min={0} max={1} step={0.05} valor={p.frcel} largura={86} onCommit={p.setFrcel} />
          </div>
        </OCard>
        <OCard
          title="Proteções agregadas"
          note="Protecão térmica (acima) e contatores (abaixo). O laço de histerese dos contatores é o que impede religamento instantâneo e oscilação numérica na fronteira."
        >
          <Grafico
            deps={[cv]}
            desenhar={(el) => {
              if (!cv.termica) return
              lineChart(el, {
                index: cv.termica.temperatura,
                height: 190,
                digits: 2,
                yLabel: 'fração não desligada',
                zeroBase: true,
                xTicks: 7,
                formatTime: (t) => Number(t).toFixed(1),
                series: [{ label: 'fth', values: cv.termica.fracao, color: 'crimson' }],
              })
            }}
          />
          <Grafico
            style={{ marginTop: 10 }}
            deps={[cv]}
            desenhar={(el) => {
              if (!cv.contator) return
              lineChart(el, {
                index: cv.tensao,
                height: 190,
                digits: 2,
                yLabel: 'fração fechada',
                formatTime: vfmt,
                xTicks: 9,
                zeroBase: true,
                series: [{ label: 'fcn', values: cv.contator.fracao, color: 'amber' }],
              })
            }}
          />
        </OCard>
      </div>

      <OCard title="O que prova que a implementação está correta">
        <div className={'note-strip' + (ex.confere ? '' : ' warn')}>
          A especificação publica um exemplo numérico de 100 MW com a tabela de resultado. Reproduzi-la é a única forma de mostrar que a implementação está <strong>correta</strong>, e não apenas
          plausível. Desvio máximo nas 12 comparações: <strong>{num(ex.desvio_maximo, 8)}</strong>.
        </div>
        <WecTable ex={ex} />
        <div className="small muted" style={{ margin: '8px 0 14px' }}>
          {ex.fonte} · reativos extras de {num(ex.extra_vars_mvar, 1)} Mvar, que vêm do balanço de rede da inicialização e não da soma dos reativos dos componentes.
        </div>
        <div className="grid g2">
          <OCard title="Conferências independentes" flush>
            <CheckList items={val.conferencias} />
          </OCard>
          <OCard title="Coerência com o Mapa Inteligente" flush note="Duas telas que discordassem sobre a mesma grandeza destruiriam a credibilidade das duas.">
            <CoherenceTable co={val.coerencia_mapa} />
          </OCard>
        </div>
      </OCard>

      <div className="grid g2" style={{ margin: '14px 0' }}>
        <OCard title="Geração distribuída no CLM" hint="o que o CLM acomoda e o que não acomoda">
          <StatLines
            pares={[
              ['MMGD estimada na área', num(gd.mmgd_kwp, 0) + ' kWp'],
              ['equivalente', num(gd.mmgd_mw, 3) + ' MW'],
            ]}
          />
          <div className="small" style={{ marginTop: 10 }}>
            <strong>Entra como:</strong> {gd.entra_como}
          </div>
          <div className="note-strip warn" style={{ marginTop: 10 }}>
            {gd.nao_contemplado}
          </div>
        </OCard>

        <OCard
          title="Limites desta parametrização"
          note={
            <>
              Fontes:{' '}
              {Object.keys(fontes).map((k, i) => (
                <span key={k}>
                  {i > 0 ? ' · ' : ''}
                  <strong>{k}</strong> {fontes[k].titulo}
                </span>
              ))}
            </>
          }
        >
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.65 }}>
            {(val.limites || []).map((l: string, i: number) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </OCard>
      </div>

      <OCard
        title="Cartão em texto"
        hint="formato neutro, com a procedência em cada linha"
        note="Neutro de propósito: emitir a sintaxe de uma ferramenta específica daria a impressão de um caso pronto para rodar, que não é o que isto é."
      >
        <pre className="code-block" style={{ maxHeight: 340, overflow: 'auto' }}>
          {card.cartao_texto}
        </pre>
      </OCard>

      <Proveniencia body={p.cardBody} />
    </>
  )
}
