/**
 * Qualidade da correlação SE × SED (protótipo, painel "correlacao"). Porte de V.correlacao em
 * 02-PROTOTIPO/web/js/views/fronteira.js: sem verdade de campo para a topologia, validação
 * externa contra a carga do ONS, coerência física e sensibilidade às premissas.
 */
/* eslint-disable @typescript-eslint/no-explicit-any */
import type { ReactNode } from 'react'
import { Api, type Envelope } from '../api'
import { barChart } from '../charts'
import { num, pct } from '../format'
import { BarRow, Conteudo, Grafico, Kpi, OCard, Pagina, Proveniencia, StatLines, Vazio, useApi } from '../ui'
import { BaseFronteira, LoadChip } from './Fronteira'

type Dado = any

export default function Correlacao() {
  return (
    <Pagina>
      <BaseFronteira>{() => <Painel />}</BaseFronteira>
    </Pagina>
  )
}

function Painel() {
  const estado = useApi(() => Api.get<Dado>('fronteira/qualidade'), [])
  return (
    <Conteudo estado={estado} texto="Calculando a validação e a varredura de sensibilidade…">
      {(body) => <Corpo body={body} />}
    </Conteudo>
  )
}

function Hist({ bins, label, cor }: { bins: Dado[]; label: (b: Dado) => string; cor: string }) {
  return (
    <Grafico
      deps={[bins]}
      desenhar={(el) =>
        barChart(el, {
          labels: (bins || []).map(label),
          values: (bins || []).map((b) => b.count),
          color: cor,
          height: 190,
          digits: 0,
          seriesLabel: 'contagem',
        })
      }
    />
  )
}

function Corpo({ body }: { body: Envelope<Dado> }) {
  const d = body.data
  const r = d.report || {}
  const sens: Dado[] = d.sensitivity || []
  const cur = sens.find((x) => x.current) || {}
  const cov: Dado[] = d.ons_coverage || []

  return (
    <>
      <div className="note-strip">
        Nenhuma base pública diz de qual SE de fronteira cada SED recebe energia. Por isso a validação é <strong>indireta</strong>, em três frentes: (1) a energia alocada contra a carga
        verificada do ONS, calculada de forma independente; (2) a coerência física do carregamento implícito das SEs; (3) a sensibilidade do resultado às duas premissas que mais pesam.
      </div>

      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Kpi label="SEDs associadas" value={num(r.seds_associated)} foot={'de ' + num(r.seds_used) + ' · ' + num(r.seds_unassociated) + ' sem SE de fronteira no raio'} accent="teal" />
        <Kpi label="Vínculos ambíguos" value={pct(r.seds_associated ? r.seds_ambiguous / r.seds_associated : null, 0)} foot="p < 0,5: mais de uma SE plausível" accent="amber" />
        <Kpi label="Mesma UF" value={pct(r.same_uf_rate, 1)} foot="concessão é quase sempre intraestadual" accent="green" />
        <Kpi label="SE mais próxima escolhida" value={pct(cur.nearest_rate, 0)} foot="no restante, a capacidade pesou mais que a distância" accent="navy" />
      </div>

      <div className="grid g2" style={{ marginBottom: 14 }}>
        <OCard
          title="Validação externa · energia alocada × carga do ONS"
          hint={'ano ' + ((cov[0] || {}).ano ?? '')}
          note={
            <>
              A razão fica abaixo de 100% <strong>por construção</strong>: perdas técnicas e não técnicas, autoconsumo da MMGD e carga ligada direto na rede básica não aparecem no faturamento
              da distribuidora. No Norte, parte relevante da carga é eletrointensiva e conectada à rede básica. O que se verifica é a ordem de grandeza e a estabilidade entre subsistemas.
            </>
          }
        >
          {cov.map((c) => (
            <BarRow key={c.subsystem} label={c.subsystem + ' — ' + c.name} frac={Math.min(1, c.ratio || 0)} value={pct(c.ratio, 0)} color="teal" />
          ))}
          <div className="table-wrap" style={{ marginTop: 10 }}>
            <table>
              <thead>
                <tr>
                  <th>Subsistema</th>
                  <th className="num">Alocada (TWh)</th>
                  <th className="num">ONS verificada (TWh)</th>
                  <th className="num">Razão</th>
                </tr>
              </thead>
              <tbody>
                {cov.map((c) => (
                  <tr key={c.subsystem}>
                    <td>{c.subsystem}</td>
                    <td className="num">{num(c.allocated_gwh / 1000, 1)}</td>
                    <td className="num">{num((c.ons_gwh || 0) / 1000, 1)}</td>
                    <td className="num">{pct(c.ratio, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </OCard>
        <OCard
          title="Sensibilidade às premissas"
          hint="atratividade = MVA^α · e^(−d/λ)"
          note="Sem verdade de campo, o critério é coerência física: carregamento homogêneo (CV baixo), nenhuma SE acima de 100% e poucas SEs sem carga. Com α = 1 a SE grande atrai demais e esvazia as vizinhas; com α = 0 (só distância) há SEs sobrecarregadas. A linha destacada é a configuração em uso."
        >
          <TabelaSens sens={sens} />
        </OCard>
      </div>

      <div className="grid g3" style={{ marginBottom: 14 }}>
        <OCard title="Distância SED → SE" hint="km">
          <Hist bins={d.hist_distance} label={(b) => num(b.from) + '–' + num(b.to)} cor="navy" />
        </OCard>
        <OCard title="Probabilidade do vínculo" hint="p do vínculo primário">
          <Hist bins={d.hist_probability} label={(b) => num(b.from, 1)} cor="teal" />
        </OCard>
        <OCard title="Carregamento implícito" hint="carga média ÷ (MVA × 0,92)">
          <Hist bins={d.hist_loading} label={(b) => pct(b.from, 0)} cor="amber" />
        </OCard>
      </div>

      <div className="grid g2" style={{ marginBottom: 14 }}>
        <OCard
          title="SEs fora da faixa plausível"
          hint={num((d.flagged || []).length) + ' SEs'}
          note="Acima da faixa: provável SE vizinha ausente do cadastro de fronteira, ou atração excessiva. Abaixo: SE que interliga transmissão e entrega pouca carga local."
        >
          <TabelaFlag rows={d.flagged} />
        </OCard>
        <OCard title="MMGD e baixa tensão" note="Município sem nenhuma SED na BDGD aberta (só há pessoa jurídica) desce direto à SE de fronteira pelo centroide.">
          <StatLines
            pares={[
              ['MMGD no cadastro ANEEL', num(r.gd_total_mw, 0) + ' MW'],
              ['· vínculo direto UC → SED', num(r.gd_direct_mw, 0) + ' MW'],
              ['· rateada pelo município', num(r.gd_municipal_allocated_mw, 0) + ' MW'],
              ['· sem SE no raio', num(r.gd_unallocated_mw, 0) + ' MW'],
              ['Baixa tensão alocada (SAMP)', num(r.bt_allocated_twh, 1) + ' TWh'],
              ['· sem destino', num(r.bt_unallocated_twh, 1) + ' TWh'],
              ['Municípios ligados pelo centroide', num(r.municipios_por_centroide)],
              ['Energia MT/AT associada', pct(r.energy_mtat_associated_share, 1)],
            ]}
          />
        </OCard>
      </div>

      <div className="grid g3">
        <OCard title="Premissas">
          <StatLines pares={(d.premises || []).map((p: Dado) => [p.k, p.v] as [ReactNode, ReactNode])} />
        </OCard>
        <OCard title="Privacidade">
          <ul className="actions" style={{ paddingLeft: 18 }}>
            {(d.privacy || []).map((x: string, i: number) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </OCard>
        <OCard title="Limites declarados">
          <ul className="actions" style={{ paddingLeft: 18 }}>
            {(d.limits || []).map((x: string, i: number) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </OCard>
      </div>
      <Proveniencia body={body} />
    </>
  )
}

function TabelaSens({ sens }: { sens: Dado[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th className="num" style={{ textTransform: 'none' }}>
              α
            </th>
            <th className="num" style={{ textTransform: 'none' }}>
              λ (km)
            </th>
            <th className="num">ambíguas</th>
            <th className="num">mais próxima</th>
            <th className="num">SEs sem carga</th>
            <th className="num">CV carreg.</th>
            <th className="num">máx.</th>
            <th className="num">&gt;100%</th>
          </tr>
        </thead>
        <tbody>
          {sens.map((x, i) => (
            <tr key={i} className={x.current ? 'sel' : ''}>
              <td className="num">{num(x.alpha, 1)}</td>
              <td className="num">{num(x.lambda_km)}</td>
              <td className="num">{pct(x.ambiguous_rate, 0)}</td>
              <td className="num">{pct(x.nearest_rate, 0)}</td>
              <td className="num">{num(x.frontier_no_load)}</td>
              <td className="num">{num(x.loading_cv, 2)}</td>
              <td className={'num ' + (x.loading_max > 1 ? 'neg' : '')}>{pct(x.loading_max, 0)}</td>
              <td className={'num ' + (x.over_100 ? 'neg' : '')}>{num(x.over_100)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TabelaFlag({ rows }: { rows: Dado[] }) {
  if (!rows || !rows.length) return <Vazio>Nenhuma SE fora da faixa.</Vazio>
  return (
    <div className="table-wrap scroll-y">
      <table>
        <thead>
          <tr>
            <th>SE</th>
            <th className="num">MVA</th>
            <th className="num">MW médio</th>
            <th>Carreg.</th>
            <th className="num">SEDs</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={(r.sub_id || '') + ':' + i}>
              <td>
                {r.name} <span className="small faint">{r.uf}</span>
              </td>
              <td className="num">{num(r.frontier_mva)}</td>
              <td className="num">{num(r.mw_avg, 0)}</td>
              <td>
                <LoadChip f={r} />
              </td>
              <td className="num">{num(r.n_sed)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
