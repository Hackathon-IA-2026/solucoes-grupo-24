/**
 * Camadas de marcadores do Mapa Híbrido: usinas em risco (círculos, cor = severidade, área ∝ MW)
 * e excedentes TSO-DSO (losangos, cor = prioridade).
 *
 * Clique SELECIONA (o mapa dá zoom e o painel mostra o detalhe) — não troca de página: o
 * operador explora no mapa e só sai dele pelo botão do card de detalhe. Marcadores com a mesma
 * coordenada aparecem em anel, ligados ao ponto real por uma linha fina (useDeslocamentos).
 */
import L from 'leaflet'
import { CircleMarker, Marker, Polyline, Tooltip } from 'react-leaflet'
import type { ExcedenteTsoDso, RiscoUsina } from '../../data/types'
import { idExcedente } from '../../modules'
import { RISK_STYLES } from '../../theme/severity'
import { corToken } from '../../theme/tokens'
import { formatMw, formatPct } from '../../utils/format'
import { useDeslocamentos, type PosicaoExibida } from './useDeslocamentos'

/** Raio do círculo (px) proporcional à raiz do montante: área ∝ MW. */
const raioRisco = (mw: number) => 5 + Math.sqrt(mw) * 0.6

const posRisco = (r: RiscoUsina): [number, number] => [r.lat, r.lon]
const idRisco = (r: RiscoUsina) => r.id
const posExcedente = (e: ExcedenteTsoDso): [number, number] => [e.lat, e.lon]

interface PropsCamada<T> {
  itens: readonly T[]
  selecionado: string | null
  destaque: string | null
  onSelecionar: (item: T) => void
  onDestaque: (id: string | null) => void
}

/** Linha do ponto real até o marcador deslocado + ponto real (só em grupos). */
function Ligacao({ p, cor }: { p: PosicaoExibida; cor: string }) {
  if (p.tamanhoGrupo < 2) return null
  return (
    <Polyline positions={[p.real, p.exibida]} pathOptions={{ color: cor, weight: 1, opacity: 0.5, dashArray: '2 3' }} interactive={false} />
  )
}

export function MarcadoresRisco({ itens, selecionado, destaque, onSelecionar, onDestaque }: PropsCamada<RiscoUsina>) {
  const posicoes = useDeslocamentos(itens, idRisco, posRisco)
  const linha = corToken('--color-ink-faint')
  const anel = corToken('--color-ink')
  // o selecionado e o destacado são desenhados por último (ficam por cima)
  const ordem = [...itens].sort((a, b) => Number(a.id === selecionado || a.id === destaque) - Number(b.id === selecionado || b.id === destaque))
  return (
    <>
      {ordem.map((r) => {
        const p = posicoes.get(r.id)
        if (!p) return null
        const foco = r.id === selecionado || r.id === destaque
        const cor = corToken(RISK_STYLES[r.severidade].token)
        return (
          <FragmentoRisco key={`${r.id}-${foco}`} r={r} p={p} foco={foco} selecionado={r.id === selecionado} cor={cor} anel={anel} linha={linha}
            onSelecionar={onSelecionar} onDestaque={onDestaque} />
        )
      })}
    </>
  )
}

function FragmentoRisco({ r, p, foco, selecionado, cor, anel, linha, onSelecionar, onDestaque }: {
  r: RiscoUsina; p: PosicaoExibida; foco: boolean; selecionado: boolean; cor: string; anel: string; linha: string
  onSelecionar: (r: RiscoUsina) => void; onDestaque: (id: string | null) => void
}) {
  return (
    <>
      <Ligacao p={p} cor={linha} />
      <CircleMarker
        center={p.exibida}
        radius={raioRisco(r.montanteMw) + (foco ? 4 : 0)}
        pathOptions={{ color: foco ? anel : cor, weight: selecionado ? 3 : foco ? 2.5 : 1.5, fillColor: cor, fillOpacity: foco ? 0.95 : 0.7 }}
        eventHandlers={{ click: () => onSelecionar(r), mouseover: () => onDestaque(r.id), mouseout: () => onDestaque(null) }}
      >
        <Tooltip direction="top" offset={[0, -6]}>
          <strong>{r.uf} · {r.nome}</strong>
          <br />
          {formatPct(r.probabilidadePct, 0)}% · {formatMw(r.montanteMw)} MW · {r.razao} · {r.horizonte}
          {p.tamanhoGrupo > 1 && (
            <>
              <br />
              <em>{p.tamanhoGrupo} usinas com a mesma coordenada (espalhadas para leitura)</em>
            </>
          )}
        </Tooltip>
      </CircleMarker>
    </>
  )
}

/** Losango (quadrado girado) para excedentes: forma diferente dos círculos de risco. */
function iconeLosango(cor: string, foco: boolean): L.DivIcon {
  const lado = foco ? 16 : 12
  const borda = foco ? 'var(--color-ink)' : 'var(--color-fundo)'
  return L.divIcon({
    className: '',
    iconSize: [lado + 2, lado + 2],
    html: `<div style="width:${lado}px;height:${lado}px;transform:rotate(45deg);background:${cor};border:${foco ? 2.5 : 1.5}px solid ${borda};opacity:.92"></div>`,
  })
}

export function MarcadoresExcedente({ itens, selecionado, destaque, onSelecionar, onDestaque }: PropsCamada<ExcedenteTsoDso>) {
  const posicoes = useDeslocamentos(itens, idExcedente, posExcedente)
  const linha = corToken('--color-ink-faint')
  return (
    <>
      {itens.map((e) => {
        const id = idExcedente(e)
        const p = posicoes.get(id)
        if (!p) return null
        const foco = id === selecionado || id === destaque
        return (
          <FragmentoExcedente key={`${id}-${foco}`} e={e} id={id} p={p} foco={foco} linha={linha} onSelecionar={onSelecionar} onDestaque={onDestaque} />
        )
      })}
    </>
  )
}

function FragmentoExcedente({ e, id, p, foco, linha, onSelecionar, onDestaque }: {
  e: ExcedenteTsoDso; id: string; p: PosicaoExibida; foco: boolean; linha: string
  onSelecionar: (e: ExcedenteTsoDso) => void; onDestaque: (id: string | null) => void
}) {
  return (
    <>
      <Ligacao p={p} cor={linha} />
      <Marker
        position={p.exibida}
        icon={iconeLosango(corToken(RISK_STYLES[e.prioridade].token), foco)}
        zIndexOffset={foco ? 1000 : 0}
        eventHandlers={{ click: () => onSelecionar(e), mouseover: () => onDestaque(id), mouseout: () => onDestaque(null) }}
      >
        <Tooltip direction="top" offset={[0, -8]}>
          <strong>{e.areaConcessao}</strong> · {e.distribuidora}
          <br />
          Excedente {formatMw(e.excedenteMw)} MW · {e.horizonte}
        </Tooltip>
      </Marker>
    </>
  )
}
