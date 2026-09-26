/**
 * Mapa Híbrido: usinas em risco (círculos por severidade) e excedentes TSO-DSO (losangos por
 * prioridade) sobre o Brasil, com camada opcional de densidade de MMGD e painel lateral.
 *
 * Interação (revisão de 2026-09-26: o mapa é o lugar de explorar, não um atalho para outra tela):
 * - clicar num marcador ou num item do painel SELECIONA: zoom no item e card de detalhe no painel
 *   (dali, botões levam ao Detalhe do Alerta ou aos Excedentes); Esc limpa a seleção;
 * - a seleção fica na URL (?sel=risco:<id>), então "ver no mapa" nas outras telas abre o mapa já
 *   focado, e o link pode ser compartilhado;
 * - passar o mouse numa UF mostra o resumo dela; clicar dá zoom e filtra o painel pela UF;
 * - filtros de razão e horizonte (usinas) e os de severidade da topbar valem para mapa e painel;
 * - "Enquadrar" ajusta o zoom a tudo que está visível; "Brasil" volta à vista inicial;
 * - usinas com a MESMA coordenada aparecem em anel, ligadas ao ponto real.
 *
 * Fundo 100% local: contorno do Brasil (Natural Earth, npm run geo:brasil) + divisas das UFs
 * (IBGE, npm run geo:ufs). Decisão (2026-09-26): os tiles da CARTO que ficavam por baixo
 * passaram a exigir chave e cobriam o mapa com "API KEY REQUIRED". O mapa não depende mais de
 * nenhum serviço externo em tempo de execução — funciona offline, na rede do ONS e na demo — e
 * um teste (src/pages/semServicoExterno.test.ts) impede a volta de camada de tiles remota.
 */
import 'leaflet/dist/leaflet.css'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ChevronRight, Crosshair, Maximize2, X } from 'lucide-react'
import L from 'leaflet'
import { AttributionControl, GeoJSON, MapContainer } from 'react-leaflet'
import { useSearchParams } from 'react-router-dom'
import { CamadaCalor } from '../components/mapa/CamadaCalor'
import { CamadaUfs, type ResumoUf } from '../components/mapa/CamadaUfs'
import { MarcadoresExcedente, MarcadoresRisco } from '../components/mapa/Marcadores'
import { AvisoFiltro } from '../components/ui/AvisoFiltro'
import { Botao, BotaoLink } from '../components/ui/Botao'
import { Card } from '../components/ui/Card'
import { Carregando, ErroDados } from '../components/ui/Estado'
import { FiltroChips } from '../components/ui/FiltroChips'
import { MockTag } from '../components/ui/MockTag'
import { RazaoBadge } from '../components/ui/RazaoBadge'
import { SeverityBadge } from '../components/ui/SeverityBadge'
import { ToggleChip } from '../components/ui/ToggleChip'
import { getDensidadeMmgd, getExcedentes, getRiscos } from '../data/dataSource'
import { ordenarExcedentes, ordenarPorSeveridade } from '../data/derivados'
import brasil from '../data/geo/brasil.geo.json'
import ufsGeo from '../data/geo/ufs.geo.json'
import { HorizonteSchema, RazaoSchema, type DensidadeMmgd, type ExcedenteTsoDso, type Horizonte, type Razao, type RiscoUsina } from '../data/types'
import { useDados } from '../data/useDados'
import { idExcedente, lerSelecaoMapa, MODULES, PARAM_SELECAO_MAPA, rotaDetalheAlerta, type SelecaoMapa } from '../modules'
import { useFiltradosPorSeveridade } from '../state/useSeverityFilter'
import { RAZAO_INFO } from '../theme/razao'
import { RISK_STYLES } from '../theme/severity'
import { corToken } from '../theme/tokens'
import { formatMw, formatPct } from '../utils/format'
import { ufDoPonto, type ColecaoUfs } from '../utils/geo'

/** Caixa do Brasil: enquadramento inicial e limite de arraste. */
const LIMITES_BR: L.LatLngBoundsExpression = [
  [-34.5, -74.5],
  [6, -32],
]
const ZOOM_ITEM = 7 // zoom ao selecionar um item (vê o anel de usinas sobrepostas e a região)
const EXCEDENTES = MODULES.find((m) => m.label === 'Excedentes TSO-DSO')!
const LISTA = MODULES.find((m) => m.label === 'Lista de Riscos')!
const UFS = ufsGeo as unknown as ColecaoUfs

/** Camadas ligáveis (a de MMGD começa desligada: é sintética). */
type Camada = 'riscos' | 'excedentes' | 'mmgd'
const ROTULO_CAMADA: Record<Camada, string> = {
  riscos: 'Usinas em risco',
  excedentes: 'Excedentes TSO-DSO',
  mmgd: 'Densidade MMGD (sintético)',
}

export default function MapaHibrido() {
  const riscos = useDados(getRiscos)
  const excedentes = useDados(getExcedentes)
  const mmgd = useDados(getDensidadeMmgd)

  for (const d of [riscos, excedentes, mmgd]) if (d.status === 'erro') return <ErroDados erro={d.erro} />
  if (riscos.status !== 'ok' || excedentes.status !== 'ok' || mmgd.status !== 'ok') return <Carregando altura="h-[32rem]" />

  return <Mapa riscos={ordenarPorSeveridade(riscos.data)} excedentes={ordenarExcedentes(excedentes.data)} mmgd={mmgd.data} />
}

function Mapa({ riscos: todosRiscos, excedentes: todosExcedentes, mmgd }: { riscos: RiscoUsina[]; excedentes: ExcedenteTsoDso[]; mmgd: DensidadeMmgd }) {
  const mapaRef = useRef<L.Map | null>(null)

  // --- seleção (na URL) e destaque (hover, compartilhado entre mapa e painel)
  const [params, setParams] = useSearchParams()
  const sel = lerSelecaoMapa(params.get(PARAM_SELECAO_MAPA))
  const selecionar = useCallback(
    (s: SelecaoMapa | null) =>
      setParams(
        (prev) => {
          const p = new URLSearchParams(prev)
          if (s) p.set(PARAM_SELECAO_MAPA, `${s.tipo}:${s.id}`)
          else p.delete(PARAM_SELECAO_MAPA)
          return p
        },
        { replace: true },
      ),
    [setParams],
  )
  const [destaque, setDestaque] = useState<string | null>(null)

  // --- filtros
  const [camadas, setCamadas] = useState<Record<Camada, boolean>>({ riscos: true, excedentes: true, mmgd: false })
  const [razoes, setRazoes] = useState<Set<Razao>>(() => new Set(RazaoSchema.options))
  const [horizontes, setHorizontes] = useState<Set<Horizonte>>(() => new Set(HorizonteSchema.options))
  const [uf, setUf] = useState<string | null>(null)
  const [aba, setAba] = useState<'riscos' | 'excedentes'>(sel?.tipo === 'excedente' ? 'excedentes' : 'riscos')

  const sevR = useFiltradosPorSeveridade(todosRiscos, (r) => r.severidade)
  const sevE = useFiltradosPorSeveridade(todosExcedentes, (e) => e.prioridade)
  // UF do excedente sai da malha do IBGE (o contrato só traz lat/lon)
  const ufExcedente = useMemo(() => new Map(todosExcedentes.map((e) => [idExcedente(e), ufDoPonto(e.lat, e.lon, UFS)])), [todosExcedentes])

  const riscos = useMemo(
    () => sevR.visiveis.filter((r) => razoes.has(r.razao) && horizontes.has(r.horizonte) && (!uf || r.uf === uf)),
    [sevR.visiveis, razoes, horizontes, uf],
  )
  const excedentes = useMemo(
    () => sevE.visiveis.filter((e) => !uf || ufExcedente.get(idExcedente(e)) === uf),
    [sevE.visiveis, uf, ufExcedente],
  )
  const ocultosPorFiltroLocal = sevR.visiveis.length - riscos.length + (sevE.visiveis.length - excedentes.length)

  // resumo por UF (tooltip das UFs), sobre o que passa nos filtros de severidade/razão/horizonte
  const resumoUf = useMemo(() => {
    const m = new Map<string, ResumoUf>()
    const pega = (k: string) => m.get(k) ?? m.set(k, { riscos: 0, mw: 0, excedentes: 0 }).get(k)!
    for (const r of sevR.visiveis.filter((r) => razoes.has(r.razao) && horizontes.has(r.horizonte))) {
      const x = pega(r.uf)
      x.riscos += 1
      x.mw += r.montanteMw
    }
    for (const e of sevE.visiveis) {
      const k = ufExcedente.get(idExcedente(e))
      if (k) pega(k).excedentes += 1
    }
    return m
  }, [sevR.visiveis, sevE.visiveis, razoes, horizontes, ufExcedente])

  // item selecionado (procurado em TODOS os itens: um link pode apontar para algo filtrado)
  const riscoSel = sel?.tipo === 'risco' ? todosRiscos.find((r) => r.id === sel.id) ?? null : null
  const excSel = sel?.tipo === 'excedente' ? todosExcedentes.find((e) => idExcedente(e) === sel.id) ?? null : null
  const itemSel = riscoSel ?? excSel

  // zoom no item quando a seleção muda (inclusive quando a tela abre com ?sel=)
  const chaveSel = sel ? `${sel.tipo}:${sel.id}` : null
  useEffect(() => {
    const mapa = mapaRef.current
    if (!mapa || !itemSel) return
    mapa.flyTo([itemSel.lat, itemSel.lon], Math.max(mapa.getZoom(), ZOOM_ITEM), { duration: 0.6 })
    setAba(riscoSel ? 'riscos' : 'excedentes')
  }, [chaveSel]) // eslint-disable-line react-hooks/exhaustive-deps

  // Esc limpa a seleção
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => e.key === 'Escape' && selecionar(null)
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [selecionar])

  const enquadrar = () => {
    const mapa = mapaRef.current
    if (!mapa) return
    const pts = [...(camadas.riscos ? riscos : []), ...(camadas.excedentes ? excedentes : [])].map((i) => L.latLng(i.lat, i.lon))
    if (!pts.length) mapa.fitBounds(LIMITES_BR)
    else if (pts.length === 1 || L.latLngBounds(pts).getNorthEast().equals(L.latLngBounds(pts).getSouthWest())) mapa.flyTo(pts[0], ZOOM_ITEM)
    else mapa.fitBounds(L.latLngBounds(pts), { padding: [40, 40], maxZoom: 9 })
  }
  const clicarUf = (u: string, limites: L.LatLngBounds) => {
    if (u === uf) return setUf(null) // clicar de novo na mesma UF tira o filtro
    setUf(u)
    mapaRef.current?.fitBounds(limites, { padding: [24, 24] })
  }

  const cores = useMemo(() => ({ contorno: corToken('--color-ink-faint') }), [])
  const mock = todosRiscos.some((r) => r.mock) || todosExcedentes.some((e) => e.mock)
  const haSobrepostos = useMemo(() => new Set(riscos.map((r) => `${r.lat},${r.lon}`)).size < riscos.length, [riscos])

  return (
    <div className="space-y-3">
      {/* camadas e filtros */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="flex flex-wrap items-center gap-1">
          {(Object.keys(ROTULO_CAMADA) as Camada[]).map((c) => (
            <ToggleChip
              key={c}
              label={ROTULO_CAMADA[c]}
              ativo={camadas[c]}
              onToggle={() => setCamadas((v) => ({ ...v, [c]: !v[c] }))}
              classeAtivo={c === 'mmgd' ? 'border-chart-2/60 bg-chart-2/10 text-ink' : 'border-accent/50 bg-accent/10 text-accent'}
              classePonto={c === 'mmgd' ? 'bg-chart-2' : 'bg-accent'}
            />
          ))}
          {camadas.mmgd && <MockTag mock={mmgd.mock} />}
        </div>
        <FiltroChips rotulo="Razão" opcoes={RazaoSchema.options} ativos={razoes} onChange={setRazoes} pontoOpcao={(r) => RAZAO_INFO[r].dot} />
        <FiltroChips rotulo="Horizonte" opcoes={HorizonteSchema.options} ativos={horizontes} onChange={setHorizontes} />
        {uf && (
          <button type="button" onClick={() => setUf(null)} className="inline-flex items-center gap-1 rounded-sm border border-accent/50 bg-accent/10 px-2 py-0.5 font-mono text-[10px] font-semibold text-accent">
            UF: {uf} <X className="size-3" aria-label="Tirar filtro de UF" />
          </button>
        )}
        <AvisoFiltro ocultos={sevR.ocultos + sevE.ocultos} className="ml-auto" />
        {ocultosPorFiltroLocal > 0 && (
          <span className="font-mono text-[11px] text-ink-faint">{ocultosPorFiltroLocal} fora dos filtros do mapa</span>
        )}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_21rem]">
        <Card flush title="Brasil · usinas, excedentes e MMGD" actions={<MockTag mock={mock} />} className="overflow-hidden">
          {/* altura = janela − topbar − cabeçalho do módulo − filtros − margens (conteúdo rola no <main>) */}
          <div className="relative h-[calc(100dvh-13rem)] min-h-[28rem]">
            <MapContainer ref={mapaRef} bounds={LIMITES_BR} maxBounds={LIMITES_BR} maxBoundsViscosity={0.8} minZoom={3} zoomSnap={0.25} className="size-full" attributionControl={false}>
              {/* prefixo só com o nome do Leaflet (o padrão traz uma bandeira sem relação com o painel) */}
              <AttributionControl prefix='<a href="https://leafletjs.com">Leaflet</a>' />
              {/* divisas estaduais (IBGE, interativas) por baixo, contorno do país (Natural Earth) por cima */}
              <CamadaUfs selecionada={uf} resumo={resumoUf} onClicar={clicarUf} />
              <GeoJSON data={brasil as GeoJSON.Feature} style={{ color: cores.contorno, weight: 1.2, fill: false }} interactive={false} />

              {camadas.mmgd && <CamadaCalor pontos={mmgd.pontos} />}
              {camadas.excedentes && (
                <MarcadoresExcedente
                  itens={excedentes}
                  selecionado={excSel ? idExcedente(excSel) : null}
                  destaque={destaque}
                  onSelecionar={(e) => selecionar({ tipo: 'excedente', id: idExcedente(e) })}
                  onDestaque={setDestaque}
                />
              )}
              {camadas.riscos && (
                <MarcadoresRisco
                  itens={riscos}
                  selecionado={riscoSel?.id ?? null}
                  destaque={destaque}
                  onSelecionar={(r) => selecionar({ tipo: 'risco', id: r.id })}
                  onDestaque={setDestaque}
                />
              )}
            </MapContainer>

            {/* controles de enquadramento (canto superior direito) */}
            <div className="absolute top-3 right-3 z-[1000] flex flex-col gap-1">
              <Botao onClick={enquadrar} title="Ajustar o zoom a tudo que está visível" className="bg-fundo/90">
                <Crosshair className="size-3.5" aria-hidden /> Enquadrar
              </Botao>
              <Botao onClick={() => mapaRef.current?.fitBounds(LIMITES_BR)} title="Voltar à vista do Brasil" className="bg-fundo/90">
                <Maximize2 className="size-3.5" aria-hidden /> Brasil
              </Botao>
            </div>
            <Legenda mmgd={camadas.mmgd} sobrepostos={haSobrepostos} />
          </div>
        </Card>

        <div className="flex min-h-0 flex-col gap-4">
          {itemSel && (riscoSel ? <CartaoRisco r={riscoSel} onLimpar={() => selecionar(null)} /> : <CartaoExcedente e={excSel!} uf={ufExcedente.get(idExcedente(excSel!)) ?? null} onLimpar={() => selecionar(null)} />)}
          <PainelItens
            aba={aba}
            onAba={setAba}
            riscos={camadas.riscos ? riscos : []}
            excedentes={camadas.excedentes ? excedentes : []}
            selecionado={chaveSel}
            destaque={destaque}
            onDestaque={setDestaque}
            onSelecionar={selecionar}
          />
        </div>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ card de detalhe
function Campo({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div>
      <dt className="rotulo text-[10px] text-ink-faint">{k}</dt>
      <dd className="kpi mt-0.5 text-body text-ink">{v}</dd>
    </div>
  )
}

function CartaoRisco({ r, onLimpar }: { r: RiscoUsina; onLimpar: () => void }) {
  return (
    <Card title="Usina selecionada" accent={RISK_STYLES[r.severidade].topo} actions={<><MockTag mock={r.mock} /><LimparSelecao onLimpar={onLimpar} /></>}>
      <p className="flex flex-wrap items-center gap-2">
        <SeverityBadge level={r.severidade} />
        <RazaoBadge razao={r.razao} />
        <span className="font-mono text-[11px] text-ink-muted">{r.uf}</span>
      </p>
      <p className="mt-1.5 text-[15px] font-semibold text-ink">{r.nome}</p>
      <dl className="mt-3 grid grid-cols-3 gap-3">
        <Campo k="Probabilidade" v={`${formatPct(r.probabilidadePct, 0)}%`} />
        <Campo k="Montante" v={`${formatMw(r.montanteMw)} MW`} />
        <Campo k="Horizonte" v={r.horizonte} />
        <Campo k="Fonte" v={r.fonte} />
        <div className="col-span-2">
          <Campo k="Distribuidora" v={r.distribuidora} />
        </div>
      </dl>
      <p className="mt-3 border-t border-line pt-2.5 text-body text-ink-muted">{r.acaoRecomendada}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <BotaoLink variante="primario" to={rotaDetalheAlerta(r.id)}>
          Detalhe do alerta <ChevronRight className="size-3" aria-hidden />
        </BotaoLink>
        <BotaoLink to={LISTA.path}>{LISTA.label}</BotaoLink>
      </div>
    </Card>
  )
}

function CartaoExcedente({ e, uf, onLimpar }: { e: ExcedenteTsoDso; uf: string | null; onLimpar: () => void }) {
  return (
    <Card title="Excedente selecionado" accent={RISK_STYLES[e.prioridade].topo} actions={<><MockTag mock={e.mock} /><LimparSelecao onLimpar={onLimpar} /></>}>
      <p className="flex flex-wrap items-center gap-2">
        <SeverityBadge level={e.prioridade} label={`prioridade ${RISK_STYLES[e.prioridade].label.toLowerCase()}`} />
        {uf && <span className="font-mono text-[11px] text-ink-muted">{uf}</span>}
      </p>
      <p className="mt-1.5 text-[15px] font-semibold text-ink">{e.areaConcessao}</p>
      <dl className="mt-3 grid grid-cols-3 gap-3">
        <Campo k="Excedente" v={`${formatMw(e.excedenteMw)} MW`} />
        <Campo k="Horizonte" v={e.horizonte} />
        <Campo k="Fonte" v={e.fonte} />
        <div className="col-span-3">
          <Campo k="Distribuidora" v={e.distribuidora} />
        </div>
      </dl>
      <p className="mt-3 border-t border-line pt-2.5 text-body text-ink-muted">{e.acaoRecomendada}</p>
      <div className="mt-3">
        <BotaoLink variante="primario" to={EXCEDENTES.path}>
          {EXCEDENTES.label} <ChevronRight className="size-3" aria-hidden />
        </BotaoLink>
      </div>
    </Card>
  )
}

function LimparSelecao({ onLimpar }: { onLimpar: () => void }) {
  return (
    <button type="button" onClick={onLimpar} title="Limpar seleção (Esc)" aria-label="Limpar seleção" className="text-ink-faint hover:text-ink">
      <X className="size-4" aria-hidden />
    </button>
  )
}

// ------------------------------------------------------------------ painel lateral
function PainelItens({ aba, onAba, riscos, excedentes, selecionado, destaque, onDestaque, onSelecionar }: {
  aba: 'riscos' | 'excedentes'
  onAba: (a: 'riscos' | 'excedentes') => void
  riscos: RiscoUsina[]
  excedentes: ExcedenteTsoDso[]
  selecionado: string | null
  destaque: string | null
  onDestaque: (id: string | null) => void
  onSelecionar: (s: SelecaoMapa) => void
}) {
  const abas = [
    { k: 'riscos' as const, rotulo: 'Usinas', n: riscos.length },
    { k: 'excedentes' as const, rotulo: 'Excedentes', n: excedentes.length },
  ]
  const itemBase = 'flex w-full flex-col items-start gap-1 border-l-2 px-3 py-2.5 text-left transition-colors'
  return (
    <Card flush className="min-h-0 flex-1">
      <div role="tablist" className="flex border-b border-line">
        {abas.map((a) => (
          <button
            key={a.k}
            role="tab"
            aria-selected={aba === a.k}
            onClick={() => onAba(a.k)}
            className={`flex-1 border-b-2 px-3 py-2 font-mono text-[11px] font-semibold tracking-wider uppercase ${aba === a.k ? 'border-accent text-accent' : 'border-transparent text-ink-muted hover:text-ink'}`}
          >
            {a.rotulo} <span className="text-ink-faint">({a.n})</span>
          </button>
        ))}
      </div>
      <ul className="max-h-[calc(100dvh-26rem)] min-h-40 divide-y divide-line/60 overflow-y-auto">
        {aba === 'riscos' &&
          riscos.map((r) => {
            const chave = `risco:${r.id}`
            const ativo = chave === selecionado
            return (
              <li key={r.id} onMouseEnter={() => onDestaque(r.id)} onMouseLeave={() => onDestaque(null)}>
                <button
                  type="button"
                  onClick={() => onSelecionar({ tipo: 'risco', id: r.id })}
                  className={`${itemBase} ${RISK_STYLES[r.severidade].barra} ${ativo ? 'bg-accent/10' : destaque === r.id ? 'bg-surface-raised' : 'hover:bg-surface-raised'}`}
                >
                  <span className="flex items-center gap-2">
                    <SeverityBadge level={r.severidade} />
                    <RazaoBadge razao={r.razao} />
                    <span className="font-mono text-[10px] text-ink-faint">{r.uf}</span>
                  </span>
                  <span className="text-body text-ink">{r.nome}</span>
                  <span className="kpi text-xs text-ink-muted">
                    {formatPct(r.probabilidadePct, 0)}% · {formatMw(r.montanteMw)} MW · {r.horizonte}
                  </span>
                </button>
              </li>
            )
          })}
        {aba === 'excedentes' &&
          excedentes.map((e) => {
            const id = idExcedente(e)
            const ativo = `excedente:${id}` === selecionado
            return (
              <li key={id} onMouseEnter={() => onDestaque(id)} onMouseLeave={() => onDestaque(null)}>
                <button
                  type="button"
                  onClick={() => onSelecionar({ tipo: 'excedente', id })}
                  className={`${itemBase} ${RISK_STYLES[e.prioridade].barra} ${ativo ? 'bg-accent/10' : destaque === id ? 'bg-surface-raised' : 'hover:bg-surface-raised'}`}
                >
                  <span className="flex items-center gap-2">
                    <SeverityBadge level={e.prioridade} />
                    <span className="font-mono text-[10px] text-ink-faint">{e.distribuidora}</span>
                  </span>
                  <span className="text-body text-ink">{e.areaConcessao}</span>
                  <span className="kpi text-xs text-ink-muted">
                    {formatMw(e.excedenteMw)} MW · {e.fonte} · {e.horizonte}
                  </span>
                </button>
              </li>
            )
          })}
        {((aba === 'riscos' && !riscos.length) || (aba === 'excedentes' && !excedentes.length)) && (
          <li className="px-4 py-8 text-center text-xs text-ink-muted">Nada visível com os filtros atuais.</li>
        )}
      </ul>
      <p className="border-t border-line px-3 py-2 text-[11px] text-ink-faint">Clique para dar zoom · passe o mouse numa UF para ver o resumo</p>
    </Card>
  )
}

/** Legenda sobre o mapa (canto inferior esquerdo). */
function Legenda({ mmgd, sobrepostos }: { mmgd: boolean; sobrepostos: boolean }) {
  const niveis = ['critical', 'high', 'medium', 'low'] as const
  return (
    <div className="pointer-events-none absolute bottom-6 left-3 z-[1000] space-y-2 rounded border border-line bg-fundo/90 px-3 py-2 text-[11px] text-ink-muted">
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {niveis.map((n) => (
          <span key={n} className="flex items-center gap-1.5">
            <span className={`size-2.5 rounded-full ${RISK_STYLES[n].dot}`} aria-hidden /> {RISK_STYLES[n].label}
          </span>
        ))}
      </p>
      <p className="flex items-center gap-3">
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full border border-ink-muted" aria-hidden /> usina (tamanho ∝ MW)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2 rotate-45 border border-ink-muted" aria-hidden /> excedente TSO-DSO
        </span>
      </p>
      {sobrepostos && (
        <p className="flex items-center gap-2">
          <span className="w-4 border-t border-dashed border-ink-muted" aria-hidden />
          anel = usinas com a mesma coordenada, ligadas ao ponto real
        </p>
      )}
      {mmgd && (
        <p className="flex items-center gap-2">
          <span className="h-2 w-16 rounded-full bg-gradient-to-r from-chart-2/20 via-chart-2 to-mmgd-pico" aria-hidden />
          densidade MMGD (sintética)
        </p>
      )}
    </div>
  )
}
