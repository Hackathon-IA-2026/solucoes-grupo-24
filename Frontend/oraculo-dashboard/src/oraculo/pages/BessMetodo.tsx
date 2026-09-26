/**
 * BESS: método, cobertura e sensibilidade (protótipo, painel "bessmetodo").
 * Porte de 02-PROTOTIPO/web/js/views/bess.js (V.bessmetodo).
 */
import { Api, type Envelope } from '../api'
import { num, pct } from '../format'
import { BarRow, Conteudo, OCard, Pagina, Proveniencia, StatLines, Vazio, useApi } from '../ui'
import { ProntoBess } from './Bess'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any

const TEXTO = 'Calculando a estabilidade do ranking…'

export default function BessMetodo() {
  return (
    <Pagina>
      <ProntoBess texto={TEXTO}>
        <Metodo />
      </ProntoBess>
    </Pagina>
  )
}

function Metodo() {
  const estado = useApi(() => Api.get('bess/metodo'), [])
  return (
    <Conteudo estado={estado} texto={TEXTO}>
      {(body) => <Corpo body={body} />}
    </Conteudo>
  )
}

function Barras({ obj, cor }: { obj: Record<string, number> | undefined; cor: (k: string) => string }) {
  return (
    <>
      {Object.entries(obj || {}).map(([k, v]) => (
        <BarRow key={k} label={k} frac={v} value={pct(v, 1)} color={cor(k)} />
      ))}
    </>
  )
}

function Corpo({ body }: { body: Envelope }) {
  const d = body.data as Dado
  return (
    <>
      <div className="grid g3" style={{ marginBottom: 14 }}>
        <OCard
          title="Localização do corte"
          note="Ponto de conexão → SE pelo código de 6 caracteres no cadastro do ONS; recuo pelas usinas (CEG) no SIGA/ANEEL. Sítio não localizado fica no ranking com a MMGD da UF."
        >
          <Barras obj={d.location} cor={(k) => (k === 'não localizado' ? 'crimson' : 'teal')} />
        </OCard>
        <OCard title="Razão da restrição" note="ENE: excedente energético · CNF: confiabilidade · REL: indisponibilidade externa · PAR: parecer de acesso.">
          <Barras obj={d.reasons} cor={(k) => (k === 'ENE' ? 'amber' : 'teal')} />
        </OCard>
        <OCard title="Origem" note="Origem SIS é aliviada por armazenamento em qualquer ponto do subsistema; LOC, só no ponto.">
          <Barras obj={d.origins} cor={(k) => (k === 'LOC' ? 'crimson' : 'teal')} />
        </OCard>
      </div>
      <OCard
        title="Estabilidade do top 10 sob outros pesos"
        note="Quantos dos 10 primeiros sítios com os pesos padrão continuam no top 10 em cada cenário. Sítio que resiste a todos é candidato robusto: não depende de uma escolha de peso."
      >
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Cenário de pesos</th>
                <th className="num">Permanecem no top 10</th>
                <th>Top 3 no cenário</th>
              </tr>
            </thead>
            <tbody>
              {(d.stability || []).map((x: Dado, i: number) => (
                <tr key={i}>
                  <td>{x.scenario}</td>
                  <td className="num">
                    <span className={'chip ' + (x.overlap >= 7 ? 'green' : x.overlap >= 5 ? 'amber' : 'crimson')}>{x.overlap + ' de ' + x.top}</span>
                  </td>
                  <td className="small">{(x.top3_names || x.top3 || []).join(' · ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </OCard>
      <div className="grid g2" style={{ marginTop: 14 }}>
        <OCard title="Premissas">
          <StatLines pares={(d.premises || []).map((p: Dado) => [p.k, p.v])} />
        </OCard>
        <OCard title="Limites declarados">
          <ul className="actions" style={{ paddingLeft: 18 }}>
            {(d.limits || []).map((x: string, i: number) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </OCard>
      </div>
      <OCard title="Sítios não localizados" hint={num((d.unlocated || []).length) + ' sítios'}>
        <TabelaNaoLocalizados rows={d.unlocated} />
      </OCard>
      <Proveniencia body={body} />
    </>
  )
}

function TabelaNaoLocalizados({ rows }: { rows: Dado[] | undefined }) {
  if (!rows || !rows.length) return <Vazio>Todos localizados.</Vazio>
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Código</th>
            <th>Sítio</th>
            <th>UF</th>
            <th className="num">Corte na janela (GWh)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.code + '-' + i}>
              <td className="mono">{r.code}</td>
              <td>{r.name}</td>
              <td>{r.uf}</td>
              <td className="num">{num(r.cut_gwh, 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
