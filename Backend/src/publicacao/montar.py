"""Monta o JSON do contrato (os recursos do dashboard, tabela RECURSOS) e publica no banco.

`montar_contrato()` é a ÚNICA função que monta o contrato (docs/contexto dos prompts.txt): o
banco e o arquivo de exportação (output/contrato.json) saem dela, então os dois não divergem.

Origem de cada recurso hoje:
| recurso    | origem                                                      | mock  |
|------------|-------------------------------------------------------------|-------|
| carga      | data/processed: carga_supervisionada + capacidade_mmgd      | false |
| previsao   | previsões fora da amostra (etapa 4: src/models/carga.py);   | false*|
|            | fatoresClimaticos: Open-Meteo (ECMWF IFS) por UF, ponderado |       |
|            | pela MMGD cadastrada; mock só se o tempo não cobrir a janela|       |
| riscos     | classificador ENE/CNF (etapa 4: src/models/curtailment.py); | false*|
|            | `distribuidora` = ponto de conexão (base tm do ONS);        |       |
|            | `lat`/`lon` = coordenada do SIGA/ANEEL (usinas_cadastro)    |       |
| alertas    | mesmo classificador + SHAP exato do LightGBM                | false |
| excedentes | MMGD por área de influência (BDGD × ANEEL) × fator de geração e carga   | false |
|            | da área RJ (ONS), persistência sazonal (src/spatial)        |       |
| validacao  | backtest (src/models/metricas.py) + manifesto de download   | false |
|            | + metadados do treino (src/models/carga.py)                 |       |
| mmgd_densidade | capacidade de MMGD por área de influência (src/spatial/construir.py) | false |
| areas_influencia | polígonos das áreas de influência (GeoJSON) + MMGD e excedente | false |
|            | de cada uma (src/spatial/camada_mapa.py)                    |       |
* Registro com qualquer parte mock é mock inteiro: se o tempo baixado não cobre a janela de
  uma curva, os fatores dela vêm do mock e a curva sai `mock: true`. O risco de
  uma usina SEM coordenada no SIGA (~18% das usinas) sai na sede da UF e com `mock: true` só
  naquele registro (docs/real_vs_mock.md). O dashboard mostra a etiqueta "mock" nesses cards.

Os mocks vêm dos MESMOS arquivos que o dashboard usa no modo mock (Frontend/.../mock/*.json):
uma cópia só. Todo item mock precisa ter "mock": true, senão a publicação falha (regra "nunca
inventar dados": mock sem flag poderia ser lido como real).
"""
from __future__ import annotations

import json
from datetime import datetime

import geopandas as gpd
import pandas as pd

from pipeline.explicabilidade import ExplicadorLightGBM, explicar_saida
from pipeline.gerar_alertas_mock import para_contrato_dashboard
from src.contrato.modelos import (AlertaDetalhado, AreasInfluencia, CargaSnapshot, DensidadeMmgd, ErroDiario,
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
from src.processing.saidas import (SAIDA_CALENDARIO, SAIDA_CAPACIDADE_MMGD, SAIDA_CARGA, SAIDA_CARGA_AREA,
                                   SAIDA_CLIMA_UF, SAIDA_USINAS_CADASTRO)
from src.spatial import camada_mapa
from src.spatial import excedentes as ex
from src.spatial.saidas import (SAIDA_AREAS_INFLUENCIA_GEOJSON, SAIDA_CARGA_AREA_INFLUENCIA,
                                SAIDA_MMGD_AREA_INFLUENCIA, SAIDA_MMGD_DIARIA)
from src.utils.config import carregar
from src.utils.paths import DASHBOARD_MOCK, RAIZ, ensure
from src.utils.tempo import FUSO, PASSO, para_utc

# Recursos ainda servidos do mock do dashboard. Vazio desde a Fase 6 (excedentes e densidade de
# MMGD passaram a sair de src/spatial); o mecanismo fica para o próximo recurso sem fonte real.
RECURSOS_MOCK: tuple[str, ...] = ()
# Campo `distribuidora` do risco (decisão do Tiago, 2026-09-26): usinas eólicas e solares do
# constrained-off se conectam à rede básica, sem distribuidora; o campo mostra o PONTO DE CONEXÃO
# publicado pelo ONS (nom_pontoconexao da base tm), com este prefixo. Posição no mapa: coordenada
# do SIGA/ANEEL (média das usinas do conjunto, ponderada pela potência); sem ela, a sede da UF
# (config/publicacao.yaml: posicao_uf) e o registro sai mock=True.
PREFIXO_CONEXAO = "Conexão: "
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


def pesos_mmgd_uf(capacidade: pd.DataFrame, agora: pd.Timestamp) -> pd.Series:
    """Peso de cada UF = MMGD cadastrada (ANEEL) até o agora (sem cadastros futuros), em MW."""
    cap = capacidade.assign(data=pd.to_datetime(capacidade["data"]))
    cap = cap[cap["data"] <= agora]
    return cap.sort_values("data").groupby("uf")["potencia_acumulada_mw"].last()


def fatores_climaticos(clima: pd.DataFrame, pesos: pd.Series, inicio: pd.Timestamp,
                       fim: pd.Timestamp) -> FatoresClimaticos | None:
    """Fatores climáticos de uma curva: tempo na janela [inicio, fim], média das UFs ponderada
    pela MMGD cadastrada em cada uma (onde está a geração que a curva "desconta").

    - radiação: média só das horas com sol (radiação média > 0): a média de 24 h, com a noite,
      não diz nada sobre a MMGD; vento, temperatura e nuvens: média da janela inteira.
    - Devolve None (e a curva cai no mock, com mock=True) se faltar alguma hora da janela ou
      alguma UF com peso: fator calculado com buraco seria dado inventado por omissão.
    """
    horas = pd.date_range(inicio.floor("h"), fim.floor("h"), freq="h")
    c = clima[clima["timestamp"].isin(horas) & clima["uf"].isin(pesos.index)]
    if len(c) != len(horas) * len(pesos) or c.isna().any().any():
        return None
    w = c["uf"].map(pesos)
    cols = ["radiacao_w_m2", "vento_ms", "temperatura_c", "nuvens_pct"]
    por_hora = c[cols].mul(w, axis=0).groupby(c["timestamp"]).sum().div(w.groupby(c["timestamp"]).sum(), axis=0)
    sol = por_hora["radiacao_w_m2"] > 0
    return FatoresClimaticos(
        radiacao_solar=round(float(por_hora.loc[sol, "radiacao_w_m2"].mean()) if sol.any() else 0.0),
        vento_ms=round(float(por_hora["vento_ms"].mean()), 1),
        temperatura_c=round(float(por_hora["temperatura_c"].mean()), 1),
        cobertura_nuvens_pct=round(float(por_hora["nuvens_pct"].mean())))


def curvas_previsao(prev: pd.DataFrame, agora: pd.Timestamp, fatores: dict[str, dict],
                    clima: pd.DataFrame | None = None, pesos_uf: pd.Series | None = None) -> list[PrevisaoCurva]:
    """As 3 curvas do Despacho Preditivo no "agora" (série publicada, modelo da config).

    Fatores climáticos: do tempo real (`clima` + `pesos_uf`, ver `fatores_climaticos`) quando ele
    cobre a janela da curva; senão, os do mock (`fatores`) e a curva sai mock=True.

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
    fatores_reais: dict[str, FatoresClimaticos] = {}
    curvas = []
    for nome_h, h in c["horizontes"].items():
        fim = agora + h * PASSO
        g = sel[(sel["horizonte"] == nome_h) & (sel["alvo"] > fim - n * PASSO) & (sel["alvo"] <= fim)]
        g = g.sort_values("alvo")
        if len(g) != n:
            raise LookupError(f"curva {nome_h}: {len(g)} de {n} pontos até {fim} (rode run_heavywork.py)")
        if (g["emissao"] > agora).any():  # invariante do replay; nunca deveria acontecer
            raise RuntimeError(f"curva {nome_h}: previsão emitida depois do agora ({agora})")
        if clima is not None:
            f = fatores_climaticos(clima, pesos_uf, g["alvo"].min(), g["alvo"].max())
            if f is not None:
                fatores_reais[nome_h] = f
        pontos = [PontoPrevisao(timestamp=_utc(r.alvo), p10=round(r.p10, 1), p50=round(r.p50, 1),
                                p90=round(r.p90, 1)) for r in g.itertuples()]
        curvas.append(PrevisaoCurva(
            mock=nome_h not in fatores_reais, horizonte=nome_h, pontos=pontos,
            rampa_projetada_mw=round(_rampa([p.p50 for p in pontos], janela), 1),
            janela_rampa_horas=janela,
            fatores_climaticos=fatores_reais.get(nome_h) or FatoresClimaticos.model_validate(fatores[nome_h])))
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
    cadastro = pd.read_csv(SAIDA_USINAS_CADASTRO).set_index("chave")
    posicao_uf = carregar("publicacao")["posicao_uf"]
    cal = pd.read_csv(SAIDA_CALENDARIO, usecols=["timestamp", "faixa_curtailment"], parse_dates=["timestamp"])
    faixa = cal.set_index("timestamp")["faixa_curtailment"]
    contribs = mcur.explicar(melhores[["chave", "horizonte", "alvo", "razao"]])

    riscos, alertas = [], []
    for row, contrib in zip(melhores.itertuples(), contribs):
        u = usinas.loc[row.chave]
        prob_pct = round(100 * float(row.prob), 1)
        cad = cadastro.loc[row.chave] if row.chave in cadastro.index else None
        coord_real = cad is not None and pd.notna(cad["lat"]) and pd.notna(cad["lon"])
        if coord_real:
            lat, lon = float(cad["lat"]), float(cad["lon"])
        else:
            if u["uf"] not in posicao_uf:  # UF nova sem posição: falha aqui, não um ponto no oceano
                raise KeyError(f"config/publicacao.yaml: posicao_uf sem a UF {u['uf']!r}")
            lat, lon = posicao_uf[u["uf"]]
        # Sem ponto de conexão no cadastro não há o que mostrar: publicação falha (nunca inventa).
        if cad is None or pd.isna(cad["ponto_conexao"]):
            raise LookupError(f"{row.chave} sem ponto de conexão em {SAIDA_USINAS_CADASTRO.name}")
        risco = RiscoUsina(
            mock=not coord_real,
            id=_id_risco(row.chave), nome=u["nom_usina"], uf=u["uf"], lat=lat, lon=lon,
            distribuidora=PREFIXO_CONEXAO + str(cad["ponto_conexao"]), fonte=FONTES_CONTRATO[u["fonte"]],
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


def pico_excedentes(agora: pd.Timestamp) -> pd.DataFrame:
    """Pico de excedente de MMGD previsto nas próximas 24 h, por subestação de fronteira.

    Método em src/spatial/excedentes.py e docs/metodo_espacial.md: capacidade da BDGD × ANEEL,
    carga e MMGD do ONS; persistência sazonal, sem nenhum dado posterior ao agora. Calculado UMA
    vez por publicação e usado pela tela Excedentes e pela camada de áreas do mapa (mesmos números).
    """
    c = carregar("espacial")
    ce = c["excedentes"]
    cap = ex.capacidade_no_agora(pd.read_csv(SAIDA_MMGD_DIARIA), agora)
    fator = ex.fator_geracao(pd.read_csv(SAIDA_CARGA_AREA), pd.read_csv(SAIDA_CAPACIDADE_MMGD), c["uf"])
    prev = ex.prever(fator, cap, pd.read_csv(SAIDA_CARGA_AREA_INFLUENCIA), agora,
                     max(ce["horizontes"].values()), ce["defasagem_sazonal_passos"])
    return ex.pico_por_area(prev, ce["horizontes"])


def excedentes_tso_dso(pico: pd.DataFrame) -> list[ExcedenteTsoDso]:
    """Tela Excedentes: subestações da área piloto com maior excedente previsto (dado real).

    Posição = a subestação (a fronteira TSO–DSO). `pico` = pico_excedentes(agora).
    """
    areas = pd.read_csv(SAIDA_MMGD_AREA_INFLUENCIA, dtype={"cod_sub": str})
    sel = ex.selecionar(pico, areas, carregar("espacial")["excedentes"])
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


def areas_influencia(pico: pd.DataFrame) -> AreasInfluencia:
    """Camada de polígonos do Mapa Híbrido: áreas de influência com MMGD e excedente (dado real)."""
    c = carregar("espacial")
    geo = gpd.read_file(SAIDA_AREAS_INFLUENCIA_GEOJSON)
    feicoes = camada_mapa.feicoes(geo, pico, c["mapa"]["simplificacao_m"], c["geometria"]["crs_metrico"],
                                  c["mapa"]["casas_decimais"])
    return AreasInfluencia(mock=False, type="FeatureCollection", descricao=c["mapa"]["descricao"],
                           features=feicoes)


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
    clima = pd.read_csv(SAIDA_CLIMA_UF, parse_dates=["timestamp"]) if SAIDA_CLIMA_UF.exists() else None
    pesos_uf = pesos_mmgd_uf(pd.read_csv(SAIDA_CAPACIDADE_MMGD), agora)
    riscos, alertas = riscos_e_alertas(agora)
    pico = pico_excedentes(agora)
    recursos = {
        "riscos": [r.para_json() for r in riscos],
        "alertas": [a.para_json() for a in alertas],
        "carga": carga.para_json(),
        "previsao": [c.para_json() for c in curvas_previsao(prev, agora, fatores, clima, pesos_uf)],
        "validacao": metricas_validacao(prev, agora, download.status_fontes(cfg["status_fontes"]),
                                        mc.metadados_treino()).para_json(),
        "excedentes": [e.para_json() for e in excedentes_tso_dso(pico)],
        "areas_influencia": areas_influencia(pico).para_json(),
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
