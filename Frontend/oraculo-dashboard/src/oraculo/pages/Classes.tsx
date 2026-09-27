/**
 * Classes de consumo e assinatura da curva (painel "classes").
 *
 * Tudo nesta página é dado real, de três fontes (backend: oraculo/profiles/medidos.py):
 *  - FORMA horária de cada classe: curvas medidas pela ANEEL (CTR, campanhas das revisões
 *    tarifárias). Substituiu os perfis estilizados, desenhados à mão, que a página mostrava.
 *  - COMPOSIÇÃO de cada subsistema: energia faturada real (BDGD MT/AT + SAMP BT), da base da
 *    Fronteira T-D.
 *  - VALIDAÇÃO: curva montada (composição × forma) contra a curva de carga global do ONS.
 * A única premissa restante (limiares de área de telhado) aparece rotulada como PREMISSA.
 */
import { Api, type Envelope } from '../api'
import { lineChart } from '../charts'
import { num, pct } from '../format'
import { BarRow, Conteudo, Grafico, OCard, Pagina, Proveniencia, StatLines, useApi } from '../ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any

/** Uma cor por classe, a mesma no gráfico, nas barras e nas notas. */
const CLASS_COLORS: Record<string, string> = {
  residencial: 'teal',
  rural: 'green',
  comercial_bt: 'navy',
  media_tensao: 'amber',
  alta_tensao: 'purple',
}

const QUALIDADE_COR: Record<string, string> = { bom: 'green', moderado: 'amber', fraco: 'crimson' }

const ident = (v: unknown) => String(v)

export default function Classes() {
  const estado = useApi(() => Api.get('mapa/classes'), [])
  return (
    <Pagina>
      <Conteudo estado={estado} texto="Montando a curva de cada subsistema a partir das classes medidas…">
        {(body) => <Corpo body={body} />}
      </Conteudo>
    </Pagina>
  )
}

function Corpo({ body }: { body: Envelope }) {
  const d = body.data as Dado
  const med = d.measured
  const classes: Dado[] = med?.classes || []
  const rotulo: Record<string, string> = Object.fromEntries(classes.map((c) => [c.key, c.label]))
  const subs: Dado[] = d.subsystems || []
  const hours: string[] = (med?.hours || Array.from({ length: 24 }, (_, i) => i)).map(
    (h: number) => String(h).padStart(2, '0') + 'h',
  )
  const t = d.footprint_thresholds_m2 || {}

  return (
    <>
      <div className="note-strip">{d.note}</div>
      {d.measured_warning && <div className="note-strip warn">Perfis medidos indisponíveis: {d.measured_warning}</div>}
      {d.composition_warning && <div className="note-strip warn">{d.composition_warning}</div>}

      {med && (
        <div className="grid g-2-1" style={{ marginBottom: 14 }}>
          <OCard
            title="Perfis medidos por classe · dia útil"
            note="Média das curvas das campanhas de medição da ANEEL (CTR). Cada curva é dividida pela sua própria média de dia útil (p.u.) antes da média: distribuidoras de porte diferente pesam igual."
          >
            <Grafico
              deps={[med]}
              desenhar={(el) =>
                lineChart(el, {
                  index: hours,
                  height: 280,
                  digits: 2,
                  xTicks: 8,
                  formatTime: ident,
                  zeroBase: true,
                  series: classes.map((c) => ({
                    label: c.label,
                    values: c.profile_pu.util,
                    color: CLASS_COLORS[c.key] || 'teal',
                    digits: 2,
                  })),
                })
              }
            />
          </OCard>
          <OCard
            title="Fim de semana e amostra"
            note="Energia média do sábado e do domingo em relação ao dia útil da mesma curva. Ano = processo tarifário mais recente de cada distribuidora."
          >
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Classe</th>
                    <th className="num">sáb.</th>
                    <th className="num">dom.</th>
                    <th className="num">curvas</th>
                    <th className="num">distrib.</th>
                    <th className="num">anos</th>
                  </tr>
                </thead>
                <tbody>
                  {classes.map((c) => (
                    <tr key={c.key}>
                      <td style={{ color: 'var(--o-' + CLASS_COLORS[c.key] + ')' }}>{c.label}</td>
                      <td className="num">{num(c.saturday_ratio, 2)}</td>
                      <td className="num">{num(c.weekend_ratio, 2)}</td>
                      <td className="num">{num(c.n_curvas)}</td>
                      <td className="num">{num(c.n_distribuidoras)}</td>
                      <td className="num">
                        {c.ano_min}–{c.ano_max}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </OCard>
        </div>
      )}

      <div className="grid g2" style={{ marginBottom: 14 }}>
        {subs.map((s) => (
          <OCard
            key={s.subsystem}
            title={s.subsystem + ' · ' + s.name}
            hint={
              s.composition ? (
                <span>
                  R² {num(s.r2, 3)} <span style={{ color: 'var(--o-' + QUALIDADE_COR[s.fit_quality] + ')' }}>({s.fit_quality})</span> ·
                  cobertura {pct(s.coverage, 0)}
                </span>
              ) : (
                'sem composição real'
              )
            }
            note={s.fit_warning || undefined}
          >
            <Grafico
              deps={[s]}
              desenhar={(el) =>
                lineChart(el, {
                  index: hours,
                  height: 200,
                  digits: 4,
                  xTicks: 6,
                  formatTime: ident,
                  series: [
                    { label: 'observado (ONS, carga global)', values: s.observed, color: 'ink', width: 2.2, digits: 4 },
                    ...(s.assembled
                      ? // `as const`: dentro do spread o TS alarga 'dash' para string e o tipo Serie recusa
                        [{ label: 'montado (composição × perfis medidos)', values: s.assembled, color: 'teal', style: 'dash' as const, digits: 4 }]
                      : []),
                  ],
                })
              }
            />
            {s.composition && (
              <div style={{ marginTop: 10 }}>
                {classes.map((c) => (
                  <BarRow
                    key={c.key}
                    label={c.label}
                    frac={s.composition.pesos[c.key]}
                    value={pct(s.composition.pesos[c.key], 1)}
                    color={CLASS_COLORS[c.key]}
                  />
                ))}
              </div>
            )}
          </OCard>
        ))}
      </div>

      <OCard
        title="Composição por subsistema · energia faturada real"
        hint="BDGD (MT/AT, por SED) + SAMP (BT, por distribuidora)"
        note="Cobertura = energia da distribuição associada às SEs de fronteira ÷ energia do ONS no mesmo ano. O que falta (consumidores na rede básica, perdas) não entra na composição. 'SED mista' = energia de SEDs com UCs de MT e de AT, que a base não separa: contada como MT."
      >
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Subsistema</th>
                <th>Classe dominante</th>
                {classes.map((c) => (
                  <th className="num" key={c.key}>
                    {c.label.split(' (')[0]}
                  </th>
                ))}
                <th className="num">GWh/ano</th>
                <th className="num">cobertura</th>
                <th className="num">SED mista</th>
                <th className="num">R²</th>
                <th className="num">dom./útil obs.</th>
                <th className="num">dom./útil mont.</th>
              </tr>
            </thead>
            <tbody>
              {subs.map((s) => {
                const p = s.composition?.pesos || {}
                return (
                  <tr key={s.subsystem}>
                    <td>
                      <strong>{s.subsystem}</strong> <span className="small faint">{s.name}</span>
                    </td>
                    <td>{s.dominant ? rotulo[s.dominant] || s.dominant : '—'}</td>
                    {classes.map((c) => (
                      <td className="num" key={c.key}>
                        {s.composition ? pct(p[c.key], 1) : '—'}
                      </td>
                    ))}
                    <td className="num">{s.composition ? num(s.composition.total_gwh) : '—'}</td>
                    <td className="num">{s.composition ? pct(s.coverage, 0) : '—'}</td>
                    <td className="num">{s.composition ? pct(s.composition.fracao_sed_mista, 1) : '—'}</td>
                    <td className="num">{s.composition ? num(s.r2, 3) : '—'}</td>
                    <td className="num">{num(s.weekend_ratio_observed, 3)}</td>
                    <td className="num">{s.composition ? num(s.weekend_ratio_assembled, 3) : '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </OCard>

      <div className="grid g2" style={{ marginTop: 14 }}>
        <OCard
          title="Limiares de área de telhado · PREMISSA"
          note="Não é dado medido: é premissa de negócio da evidência morfológica do Mapa Inteligente (classes.py). A ponderação é por ÁREA, não por contagem: um galpão de 5.000 m² pesa muito mais na carga do que uma casa de 120 m²."
        >
          <StatLines
            pares={[
              ['Residencial', 'até ' + num(t.residencial_max) + ' m²'],
              ['Comercial', num(t.residencial_max) + ' a ' + num(t.comercial_max) + ' m²'],
              ['Industrial', 'acima de ' + num(t.comercial_max) + ' m²'],
            ]}
          />
        </OCard>
        <OCard title="O que cada classe cobre">
          {classes.map((c) => (
            <div className="stat-line" style={{ display: 'block' }} key={c.key}>
              <div style={{ color: 'var(--o-' + (CLASS_COLORS[c.key] || 'teal') + ')', fontWeight: 600 }}>
                {c.label} <span className="small faint">· subgrupos {c.subgrupos.join(', ')}</span>
              </div>
              <div className="small muted">{c.note}</div>
            </div>
          ))}
        </OCard>
      </div>
      <Proveniencia body={body} />
    </>
  )
}
