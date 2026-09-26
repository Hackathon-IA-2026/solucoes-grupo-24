"""Monta o JSON do contrato (os recursos do dashboard, tabela RECURSOS) e publica no banco.

`montar_contrato()` é a ÚNICA função que monta o contrato (docs/contexto dos prompts.txt): o
banco e o arquivo de exportação (output/contrato.json) saem dela, então os dois não divergem.

Origem de cada recurso hoje:
| recurso    | origem                                                      | mock  |
|------------|-------------------------------------------------------------|-------|
| carga      | data/processed: carga_supervisionada + capacidade_mmgd      | false |
| previsao   | previsões fora da amostra (etapa 4: src/models/carga.py);   | true* |
|            | fatoresClimaticos ainda do mock (sem fonte meteorológica)   |       |
| riscos     | classificador ENE/CNF (etapa 4: src/models/curtailment.py); | true* |
|            | `distribuidora` ainda sem definição (decisão do Luiz);      |       |
|            | `lat`/`lon` = sede da UF (sem coordenada por usina)         |       |
| alertas    | mesmo classificador + SHAP exato do LightGBM                | false |
| excedentes | MMGD por área de influência (BDGD × ANEEL) × fator de geração e carga   | false |
|            | da área RJ (ONS), persistência sazonal (src/spatial)        |       |
| validacao  | backtest (src/models/metricas.py) + manifesto de download   | false |
|            | + metadados do treino (src/models/carga.py)                 |       |
| mmgd_densidade | capacidade de MMGD por área de influência (src/spatial/construir.py) | false |
* Registro com qualquer parte mock é mock inteiro: a curva é real, mas os fatores climáticos
  não, então `mock: true` até existir fonte meteorológica (ou o contrato mudar); o risco é
  real, mas o campo `distribuidora` não, então `mock: true` até o Luiz definir o que ele
  mostra (docs/real_vs_mock.md). O dashboard mostra a etiqueta "mock" nesses cards.

Os mocks vêm dos MESMOS arquivos que o dashboard usa no modo mock (Frontend/.../mock/*.json):
uma cópia só. Todo item mock precisa ter "mock": true, senão a publicação falha (regra "nunca
inventar dados": mock sem flag poderia ser lido como real).
"""
from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

from pipeline.explicabilidade import ExplicadorLightGBM, explicar_saida
from pipeline.gerar_alertas_mock import para_contrato_dashboard
from src.contrato.modelos import (AlertaDetalhado, CargaSnapshot, DensidadeMmgd, ErroDiario,
                                  ExcedenteTsoDso, FatoresClimaticos, MetricasValidacao, ModeloInfo,
                                  Periodo, PontoPrevisao, PrevisaoCurva, RiscoUsina, StatusFonte)
from src.db import migracoes, repositorio
from src.db.sessao import nova_sessao
from src.features.carga import SUBSISTEMAS
from src.ingestion import download
from src.features.curtailment import rotulo_explicacao
from src.models import carga as mc
from src.models import curtailment as mcur
from src.models import metricas as mt
from src.processing.saidas import SAIDA_CALENDARIO, SAIDA_CAPACIDADE_MMGD, SAIDA_CARGA, SAIDA_CARGA_AREA
from src.spatial import excedentes as ex
from src.spatial.saidas import SAIDA_CARGA_AREA_INFLUENCIA, SAIDA_MMGD_DIARIA, SAIDA_MMGD_AREA_INFLUENCIA
from src.utils.config import carregar
from src.utils.paths import DASHBOARD_MOCK, RAIZ, ensure
from src.utils.tempo import FUSO, PASSO, para_utc

# Recursos ainda servidos do mock do dashboard. Vazio desde a Fase 6 (excedentes e densidade de
# MMGD passaram a sair de src/spatial); o mecanismo fica para o próximo recurso sem fonte real.
RECURSOS_MOCK: tuple[str, ...] = ()
# Sem fonte meteorológica, os fatores climáticos da curva vêm do mock -> curva inteira mock=True.
# Vira True quando houver ERA5/previsão numérica (e a curva passa a mock=False sozinha).
FATORES_CLIMATICOS_REAIS = False
# O contrato exige `distribuidora` no risco, mas o que ele deve mostrar para usinas da rede
# básica ainda não foi definido (decisão pendente do Luiz, docs/FASES.md). Até lá o campo leva
# este texto e o risco inteiro sai mock=True. Ao definir: preencher de verdade e trocar para None.
DISTRIBUIDORA_PENDENTE: str | None = "a definir"
# Não há coordenada por usina no que o projeto ingere (as bases do ONS não trazem; a do SIGA/ANEEL
# ainda não entra). O Mapa Híbrido recebe a SEDE DA UF (config/publicacao.yaml: posicao_uf), uma
# aproximação -> risco mock=True enquanto isto for False. Ao ingerir a coordenada real, trocar.
POSICAO_USINA_REAL = False
FONTES_CONTRATO = {"eolica": "Eólica", "solar": "Solar FV"}


def resolver_agora(valor: str) -> pd.Timestamp | None:
    """config `agora` -> horário local do projeto (naive) ou None (= último dado)."""
    if valor == "ultimo_dado":
        return None
    t = pd.Timestamp(valor)
    if t.tzinfo is None:
        raise ValueError(f"publicacao.yaml: 'agora' sem fuso ({valor}); use ex. 2025-08-10T13:00:00-03:00")
    return t.tz_convert(FUSO).tz_localize(None)


def snapshot_carga(carga: pd.DataFrame, capacidade: pd.DataFrame,
                   agora: pd.Timestamp | None = None) -> CargaSnapshot:
    """Retrato da carga do SIN no "agora" (dado real, mock=False).

    - Instante: a última semi-hora (≤ agora, se dado) em que os 4 subsistemas têm carga global
      E MMGD. Soma parcial de subsistemas nunca vira "SIN".
    - SIN = soma dos 4 subsistemas; supervisionada = global − MMGD (mesma regra do contrato).
    - percentualMmgdNaGeracao = MMGD ÷ carga global × 100. Decisão: a carga global é toda a
      geração que atende a demanda (supervisionada + MMGD), então esta é a participação da
      MMGD no atendimento, no mesmo sentido da Figura 7 do plano (PAR/PEL).
    - mmgdSobreCapacidadeInstalada = MMGD estimada pelo ONS ÷ potência cadastrada na ANEEL até
      a data do instante (sem cadastros futuros). O cadastro cobre todo o país (inclusive
      sistemas isolados), a estimativa do ONS só o SIN: a razão fica levemente subestimada.
    """
    c = carga[carga["subsistema"].isin(SUBSISTEMAS)].copy()
    c["timestamp"] = pd.to_datetime(c["timestamp"])
    if agora is not None:
        c = c[c["timestamp"] <= agora]
    ok = c.dropna(subset=["carga_global", "mmgd_estimada"])
    completos = ok.groupby("timestamp")["subsistema"].nunique()
    completos = completos[completos == len(SUBSISTEMAS)]
    if completos.empty:
        raise LookupError(f"nenhuma semi-hora com os 4 subsistemas completos até {agora}")
    t = completos.index.max()
    linha = ok[ok["timestamp"] == t]
    global_mw, mmgd_mw = float(linha["carga_global"].sum()), float(linha["mmgd_estimada"].sum())

    cap = capacidade.copy()
    cap["data"] = pd.to_datetime(cap["data"])
    ate = cap[cap["data"] <= t.normalize()]
    cap_mw = float(ate.groupby("uf")["potencia_acumulada_mw"].last().sum())
    if cap_mw <= 0:
        raise LookupError(f"sem capacidade de MMGD cadastrada até {t.date()}")

    return CargaSnapshot(
        mock=False,
        timestamp_utc=_utc(t),
        carga_global_mw=round(global_mw, 1),
        mmgd_estimada_mw=round(mmgd_mw, 1),
        carga_supervisionada_mw=round(global_mw, 1) - round(mmgd_mw, 1),
        percentual_mmgd_na_geracao=round(100 * mmgd_mw / global_mw, 2),
        mmgd_sobre_capacidade_instalada=round(mmgd_mw / cap_mw, 4),
    )


def _utc(t: pd.Timestamp):
    """Horário local do projeto -> datetime UTC (o contrato só trafega UTC)."""
    return para_utc(pd.Series([t])).iloc[0].to_pydatetime()


def _rampa(p50: list[float], janela_horas: float) -> float:
    """Maior subida do P50 em `janela_horas` (mesma regra do trechoDeRampa do dashboard)."""
    k = round(janela_horas * 2)
    return max(p50[i + k] - p50[i] for i in range(len(p50) - k))


def curvas_previsao(prev: pd.DataFrame, agora: pd.Timestamp, fatores: dict[str, dict]) -> list[PrevisaoCurva]:
    """As 3 curvas do Despacho Preditivo no "agora" (série publicada, modelo da config).

    Curva do horizonte h (em passos): as N semi-horas que TERMINAM em agora + h; cada ponto é a
    previsão emitida h antes do próprio alvo (modelo direto, janela deslizante). Assim toda
    emissão é <= agora: nenhum ponto usa dado posterior ao "agora" do replay.
    - D+1 (h = 48): as próximas 24 h inteiras, todas no futuro.
    - 3h / 30min: termina 3 h / 30 min à frente; o resto é a trajetória recente desse horizonte.
    """
    c = mc.cfg()
    n, pub, modelo = c["curva"]["pontos"], c["serie_publicada"], c["curva"]["modelo"]
    janela = c["curva"]["janela_rampa_horas"]
    sel = prev[(prev["serie"] == pub) & (prev["modelo"] == modelo)]
    curvas = []
    for nome_h, h in c["horizontes"].items():
        fim = agora + h * PASSO
        g = sel[(sel["horizonte"] == nome_h) & (sel["alvo"] > fim - n * PASSO) & (sel["alvo"] <= fim)]
        g = g.sort_values("alvo")
        if len(g) != n:
            raise LookupError(f"curva {nome_h}: {len(g)} de {n} pontos até {fim} (rode run_heavywork.py)")
        if (g["emissao"] > agora).any():  # invariante do replay; nunca deveria acontecer
            raise RuntimeError(f"curva {nome_h}: previsão emitida depois do agora ({agora})")
        pontos = [PontoPrevisao(timestamp=_utc(r.alvo), p10=round(r.p10, 1), p50=round(r.p50, 1),
                                p90=round(r.p90, 1)) for r in g.itertuples()]
        curvas.append(PrevisaoCurva(
            mock=not FATORES_CLIMATICOS_REAIS, horizonte=nome_h, pontos=pontos,
            rampa_projetada_mw=round(_rampa([p.p50 for p in pontos], janela), 1),
            janela_rampa_horas=janela,
            fatores_climaticos=FatoresClimaticos.model_validate(fatores[nome_h])))
    return curvas


def metricas_validacao(prev: pd.DataFrame, agora: pd.Timestamp, fontes: list[dict],
                       treino: dict) -> MetricasValidacao:
    """Tela Validação: backtest fora da amostra da série publicada até o "agora".

    Métricas sobre todo o período de teste com real conhecido até o agora (mesmas funções do
    relatório docs/reports/baseline_carga.md); histórico = últimos N dias completos NOS DOIS
    (modelo e baseline, lado a lado no gráfico). `treino` = mc.metadados_treino().
    Períodos do modelo: treino = split da config; teste = do início do teste até o último dia
    com real conhecido até o agora (o que as métricas de fato cobrem).
    """
    c = mc.cfg()
    v = c["validacao"]
    p = prev[(prev["serie"] == c["serie_publicada"]) & (prev["horizonte"] == v["horizonte"])
             & (prev["alvo"] <= agora)]
    p = mt.com_real(p)
    modelo, clima = p[p["modelo"] == v["modelo"]], p[p["modelo"] == v["climatologia"]]
    if modelo.empty:
        raise LookupError(f"sem previsões fora da amostra com real conhecido até {agora}")
    m = mt.basicas(modelo)
    dm, dc = mt.erro_diario(modelo), mt.erro_diario(clima)
    diario = dm[dm["n"] == 48].merge(dc[dc["n"] == 48], on="data", suffixes=("", "_base"))
    diario = diario.tail(v["dias_historico"])
    sp = mc.split()
    info = ModeloInfo(
        nome=v["nome_modelo"], versao=treino["versao"], data_treino=treino["dataTreino"],
        periodo_treino=Periodo(inicio=sp.inicio_treino.date(), fim=sp.fim_treino.date()),
        periodo_teste=Periodo(inicio=sp.inicio_teste.date(), fim=modelo["data"].max().date()))
    return MetricasValidacao(
        mock=False,
        erro_medio_absoluto_mw=round(m["mae"], 1),
        rmse_mw=round(m["rmse"], 1),
        mape_pct=round(m["mape"], 2),
        skill_vs_climatologia=round(mt.skill(m["mae"], mt.basicas(clima)["mae"]), 3),
        baseline_nome=v["nome_baseline"],
        historico_erro30d=[ErroDiario(data=r.data.date(), mae=round(r.mae, 1), rmse=round(r.rmse, 1),
                                      mae_baseline=round(r.mae_base, 1), rmse_baseline=round(r.rmse_base, 1))
                           for r in diario.itertuples()],
        modelo=info,
        status_fontes=[StatusFonte.model_validate(f) for f in fontes],
    )


def _severidade(prob_pct: float, limiares: dict[str, float]) -> str:
    """Primeiro nível (de cima para baixo) cujo limiar a probabilidade atinge."""
    return next(nivel for nivel, lim in limiares.items() if prob_pct >= lim)


def _id_risco(chave: str) -> str:
    """"eolica:BACLA2X" -> "eolica-bacla2x" (id estável, legível na URL do dashboard)."""
    return chave.replace(":", "-").lower()


def riscos_e_alertas(agora: pd.Timestamp) -> tuple[list[RiscoUsina], list[AlertaDetalhado]]:
    """Lista de Riscos e Detalhe do Alerta no "agora" (classificador de curtailment).

    - Emissão usada: a mais recente <= agora (as bases de constrained-off atrasam em relação
      à carga; `atualizadoHaMin` mostra essa defasagem em vez de escondê-la).
    - Por usina: entre horizontes e razões, a previsão de maior montante esperado
      (P(corte) × E[MW | corte]); lista = as N usinas de maior montante.
    - Alerta: motivos = probabilidade de cada razão (normalizada a 100%) no mesmo alvo;
      variáveis = SHAP exato do LightGBM da razão escolhida, agrupado em rótulos legíveis.
    """
    c = mcur.cfg()
    pc = c["publicacao"]
    razoes = [r.lower() for r in c["razoes"]]
    emissoes = mcur.ler_previsoes(colunas=["emissao"])["emissao"]
    emissoes = emissoes[emissoes <= agora]
    if emissoes.empty:
        raise LookupError(f"sem previsão de curtailment emitida até {agora}")
    emissao = emissoes.max()
    p = mcur.ler_previsoes(filtros=[("emissao", "=", emissao)])
    p["chave"] = p["chave"].astype(str)
    p["horizonte"] = p["horizonte"].astype(str)
    mont = p[[f"montante_{r}" for r in razoes]].to_numpy()
    p["razao"] = [c["razoes"][i] for i in mont.argmax(axis=1)]
    p["montante"] = mont.max(axis=1)
    p["prob"] = [getattr(row, f"p_{row.razao.lower()}") for row in p.itertuples()]
    melhores = (p.sort_values("montante", ascending=False).drop_duplicates("chave")
                .head(pc["top_usinas"]))
    usinas = pd.read_parquet(mcur.ARQ_USINAS).set_index("chave")
    posicao_uf = carregar("publicacao")["posicao_uf"]
    cal = pd.read_csv(SAIDA_CALENDARIO, usecols=["timestamp", "faixa_curtailment"], parse_dates=["timestamp"])
    faixa = cal.set_index("timestamp")["faixa_curtailment"]
    contribs = mcur.explicar(melhores[["chave", "horizonte", "alvo", "razao"]])

    riscos, alertas = [], []
    for row, contrib in zip(melhores.itertuples(), contribs):
        u = usinas.loc[row.chave]
        prob_pct = round(100 * float(row.prob), 1)
        if u["uf"] not in posicao_uf:  # UF nova sem posição: falha aqui, não um ponto no oceano
            raise KeyError(f"config/publicacao.yaml: posicao_uf sem a UF {u['uf']!r}")
        lat, lon = posicao_uf[u["uf"]]
        risco = RiscoUsina(
            mock=DISTRIBUIDORA_PENDENTE is not None or not POSICAO_USINA_REAL,
            id=_id_risco(row.chave), nome=u["nom_usina"], uf=u["uf"], lat=lat, lon=lon,
            distribuidora=DISTRIBUIDORA_PENDENTE or "", fonte=FONTES_CONTRATO[u["fonte"]],
            razao=row.razao, probabilidade_pct=prob_pct, montante_mw=round(float(row.montante), 1),
            horizonte=row.horizonte, severidade=_severidade(prob_pct, pc["severidade"]),
            acao_recomendada=pc["acao"][row.razao].format(faixa=faixa[row.alvo]))
        riscos.append(risco)

        agrupado: dict[str, float] = {}
        for feat, v in contrib.items():
            rot = rotulo_explicacao(feat)
            agrupado[rot] = agrupado.get(rot, 0.0) + v
        principais = dict(sorted(agrupado.items(), key=lambda kv: -abs(kv[1]))[:pc["variaveis_shap"]])
        saida = {
            "probabilidade": float(row.prob), "montante_mw": risco.montante_mw, "usina": risco.nome,
            "horario_previsto": _utc(row.alvo), "janela_previsao": row.horizonte,
            "motivos": {r.upper(): float(getattr(row, f"p_{r}")) for r in razoes},
            "dataset_origem": pc["dataset"][u["fonte"]], "atualizado_em": _utc(emissao), "mock": False,
        }
        payload = explicar_saida(saida, ExplicadorLightGBM(principais), agora=_utc(agora))
        alertas.append(AlertaDetalhado.model_validate(para_contrato_dashboard(payload, risco.id)))
    return riscos, alertas


def excedentes_tso_dso(agora: pd.Timestamp) -> list[ExcedenteTsoDso]:
    """Tela Excedentes: áreas de influência da área piloto com maior excedente de MMGD previsto (24 h).

    Método em src/spatial/excedentes.py e docs/metodo_espacial.md. Dado real (mock=False):
    capacidade da BDGD × ANEEL, carga e MMGD do ONS; a previsão é persistência sazonal, sem
    nenhum dado posterior ao agora. Posição = a subestação (a fronteira TSO–DSO).
    """
    c = carregar("espacial")
    ce = c["excedentes"]
    areas = pd.read_csv(SAIDA_MMGD_AREA_INFLUENCIA, dtype={"cod_sub": str})
    cap = ex.capacidade_no_agora(pd.read_csv(SAIDA_MMGD_DIARIA), agora)
    fator = ex.fator_geracao(pd.read_csv(SAIDA_CARGA_AREA), pd.read_csv(SAIDA_CAPACIDADE_MMGD), c["uf"])
    prev = ex.prever(fator, cap, pd.read_csv(SAIDA_CARGA_AREA_INFLUENCIA), agora,
                     max(ce["horizontes"].values()), ce["defasagem_sazonal_passos"])
    sel = ex.selecionar(ex.pico_por_area(prev, ce["horizontes"]), areas, ce)
    return [ExcedenteTsoDso(mock=False, area_concessao=r.area, distribuidora=r.distribuidora,
                            lat=r.lat_sub, lon=r.lon_sub, fonte=r.fonte,
                            excedente_mw=round(float(r.excedente_mw), 1), prioridade=r.prioridade,
                            horizonte=r.horizonte, acao_recomendada=r.acao)
            for r in sel.itertuples()]


def densidade_mmgd() -> DensidadeMmgd:
    """Camada de calor do Mapa Híbrido: capacidade de MMGD por área de influência (dado real)."""
    areas = pd.read_csv(SAIDA_MMGD_AREA_INFLUENCIA)
    return DensidadeMmgd(mock=False, descricao=carregar("espacial")["densidade"]["descricao"],
                         pontos=ex.pontos_densidade(areas))


def ler_mock(recurso: str) -> list | dict:
    """Mock do dashboard para um recurso; recusa qualquer item sem "mock": true."""
    dados = json.loads((DASHBOARD_MOCK / f"{recurso}.json").read_text(encoding="utf-8"))
    itens = dados if isinstance(dados, list) else [dados]
    sem_flag = [i for i, x in enumerate(itens) if x.get("mock") is not True]
    if sem_flag:
        raise ValueError(f"mock {recurso}.json: itens {sem_flag} sem \"mock\": true")
    return dados


def montar_contrato() -> tuple[dict, datetime]:
    """Os recursos do contrato (RECURSOS) + o instante de referência (UTC). Função única (DRY)."""
    cfg = carregar("publicacao")
    carga = snapshot_carga(pd.read_csv(SAIDA_CARGA), pd.read_csv(SAIDA_CAPACIDADE_MMGD),
                           resolver_agora(str(cfg["agora"])))
    # O "agora" de todos os recursos é o instante do snapshot (último dado completo até o
    # agora configurado), em horário local do projeto, como as tabelas processadas.
    agora = pd.Timestamp(carga.timestamp_utc).tz_convert(FUSO).tz_localize(None)
    prev = mc.ler_previsoes()
    fatores = {c["horizonte"]: c["fatoresClimaticos"] for c in ler_mock("previsao")}
    riscos, alertas = riscos_e_alertas(agora)
    recursos = {
        "riscos": [r.para_json() for r in riscos],
        "alertas": [a.para_json() for a in alertas],
        "carga": carga.para_json(),
        "previsao": [c.para_json() for c in curvas_previsao(prev, agora, fatores)],
        "validacao": metricas_validacao(prev, agora, download.status_fontes(cfg["status_fontes"]),
                                        mc.metadados_treino()).para_json(),
        "excedentes": [e.para_json() for e in excedentes_tso_dso(agora)],
        "mmgd_densidade": densidade_mmgd().para_json(),
        **{r: ler_mock(r) for r in RECURSOS_MOCK},
    }
    return recursos, carga.timestamp_utc


def publicar() -> str:
    """Etapa 5: monta, exporta output/contrato.json, atualiza o schema do banco e grava."""
    recursos, instante = montar_contrato()
    cfg = carregar("publicacao")
    export = RAIZ / cfg["arquivo_export"]
    ensure(export.parent)
    export.write_text(json.dumps({"instanteReferencia": instante.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                  "recursos": recursos}, ensure_ascii=False, indent=1), encoding="utf-8")
    migracoes.atualizar_banco()
    with nova_sessao() as sessao:
        execucao_id = repositorio.publicar(sessao, recursos, instante, origem="run_heavywork")
    reais = [r for r, v in recursos.items() if not (v if isinstance(v, list) else [v])[0]["mock"]]
    return (f"execução {execucao_id}, agora = {instante:%Y-%m-%d %H:%M} UTC; "
            f"dado real: {reais}; mock: {[r for r in recursos if r not in reais]}")
