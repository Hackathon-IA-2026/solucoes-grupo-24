"""Relatório do backtest da demanda de meses (docs/reports/demanda_meses.md + CSV de métricas).

Chamado pela etapa `demanda_meses` (src/models/demanda_meses.py::executar). Só formata: toda
conta está em demanda_meses.py.
"""
from __future__ import annotations

import pandas as pd

from src.models import demanda_meses as dm
from src.utils.paths import ensure


def _tabela(df: pd.DataFrame, colunas: list[str], fmt: dict) -> str:
    """Tabela markdown simples (sem depender do `tabulate`)."""
    linhas = ["| " + " | ".join(colunas) + " |", "|" + "---|" * len(colunas)]
    for r in df[colunas].itertuples(index=False):
        linhas.append("| " + " | ".join(fmt.get(c, "{}").format(v) if pd.notna(v) else "—"
                                        for c, v in zip(colunas, r)) + " |")
    return "\n".join(linhas)


def escrever(met: pd.DataFrame, fr: pd.DataFrame, bt: pd.DataFrame) -> str:
    c = dm.cfg()
    ensure(dm.caminho("metricas").parent)
    met.to_csv(dm.caminho("metricas"), index=False)
    teste = bt[bt["emissao"] >= pd.Timestamp(c["backtest"]["primeira_emissao"])]
    fmt = {"mae_mw": "{:,.0f}", "mape_pct": "{:.2f}", "vies_mw": "{:+,.0f}",
           "mae_minima_diurna_mw": "{:,.0f}", "mae_ponta_noturna_mw": "{:,.0f}",
           "cobertura_p10_p90": "{:.0%}", "skill_vs_sazonal_ingenuo": "{:+.3f}",
           "skill_vs_persistencia_semanal": "{:+.3f}", "horizonte_mes": "{}"}

    # Resumo: média sobre horizontes (cada horizonte pesa igual) por série e modelo.
    res = (met.groupby(["serie", "modelo"])[["mae_mw", "mape_pct", "skill_vs_sazonal_ingenuo",
                                             "cobertura_p10_p90"]].mean().reset_index())
    ordem = {s: i for i, s in enumerate(c["series"])}
    res = res.sort_values(["serie", "mae_mw"], key=lambda s: s.map(ordem) if s.name == "serie" else s)

    # Critério de aceite da Fase 1: skill > 0 sobre o sazonal ingênuo (variante sem tempo, a
    # que existe para meses à frente), por série, na média dos horizontes.
    clim = res[res["modelo"] == "clim"].set_index("serie")["skill_vs_sazonal_ingenuo"]
    aceite = ", ".join(f"{s} {v:+.3f}" for s, v in clim.items())

    det = met[met["modelo"].isin(c["variantes"] + ["sazonal_ingenuo"])].sort_values(
        ["serie", "horizonte_mes", "modelo"], key=lambda s: s.map(ordem) if s.name == "serie" else s)
    sin = fr[fr["serie"] == "SIN"]
    mensal = (sin.assign(m=sin["timestamp"].dt.to_period("M").astype(str))
              .groupby("m")[["p10", "p50", "p90"]].mean().reset_index())
    mensal.columns = ["mês", "P10 (MWmed)", "P50 (MWmed)", "P90 (MWmed)"]

    texto = f"""# Demanda bruta para meses à frente — backtest (Fase 1)

Gerado por `src/models/demanda_meses.py` (etapa `demanda_meses` do `run_heavywork.py`).
Parâmetros: `Backend/config/demanda_meses.yaml`. Especificação: `docs/oraculo/especificacao/17-previsao-meses-carga-mmgd-pato.md`.

**Alvo:** demanda bruta = carga global consistida do ONS (não a supervisionada: a MMGD é
prevista à parte nas fases seguintes e a curva do pato é D − G). Resolução horária.

**Modelo:** nível dos últimos 12 meses × crescimento × índice sazonal mensal × perfil
(mês × dia-tipo × hora, últimos {c['perfil_anos']} anos) + sensibilidade à temperatura (β por mês × hora).
- `era5`: temperatura ERA5 observada nos alvos (**tempo perfeito**: teto do que o tempo previsto pode dar).
- `clim`: sem tempo (anomalia 0). É a variante publicada para a frente até o SEAS5 entrar (Fase 2).

**Backtest:** origem móvel, uma emissão no 1º dia de cada mês desde {c['backtest']['primeira_emissao']}
({teste['emissao'].nunique()} emissões de teste), horizontes de 1 a {c['backtest']['horizonte_meses']} meses,
{len(teste):,} previsões horárias com real conhecido. Crescimento no backtest: só a taxa histórica (o PLAN
2026-2030 2ª RQ saiu em 07/08/2026, depois do início do teste). Banda P10–P90: quantis do erro relativo
das {c['backtest']['calibracao_emissoes']} emissões anteriores, só com alvos já ocorridos na emissão.

**Baselines:** sazonal ingênuo (mesmo horário 364 dias antes × crescimento) e persistência semanal.

## Critério de aceite da Fase 1

Skill da variante `clim` (sem tempo) sobre o sazonal ingênuo, média dos horizontes: {aceite}.

## Resumo por série (média dos horizontes)

{_tabela(res, ["serie", "modelo", "mae_mw", "mape_pct", "skill_vs_sazonal_ingenuo", "cobertura_p10_p90"], fmt)}

## Por horizonte

{_tabela(det, ["serie", "horizonte_mes", "modelo", "mae_mw", "mape_pct", "vies_mw", "mae_minima_diurna_mw",
               "mae_ponta_noturna_mw", "cobertura_p10_p90", "skill_vs_sazonal_ingenuo"], fmt)}

## Previsão para a frente — SIN (média mensal)

Emitida em {fr['emissao'].iloc[0]:%Y-%m-%d %H:%M}, variante `{c['previsao']['variante']}`, crescimento
`{c['previsao']['tendencia']}` (taxa da carga global do SIN no PLAN 2026-2030 2ª RQ, aplicada a todos os subsistemas).
Previsão horária completa em `Backend/{c['saidas']['previsao']}`.

{_tabela(mensal, list(mensal.columns), {k: "{:,.0f}" for k in mensal.columns if k != "mês"})}

## Limitações

- Meses à frente sem previsão de tempo: a banda da variante `clim` inclui a variabilidade do tempo
  (é medida no erro real). A variante `era5` mostra quanto o tempo previsto poderia ganhar no máximo.
- **Banda ainda estreita nos horizontes longos:** a cobertura P10–P90 fica perto de 75–78% no mês 1
  e cai nos seguintes (meta da spec: 75–85%). A calibração vê só as 12 emissões anteriores, e o erro de
  nível de um ano inteiro (crescimento) mal aparece nelas. Próximo passo: CQR/janela maior (Fase 3).
- O último mês da previsão para a frente é parcial (emissão no meio do mês) e usa a banda do horizonte 6.
- A taxa do PLAN é do SIN; nos subsistemas é premissa.
- O sazonal ingênuo compara o mesmo dia da semana 364 dias antes: um feriado móvel pode cair em dia
  diferente (o modelo trata feriado como domingo; o baseline não).
- Mudanças estruturais (tarifa branca, veículo elétrico, BESS atrás do medidor) não estão modeladas.
"""
    ensure(dm.caminho("relatorio").parent)
    dm.caminho("relatorio").write_text(texto, encoding="utf-8")
    return f"relatório em {dm.caminho('relatorio').name}"
