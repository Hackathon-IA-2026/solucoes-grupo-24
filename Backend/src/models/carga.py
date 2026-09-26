"""Previsão de carga supervisionada: baselines + LightGBM quantílico (Fase 3, Fatia 2).

Etapa 3 do run_heavywork.py (`treinar`) e etapa 4 (`prever`). Parâmetros em
config/modelos_carga.yaml.

Modelos, por série (SE, S, NE, N, SIN) e horizonte (h = 1, 6, 48 passos de 30 min):
| modelo          | P50                                          | P10 / P90                          |
|-----------------|----------------------------------------------|------------------------------------|
| persistencia    | último valor conhecido na emissão            | P50 + quantis do resíduo no treino |
| sazonal_dia     | mesmo horário do dia mais recente disponível | idem                               |
| sazonal_semana  | mesmo horário da semana anterior             | idem                               |
| climatologia    | média do treino por mês × dia da semana × hora | idem (é a base do skill)         |
| lightgbm        | referência + desvio previsto (objetivo quantile, um modelo por quantil); banda  |
|                 | P10–P90 calibrada por conformal (CQR) numa janela no fim do treino              |

Calibração conformal (CQR, Romano et al. 2019): quantis ajustados na própria amostra ficam
estreitos demais (no primeiro backtest a banda P10–P90 cobriu ~50% dos reais, não 80%). O
LightGBM é ajustado sem os últimos `calibracao_dias` do treino; nessa janela mede-se o quanto
a banda precisa abrir (ou fechar) para cobrir a fração nominal. Depois o modelo é reajustado
com o treino INTEIRO (sem isso, os meses mais recentes, os que mais se parecem com o futuro,
ficariam de fora: no backtest o MAE do 3h piorou 30%) e a correção medida é aplicada nas
previsões. A janela de calibração fica DENTRO do treino: o teste continua intocado.

Garantias contra vazamento temporal (bug inexprimível, não só testado):
- features só com dados até a emissão (src/features/defasagens.py recusa o contrário);
- `prever` só emite previsões com emissão >= inicio_teste, e RECUSA rodar se o modelo salvo
  foi treinado com alvos em ou depois de inicio_teste. Tudo que sai daqui para o banco é
  fora da amostra, por construção.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import date

import joblib
import numpy as np
import pandas as pd

from src.features import carga as fc
from src.models.split import Split
from src.processing.tabelas import SAIDA_CALENDARIO, SAIDA_CARGA
from src.utils.config import carregar
from src.utils.paths import MODELOS, ensure
from src.utils.tempo import PASSO

log = logging.getLogger("modelos_carga")

DIR = MODELOS / "carga"
ARQ_MODELOS = DIR / "modelos.joblib"
ARQ_PREVISOES = DIR / "previsoes.parquet"


def arq_metadados():
    """Metadados do treino (versão e data), gravados JUNTO com modelos.joblib: a tela Validação
    mostra a versão do modelo que de fato foi treinado, não a da config atual. Derivado de
    ARQ_MODELOS na hora (e não uma constante própria): os dois nunca apontam para pastas
    diferentes, nem quando os testes redirecionam ARQ_MODELOS."""
    return ARQ_MODELOS.with_name("metadados.json")
BASELINES = ("persistencia", "sazonal_dia", "sazonal_semana")
MODELOS_TODOS = (*BASELINES, "climatologia", "lightgbm")
COLS_QUANTIS = ("p10", "p50", "p90")


def cfg() -> dict:
    return carregar("modelos_carga")


# --------------------------------------------------------------------------- dados e split
@dataclass
class Dados:
    y: pd.DataFrame      # alvo, larga: timestamp × série (com linhas futuras NaN)
    mmgd: pd.DataFrame   # MMGD estimada, mesma grade
    cal: pd.DataFrame    # features de calendário, mesma grade

    @property
    def ultimo_dado(self) -> pd.Timestamp:
        """Último instante com o alvo do SIN (os 4 subsistemas)."""
        return self.y["SIN"].last_valid_index()


def carregar_dados() -> Dados:
    c = cfg()
    carga = pd.read_csv(SAIDA_CARGA)
    futuros = max(c["horizontes"].values())  # alvos além do último dado (previsão "ao vivo")
    y = fc.series_largas(carga, c["alvo"], futuros)
    mmgd = fc.series_largas(carga, "mmgd_estimada", futuros)
    cal = fc.calendario(pd.read_csv(SAIDA_CALENDARIO)).reindex(y.index)
    return Dados(y=y, mmgd=mmgd, cal=cal)


def split() -> Split:
    """Split cronológico da carga (config/modelos_carga.yaml; regras em src/models/split.py)."""
    return Split.de(cfg()["split"])


def correcao_conformal(q: np.ndarray, real: np.ndarray, cobertura: float) -> float:
    """Quanto abrir P10 e P90 (MW, simétrico) para a banda cobrir `cobertura` na calibração.

    Escore do CQR: E = max(P10 − real, real − P90) (negativo = real dentro da banda, com folga).
    A correção é o quantil ceil((n+1)·cobertura)/n dos escores (garantia de cobertura
    em amostra finita sob permutabilidade).
    """
    escores = np.maximum(q[:, 0] - real, real - q[:, 2])
    n = len(escores)
    nivel = min(1.0, np.ceil((n + 1) * cobertura) / n)
    return float(np.quantile(escores, nivel))


def ordenar_quantis(q: np.ndarray) -> np.ndarray:
    """Rearranjo (Chernozhukov et al.): ordena P10 ≤ P50 ≤ P90 em cada linha.

    Modelos quantílicos independentes podem cruzar; o contrato recusa quantil fora de ordem.
    Ordenar é a correção padrão e nunca piora o pinball. Toda saída de quantis passa por aqui.
    """
    return np.sort(q, axis=1)


# --------------------------------------------------------------------------- treino
# Climatologia: média do TREINO por chave de calendário, da mais fina para a mais grossa. Se a
# chave fina não existe no treino (ex.: mês que o treino não cobre), usa a seguinte: a
# climatologia nunca fica sem valor por falta de combinação.
_CHAVES_CLIMA = (["mes", "dia_semana_efetivo", "hora_decimal"], ["dia_semana_efetivo", "hora_decimal"])


def _climatologia(y: pd.Series, cal: pd.DataFrame) -> list[pd.Series]:
    return [y.groupby([cal[c] for c in chave]).mean() for chave in _CHAVES_CLIMA]


def _previsao_base(modelo: str, y: pd.Series, h: int, cal: pd.DataFrame, clima: list[pd.Series] | None) -> pd.Series:
    """P50 de um modelo de referência (baselines e climatologia; esta não usa defasagem)."""
    if modelo in BASELINES:
        return fc.referencia(y, h, modelo)
    out = pd.Series(np.nan, index=y.index)
    for chave, medias in zip(_CHAVES_CLIMA, clima):
        valores = medias.reindex(pd.MultiIndex.from_arrays([cal[c] for c in chave])).to_numpy()
        out = out.fillna(pd.Series(valores, index=y.index))
    return out


def treinar(dados: Dados | None = None) -> str:
    """Etapa 3: treina e salva todos os modelos; devolve o resumo para o run_heavywork."""
    import lightgbm as lgb  # import local: só a parte pesada carrega o LightGBM

    c, sp = cfg(), split()
    dados = dados or carregar_dados()
    quantis = c["quantis"]
    salvo: dict = {"split": sp, "quantis": quantis, "lightgbm": {}, "residuos": {}, "clima": {},
                   "features": {}, "conformal": {}}
    cobertura = quantis[-1] - quantis[0]  # P10–P90 -> 80%
    inicio_calib = sp.fim_treino - pd.Timedelta(days=c["calibracao_dias"])
    for serie in c["series"]:
        y = dados.y[serie]
        tr_clima = sp.treino(y.index) & y.notna().to_numpy()
        clima = _climatologia(y[tr_clima], dados.cal[tr_clima])
        salvo["clima"][serie] = clima
        for nome_h, h in c["horizontes"].items():
            tr = sp.treino(y.index) & y.notna().to_numpy()
            # quantis do resíduo (real − P50) no treino: dão P10/P90 aos modelos pontuais
            for base in (*BASELINES, "climatologia"):
                p50 = _previsao_base(base, y, h, dados.cal, clima)
                res = (y - p50)[tr & p50.notna().to_numpy()]
                salvo["residuos"][(serie, nome_h, base)] = np.quantile(res, quantis)

            x = fc.matriz(y, dados.mmgd[serie], dados.cal, h, c["features"])
            ref = fc.referencia(y, h, c["referencia"][nome_h])
            ok = tr & ref.notna().to_numpy()
            ajuste = ok & np.asarray(y.index < inicio_calib)
            calib = ok & ~ajuste
            desvio = y - ref
            salvo["features"][(serie, nome_h)] = list(x.columns)
            def _ajustar(linhas: np.ndarray) -> dict:
                return {q: lgb.LGBMRegressor(objective="quantile", alpha=q, **c["lightgbm"])
                        .fit(x[linhas], desvio[linhas]) for q in quantis}

            modelos = _ajustar(ajuste)
            qc = ordenar_quantis(np.column_stack([ref[calib] + modelos[q].predict(x[calib]) for q in quantis]))
            salvo["conformal"][(serie, nome_h)] = correcao_conformal(qc, y[calib].to_numpy(), cobertura)
            salvo["lightgbm"][(serie, nome_h)] = _ajustar(ok)  # reajuste com o treino inteiro
            log.info("treinado %s %s: %d linhas", serie, nome_h, int(ok.sum()))
    ensure(DIR)
    joblib.dump(salvo, ARQ_MODELOS)
    arq_metadados().write_text(json.dumps({"versao": versao_config(),
                                         "dataTreino": date.today().isoformat()}), encoding="utf-8")
    n = len(salvo["lightgbm"])
    return (f"{n} LightGBM × {len(quantis)} quantis (banda calibrada por CQR) + {len(BASELINES)} "
            f"baselines e climatologia; treino até {sp.fim_treino:%Y-%m-%d}")


# --------------------------------------------------------------------------- previsão (replay)
def prever(dados: Dados | None = None) -> str:
    """Etapa 4: previsões de TODAS as emissões fora da amostra (modo replay).

    Uma linha por (série, horizonte, modelo, alvo). Emissões de inicio_teste até o último dado;
    alvos até último dado + h (as previsões "do agora" para frente). A publicação escolhe o
    "agora" nesta tabela, e o backtest é a mesma tabela onde o real já é conhecido.
    """
    c = cfg()
    salvo = joblib.load(ARQ_MODELOS)
    sp: Split = salvo["split"]
    if sp != split():
        raise RuntimeError("modelos salvos com outro split: rode o treino de novo (etapa 3)")
    # Invariante contra vazamento: nenhum alvo de treino em ou depois do início do teste.
    if sp.fim_treino >= sp.inicio_teste:
        raise RuntimeError("modelo treinado com alvos do período de teste")
    dados = dados or carregar_dados()
    ultimo = dados.ultimo_dado
    partes = []
    for serie in c["series"]:
        y = dados.y[serie]
        for nome_h, h in c["horizontes"].items():
            idx = y.index
            emissao = idx - h * PASSO
            sel = sp.teste(idx, h) & np.asarray(emissao <= ultimo)
            alvos = idx[sel]

            def _linhas(modelo: str, q: np.ndarray) -> pd.DataFrame:
                q = ordenar_quantis(q)
                return pd.DataFrame({"serie": serie, "horizonte": nome_h, "modelo": modelo,
                                     "alvo": alvos, "emissao": alvos - h * PASSO,
                                     "p10": q[:, 0], "p50": q[:, 1], "p90": q[:, 2],
                                     "real": y[sel].to_numpy()})

            for base in (*BASELINES, "climatologia"):
                p50 = _previsao_base(base, y, h, dados.cal, salvo["clima"][serie])[sel].to_numpy()
                r = salvo["residuos"][(serie, nome_h, base)]
                partes.append(_linhas(base, p50[:, None] + r[None, :]))

            x = fc.matriz(y, dados.mmgd[serie], dados.cal, h, c["features"])
            if list(x.columns) != salvo["features"][(serie, nome_h)]:
                raise RuntimeError("features diferentes das do treino: rode o treino de novo")
            ref = fc.referencia(y, h, c["referencia"][nome_h])[sel].to_numpy()
            modelos = salvo["lightgbm"][(serie, nome_h)]
            q = np.column_stack([ref + modelos[qq].predict(x[sel]) for qq in salvo["quantis"]])
            q = ordenar_quantis(q)
            corr = salvo["conformal"][(serie, nome_h)]
            q[:, 0] -= corr
            q[:, -1] += corr
            partes.append(_linhas("lightgbm", q))
    prev = pd.concat(partes, ignore_index=True)
    # Sem referência (buraco no dado da emissão) não há previsão: melhor ausente que inventada.
    prev = prev.dropna(subset=list(COLS_QUANTIS))
    ensure(DIR)
    prev.to_parquet(ARQ_PREVISOES, index=False)
    return (f"{len(prev):,} previsões fora da amostra (emissões de {sp.inicio_teste:%Y-%m-%d} "
            f"até {ultimo:%Y-%m-%d %H:%M})")


def versao_config() -> str:
    """Identidade do modelo: hash das seções da config que definem o treino (split, features,
    hiperparâmetros...). Mudou qualquer uma -> versão nova; mesma config -> mesma versão em
    qualquer máquina. Sem número de versão mantido à mão."""
    c = cfg()
    definicao = {k: c[k] for k in ("series", "horizontes", "quantis", "split", "features",
                                   "referencia", "calibracao_dias", "lightgbm")}
    return "cfg-" + hashlib.sha1(json.dumps(definicao, sort_keys=True).encode()).hexdigest()[:8]


def metadados_treino() -> dict:
    """{"versao": ..., "dataTreino": date} do modelo salvo (tela Validação).

    Modelos treinados antes de existir metadados.json: versão = config atual e data = gravação
    do modelos.joblib (aviso no log; o próximo treino grava os metadados de verdade).
    """
    arq = arq_metadados()
    if arq.exists():
        m = json.loads(arq.read_text(encoding="utf-8"))
        return {"versao": m["versao"], "dataTreino": date.fromisoformat(m["dataTreino"])}
    if not ARQ_MODELOS.exists():
        raise FileNotFoundError(f"{ARQ_MODELOS} não existe: rode python run_heavywork.py")
    log.warning("%s ausente: versão do modelo inferida da config atual", arq.name)
    return {"versao": versao_config(), "dataTreino": date.fromtimestamp(ARQ_MODELOS.stat().st_mtime)}


def ler_previsoes() -> pd.DataFrame:
    if not ARQ_PREVISOES.exists():
        raise FileNotFoundError(f"{ARQ_PREVISOES} não existe: rode python run_heavywork.py")
    return pd.read_parquet(ARQ_PREVISOES)
