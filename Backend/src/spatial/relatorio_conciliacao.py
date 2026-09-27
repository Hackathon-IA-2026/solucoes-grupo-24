"""Relatório da conciliação de MMGD (docs/reports/relatorio_conciliacao.md), gerado a cada execução.

Só formata o que src/spatial/conciliacao.py calculou: nenhum número é digitado aqui. Método,
decisões e a medição de sensibilidade do detector ficam em docs/metodo_conciliacao.md.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.spatial.conciliacao_cfg import piloto, saida
from src.utils.paths import ensure

NOMES = {"3304557": "Rio de Janeiro", "3303302": "Niterói"}  # só para leitura; a chave é o código IBGE


def _kw(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


def _mw(v: float) -> str:
    return f"{v / 1000:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _tabela(df: pd.DataFrame) -> str:
    cab = "| " + " | ".join(df.columns) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    return "\n".join([cab, sep, *("| " + " | ".join(str(v) for v in r) + " |" for r in df.itertuples(index=False))])


def escrever(trafo: pd.DataFrame, mun: pd.DataFrame, res: pd.DataFrame, serie: pd.DataFrame, u: pd.DataFrame,
             data_base: dict, data_ref: pd.Timestamp, data_geracao: pd.Timestamp, meta_visao: dict,
             det: pd.DataFrame, c: dict, dupla_kw: dict) -> str:
    conf_min = c["conciliacao"]["confianca_minima"]
    r = res.set_index("municipio")
    linhas = []
    for m in mun.itertuples():
        g = trafo[trafo["municipio"] == m.municipio]
        img = g[g["tem_imagem"]]
        datas = sorted({d.date().isoformat() for d in img["data_imagem"].dropna()})
        linhas.append({
            "Município": f"{NOMES.get(m.municipio, m.municipio)} ({m.municipio})",
            "Transformadores": _kw(len(g)), "Com MMGD na BDGD": _kw((g["capacidade_bdgd_kw"] > 0).sum()),
            "BDGD (MW)": _mw(g["capacidade_bdgd_kw"].sum()),
            "ANEEL data-base (MW)": _mw(m.capacidade_aneel_data_base),
            "ANEEL data_ref (MW)": _mw(m.capacidade_aneel_data_ref),
            "Defasagem (MW)": _mw(m.defasagem_kw),
            "Razão BDGD/ANEEL": "—" if pd.isna(m.razao_cobertura_bdgd) else f"{m.razao_cobertura_bdgd:.3f}".replace(".", ","),
            "Com imagem": _kw(len(img)), "Data(s) da imagem": ", ".join(datas) or "—",
            "Excesso de detecções": f"{r.loc[m.municipio, 'excesso_det_total']:.1f}".replace(".", ","),
            "Resíduo (instalações)": f"{m.residuo_satelite:.1f}".replace(".", ","),
        })
    tab_mun = pd.DataFrame(linhas)

    top = trafo.sort_values("parcela_defasagem_kw", ascending=False).head(10)
    tab_top = pd.DataFrame({
        "Transformador": top["id_transformador"], "Município": top["municipio"].map(lambda x: NOMES.get(x, x)),
        "BDGD (kW)": top["capacidade_bdgd_kw"].map(lambda v: f"{v:.1f}"),
        "Parcela da defasagem (kW)": top["parcela_defasagem_kw"].map(lambda v: f"{v:.1f}"),
        "Faixa (kW)": [f"{a:.1f}–{b:.1f}" for a, b in zip(top["faixa_min_kw"], top["faixa_max_kw"])],
        "Método": top["metodo_alocacao"],
    })
    visao = trafo[trafo["metodo_alocacao"] == "visao"]
    mudou = (visao.assign(dif=(visao["parcela_defasagem_kw"] - visao["parcela_fallback_kw"]).abs())
             .sort_values("dif", ascending=False).head(10))
    tab_visao = pd.DataFrame({
        "Transformador": mudou["id_transformador"], "Excesso de detecções": mudou["excesso_det"].map(lambda v: f"{v:.1f}"),
        "Com visão (kW)": mudou["parcela_defasagem_kw"].map(lambda v: f"{v:.2f}"),
        "100% fallback (kW)": mudou["parcela_fallback_kw"].map(lambda v: f"{v:.2f}"),
    })

    susp = c["aneel"]["suspensao"]
    flags_mun = "\n".join(f"- **{NOMES.get(m.municipio, m.municipio)}**: {m.flags or 'nenhuma'}" for m in mun.itertuples())
    cont_flags = trafo["flags"].str.split(";").explode().loc[lambda s: s.str.len() > 0].value_counts()
    tab_flags = pd.DataFrame({"Flag": cont_flags.index, "Transformadores": cont_flags.map(_kw).values})
    n_det = int((det["confianca"] >= conf_min).sum()) if len(det) else 0
    sem_aneel = u[u["sem_aneel"]]
    txt = f"""# Conciliação da capacidade de MMGD — área piloto

Gerado por `python -m src.spatial.conciliacao` em {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC.
Método, premissas e limitações: [docs/metodo_conciliacao.md](../metodo_conciliacao.md).

- **Data-base da BDGD:** {', '.join(sorted({d.date().isoformat() for d in data_base.values()}))} (LIGHT e Enel RJ, extrato V11).
- **Data de referência (data_ref):** {data_ref.date().isoformat()} (cadastro da ANEEL gerado em {data_geracao.date().isoformat()}).
- **Área piloto:** {'; '.join(f"{s}: {', '.join(NOMES.get(x, x) for x in ms)}" for s, ms in piloto().items())}.
- **Visão computacional:** {meta_visao.get('tiles_varridos', 0)} ladrilhos Esri z{meta_visao.get('zoom', '—')} varridos,
  {len(det)} detecções agrupadas, {n_det} com confiança ≥ {conf_min}.

## Números-chave por município

{_tabela(tab_mun)}

Capacidade BDGD = potência do **cadastro da ANEEL** para o mesmo CEG, localizada no transformador pela BDGD
(CEG sem cadastro: POT_INST da BDGD, {len(sem_aneel)} empreendimentos, {_kw(sem_aneel['pot_kw'].sum())} kW).
Só as unidades de baixa tensão (UGBT) têm transformador MT/BT; a razão de cobertura usa todas (UGBT, UGMT, UGAT).

## Cobertura BDGD × ANEEL

Faixa de confiança: {c['cobertura']['faixa'][0]}–{c['cobertura']['faixa'][1]}. Flags por município:

{flags_mun}

Recadastro depois da data-base (possível dupla contagem: está na BDGD e também na defasagem, porque a única
data do cadastro é a da última atualização cadastral): {'; '.join(f"{NOMES.get(k, k)} {_kw(v)} kW" for k, v in dupla_kw.items())}.

## Maiores parcelas de defasagem por transformador

{_tabela(tab_top)}

## Onde a visão mudou a alocação

{_tabela(tab_visao) if len(tab_visao) else 'A visão não alterou nenhuma alocação: sem imagem posterior à data-base com excesso de detecções.'}

## Flags por transformador

{_tabela(tab_flags) if len(tab_flags) else 'Nenhuma.'}

## Limitações

- A ANEEL não publica data de conexão: a série usa a data da **última atualização cadastral**. A migração
  SISGD → MMGD ({susp['inicio']} a {susp['fim']}) e o acúmulo de {susp['acumulo_dias']} dias depois ficam
  marcados (`flag_suspensao`, `flag_pos_suspensao` em `capacidade_aneel_municipio.parquet`), não corrigidos.
- Os últimos meses do cadastro chegam incompletos (inserção atrasada): `data_ref` perto da geração do arquivo
  subestima a defasagem.
- O detector (`best.pt`, treinado em Google z20) perde sensibilidade na Esri z19: a contagem de detecções é um
  piso, e o excesso tende a zero. Ver a medição em docs/metodo_conciliacao.md.
- A imagem Esri do Rio é anterior à data-base da BDGD: ali a visão não aloca defasagem, só gera resíduo.
- Área atendida = célula de Voronoi dos transformadores (raio máximo {c['areas_trafo']['raio_max_m']} m), não o
  traçado real da rede de BT. Transformadores no mesmo posto dividem a célula.
- Resíduo e excesso NÃO entram na capacidade (instalações aguardando conexão, falsos positivos e irregulares).
"""
    destino = saida("relatorio")
    ensure(destino.parent)
    destino.write_text(txt, encoding="utf-8")
    return txt
