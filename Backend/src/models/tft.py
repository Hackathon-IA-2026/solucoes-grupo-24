"""TFT (Temporal Fusion Transformer) com perda assimétrica por patamar (Fase 5, Fatia 3).

Etapas `treino_tft` e `previsao_tft` do run_heavywork.py. Parâmetros próprios em
config/modelos_tft.yaml; séries, horizontes, quantis, split e janela de calibração vêm de
config/modelos_carga.yaml (os MESMOS do LightGBM e dos baselines: comparação justa e sem cópia).

Como o modelo enxerga o problema
- Um modelo só para as 5 séries (SE, S, NE, N, SIN; a série entra como categoria estática).
  Cada série é dividida pela SUA média no treino (escala perto de 1 para todas), e o resultado
  multiplicado de volta na previsão. A média usa só alvos de treino.
- Multi-horizonte: cada janela tem `encoder` passos de histórico e prevê os 48 passos
  seguintes de uma vez. Os horizontes do contrato (h = 1, 6, 48) são os passos 1, 6 e 48 da
  janela emitida em (alvo − h): cada linha de saída tem a mesma semântica das do LightGBM.
- Entradas conhecidas no futuro (decoder): calendário do alvo (hora, dia da semana com
  feriado = domingo, mês, dia do ano, feriado, Dia dos Pais) e as defasagens de 48 e 336 passos
  (mesmo horário ontem e há uma semana). Estas vêm de src/features/defasagens.py com
  horizonte = 48, que RECUSA defasagem menor que o horizonte: y(alvo − k) com k >= 48 já é
  passado em qualquer emissão da janela.
- Entradas só do passado (encoder): a própria carga supervisionada e a MMGD estimada. A
  pytorch-forecasting não passa entradas "desconhecidas" ao decoder: as linhas futuras recebem
  0 nessas colunas só para o dataset aceitar (não entram na rede; o teste de vazamento prova).
- Perda: pinball assimétrica por patamar do alvo (src/models/perda_assimetrica.py).

Validação e calibração (decisão)
- A janela de calibração no fim do treino (`calibracao_dias`) é partida em duas: a primeira
  parte escolhe a época (parada antecipada), a segunda mede a correção conformal (CQR) da banda
  P10–P90, com a MESMA função do LightGBM (carga.correcao_conformal).
- Diferente do LightGBM, o TFT NÃO é reajustado com o treino inteiro depois da calibração
  (custaria outro treino inteiro em CPU): os ~6 últimos meses do treino ficam só para escolher
  a época e calibrar. O teste continua intocado.

Garantias contra vazamento temporal
- Treino só com janelas cujo alvo está em [inicio_treino, inicio_calib); a parada antecipada e
  a calibração só com alvos até fim_treino (< inicio_teste).
- `prever` só emite janelas com emissão >= inicio_teste e recusa rodar se o modelo salvo foi
  treinado com outro split. tests/test_tft.py perturba todo o futuro depois de uma emissão e
  confere que a previsão daquela emissão não muda.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import date

import joblib
import numpy as np
import pandas as pd

from src.features import defasagens
from src.models import carga as mc
from src.models.perda_assimetrica import PinballAssimetrica, tabela_pesos
from src.utils.config import carregar
from src.utils.paths import MODELOS, ensure
from src.utils.tempo import PASSO
from src.utils.torch_windows import importar_torch

torch = importar_torch()

import lightning.pytorch as pl  # noqa: E402  (depois do torch: ver src/utils/torch_windows.py)
from lightning.pytorch.callbacks import EarlyStopping, ModelCheckpoint  # noqa: E402
from pytorch_forecasting import TemporalFusionTransformer, TimeSeriesDataSet  # noqa: E402
from pytorch_forecasting.data import NaNLabelEncoder, TorchNormalizer  # noqa: E402

log = logging.getLogger("modelos_tft")

DIR = MODELOS / "tft"
ARQ_CKPT = DIR / "tft.ckpt"
ARQ_ESTADO = DIR / "estado.joblib"   # split, escalas, parâmetros do dataset, correção conformal
ARQ_PREVISOES = mc.ARQ_PREVISOES_TFT  # caminho definido junto das previsões dos outros modelos
MODELO = "tft"

# Colunas do dataset (os nomes de coluna são os mesmos no treino e na previsão).
_CAL_REAIS = ["hora_decimal", "dia_do_ano", "eh_feriado", "dia_dos_pais"]
_CAL_CATEG = ["dia_semana_efetivo", "mes"]


def cfg() -> dict:
    return carregar("modelos_tft")


def _passos_previsao() -> int:
    """A janela prevê até o maior horizonte do contrato (48 passos = D+1)."""
    return max(mc.cfg()["horizontes"].values())


def _col_defasagem(k: int) -> str:
    return f"carga_alvo_menos_{k}"


# --------------------------------------------------------------------------- dados
def escalas(dados: mc.Dados) -> dict[str, float]:
    """Média de cada série só nos alvos de treino (nunca olha o teste)."""
    sp = mc.split()
    tr = sp.treino(dados.y.index)
    return {s: float(dados.y.loc[tr, s].mean()) for s in mc.cfg()["series"]}


def montar_frame(dados: mc.Dados, escala: dict[str, float]) -> pd.DataFrame:
    """Tabela longa (uma linha por série × semi-hora) no formato do TimeSeriesDataSet.

    - time_idx = posição na grade regular de 30 min (a mesma para todas as séries);
    - linhas com buraco de dado são removidas (allow_missing_timesteps cuida da janela);
    - linhas depois do último dado da série ("futuro") ficam, com carga e MMGD = 0: são o
      decoder das previsões do agora e essas colunas não entram no decoder.
    """
    c = cfg()
    h_max = _passos_previsao()
    grade = dados.y.index
    partes = []
    for serie in mc.cfg()["series"]:
        y = dados.y[serie]
        e = escala[serie]
        ultimo = y.last_valid_index()
        df = pd.DataFrame({"serie": serie, "time_idx": np.arange(len(grade)), "alvo": grade,
                           "y": y.to_numpy() / e, "mmgd": dados.mmgd[serie].to_numpy() / e},
                          index=grade)
        for k in c["janela"]["defasagens_conhecidas"]:
            # horizonte = h_max: defasagens.defasagem recusa k < 48 (seria futuro na emissão)
            df[_col_defasagem(k)] = defasagens.defasagem(y, k, h_max).to_numpy() / e
        cal = dados.cal.reindex(grade)
        for col in _CAL_REAIS:
            df[col] = cal[col].astype(float).to_numpy()
        for col in _CAL_CATEG:
            df[col] = cal[col].astype("Int64").astype(str).to_numpy()
        # Coluna de "peso" do dataset = código do patamar do alvo (lido pela perda assimétrica).
        df["patamar_codigo"] = cal["patamar"].astype(float).to_numpy()
        futuro = grade > ultimo
        df.loc[futuro, ["y", "mmgd"]] = 0.0
        df = df[futuro | df["y"].notna()]
        df = df.dropna(subset=["mmgd", "patamar_codigo", *_CAL_REAIS,
                               *(_col_defasagem(k) for k in c["janela"]["defasagens_conhecidas"])])
        partes.append(df)
    frame = pd.concat(partes, ignore_index=True)
    frame["serie"] = frame["serie"].astype(str)
    return frame


def _idx(dados: mc.Dados, ts: pd.Timestamp) -> int:
    """time_idx do primeiro instante da grade em ou depois de `ts`."""
    return int(dados.y.index.searchsorted(ts))


def _dataset_treino(frame: pd.DataFrame, min_prediction_idx: int) -> TimeSeriesDataSet:
    c = cfg()
    h_max = _passos_previsao()
    return TimeSeriesDataSet(
        frame, time_idx="time_idx", target="y", group_ids=["serie"], weight="patamar_codigo",
        max_encoder_length=c["janela"]["encoder"], min_encoder_length=c["janela"]["encoder"],
        max_prediction_length=h_max, min_prediction_length=h_max,
        min_prediction_idx=min_prediction_idx,
        static_categoricals=["serie"],
        time_varying_known_categoricals=_CAL_CATEG,
        time_varying_known_reals=[*_CAL_REAIS,
                                  *(_col_defasagem(k) for k in c["janela"]["defasagens_conhecidas"])],
        time_varying_unknown_reals=["y", "mmgd"],
        # As séries já chegam divididas pela média do treino: normalizar de novo não ajuda e
        # esconderia a escala (identity = a rede vê o valor como está).
        target_normalizer=TorchNormalizer(method="identity", center=False),
        categorical_encoders={col: NaNLabelEncoder(add_nan=True) for col in ["serie", *_CAL_CATEG]},
        add_relative_time_idx=True,
        allow_missing_timesteps=True,
    )


# --------------------------------------------------------------------------- treino
def _perda() -> PinballAssimetrica:
    sub, sup = tabela_pesos(cfg()["perda"]["pesos"])
    return PinballAssimetrica(quantiles=list(mc.cfg()["quantis"]), pesos_sub=sub, pesos_sup=sup)


def _trainer(**extra) -> pl.Trainer:
    return pl.Trainer(accelerator="cpu", logger=False, enable_progress_bar=False,
                      enable_model_summary=False, **extra)


def treinar(dados: mc.Dados | None = None) -> str:
    """Etapa treino_tft: treina, calibra a banda e salva; devolve o resumo para o run_heavywork."""
    c, cm, sp = cfg(), mc.cfg(), mc.split()
    t = c["treino"]
    pl.seed_everything(t["semente"], workers=True)
    torch.set_num_threads(os.cpu_count() or 1)
    dados = dados or mc.carregar_dados()
    escala = escalas(dados)
    frame = montar_frame(dados, escala)

    inicio_calib = sp.fim_treino - pd.Timedelta(days=cm["calibracao_dias"])
    inicio_conformal = inicio_calib + pd.Timedelta(days=t["dias_parada_antecipada"])
    if not sp.inicio_treino < inicio_calib < inicio_conformal < sp.fim_treino:
        raise ValueError("janelas de calibração do TFT fora do treino: revise calibracao_dias e dias_parada_antecipada")
    # Treino: janelas com todos os alvos em [inicio_treino, inicio_calib).
    ds_treino = _dataset_treino(frame[frame["alvo"] < inicio_calib], _idx(dados, sp.inicio_treino))
    # Parada antecipada: alvos em [inicio_calib, inicio_conformal).
    ds_parada = TimeSeriesDataSet.from_dataset(
        ds_treino, frame[frame["alvo"] < inicio_conformal], stop_randomization=True,
        min_prediction_idx=_idx(dados, inicio_calib))

    modelo = TemporalFusionTransformer.from_dataset(
        ds_treino, loss=_perda(), logging_metrics=torch.nn.ModuleList([]),
        hidden_size=c["rede"]["hidden_size"], attention_head_size=c["rede"]["attention_head_size"],
        hidden_continuous_size=c["rede"]["hidden_continuous_size"], dropout=c["rede"]["dropout"],
        learning_rate=c["rede"]["learning_rate"], reduce_on_plateau_patience=t["paciencia"])
    ensure(DIR)
    ckpt = ModelCheckpoint(dirpath=DIR / "_checkpoints", monitor="val_loss", save_top_k=1)
    trainer = _trainer(max_epochs=t["max_epochs"], gradient_clip_val=c["rede"]["gradient_clip_val"],
                       limit_train_batches=t["lotes_por_epoca"], limit_val_batches=t["lotes_validacao"],
                       callbacks=[EarlyStopping(monitor="val_loss", patience=t["paciencia"]), ckpt])
    # shuffle das janelas de validação: com limit_val_batches, sem sortear só se veria o começo
    # da janela de parada antecipada (a mesma semente -> as mesmas janelas a cada época).
    trainer.fit(modelo,
                train_dataloaders=ds_treino.to_dataloader(train=True, batch_size=t["batch_size"], num_workers=0),
                val_dataloaders=ds_parada.to_dataloader(train=False, batch_size=t["batch_size_previsao"],
                                                        num_workers=0, shuffle=True))
    shutil.copyfile(ckpt.best_model_path, ARQ_CKPT)
    shutil.rmtree(DIR / "_checkpoints", ignore_errors=True)
    melhor = TemporalFusionTransformer.load_from_checkpoint(ARQ_CKPT)

    # Correção conformal por série × horizonte, com alvos em [inicio_conformal, fim_treino].
    calib = _prever_janelas(melhor, ds_treino.get_parameters(), frame[frame["alvo"] <= sp.fim_treino], dados, escala,
                            emissao_min=inicio_conformal - _passos_previsao() * PASSO)
    calib = calib[(calib["alvo"] >= inicio_conformal) & (calib["alvo"] <= sp.fim_treino)].dropna(subset=["real"])
    cobertura = cm["quantis"][-1] - cm["quantis"][0]
    conformal = {(s, h): mc.correcao_conformal(g[["p10", "p50", "p90"]].to_numpy(), g["real"].to_numpy(), cobertura)
                 for (s, h), g in calib.groupby(["serie", "horizonte"])}
    joblib.dump({"split": sp, "escala": escala, "conformal": conformal,
                 "parametros_dataset": ds_treino.get_parameters(),
                 "epocas": trainer.current_epoch, "val_loss": float(ckpt.best_model_score)}, ARQ_ESTADO)
    mc.arq_metadados(ARQ_CKPT).write_text(json.dumps({"versao": versao_config(),
                                                     "dataTreino": date.today().isoformat()}), encoding="utf-8")
    return (f"TFT treinado ({trainer.current_epoch} épocas, val_loss {float(ckpt.best_model_score):.4f}); "
            f"banda calibrada por CQR em {len(conformal)} série × horizonte; treino até {inicio_calib:%Y-%m-%d}")


# --------------------------------------------------------------------------- previsão
def _prever_janelas(modelo, parametros: dict, frame: pd.DataFrame, dados: mc.Dados,
                    escala: dict[str, float], emissao_min: pd.Timestamp,
                    emissao_max: pd.Timestamp | None = None) -> pd.DataFrame:
    """Previsões (sem correção conformal) de todas as janelas com emissão >= emissao_min.

    Saída no formato das previsões do LightGBM: uma linha por (série, horizonte, alvo).
    """
    c = cfg()
    # Mesmos codificadores e escalas do treino (parâmetros ajustados só no treino).
    ds = TimeSeriesDataSet.from_parameters(parametros, frame, stop_randomization=True,
                                           min_prediction_idx=_idx(dados, emissao_min) + 1)
    pred = modelo.predict(ds.to_dataloader(train=False, batch_size=c["treino"]["batch_size_previsao"],
                                           num_workers=0),
                          mode="quantiles", return_index=True,
                          trainer_kwargs={"accelerator": "cpu", "logger": False, "enable_progress_bar": False})
    saida = pred.output.detach().cpu().numpy()        # (janelas, 48, quantis)
    idx = pred.index.reset_index(drop=True)            # time_idx do 1º passo previsto + série
    grade = dados.y.index
    emissao = grade[idx["time_idx"].to_numpy() - 1]
    partes = []
    for nome_h, h in mc.cfg()["horizontes"].items():
        q = mc.ordenar_quantis(saida[:, h - 1, :]) * idx["serie"].map(escala).to_numpy()[:, None]
        alvo = emissao + h * PASSO
        df = pd.DataFrame({"serie": idx["serie"].to_numpy(), "horizonte": nome_h, "modelo": MODELO,
                           "alvo": alvo, "emissao": emissao, "p10": q[:, 0], "p50": q[:, 1], "p90": q[:, 2]})
        partes.append(df)
    prev = pd.concat(partes, ignore_index=True)
    if emissao_max is not None:
        prev = prev[prev["emissao"] <= emissao_max]
    # real: do alvo, na série original (NaN para alvos ainda sem dado: previsões "do agora")
    reais = dados.y.stack().rename("real")
    reais.index.names = ["alvo", "serie"]
    return prev.merge(reais.reset_index(), on=["alvo", "serie"], how="left")


def prever(dados: mc.Dados | None = None) -> str:
    """Etapa previsao_tft: todas as emissões fora da amostra (modo replay), como o LightGBM."""
    estado = joblib.load(ARQ_ESTADO)
    sp = mc.split()
    if estado["split"] != sp:
        raise RuntimeError("TFT salvo com outro split: rode o treino de novo (etapa treino_tft)")
    if sp.fim_treino >= sp.inicio_teste:  # invariante contra vazamento
        raise RuntimeError("modelo treinado com alvos do período de teste")
    torch.set_num_threads(os.cpu_count() or 1)
    dados = dados or mc.carregar_dados()
    frame = montar_frame(dados, estado["escala"])
    modelo = TemporalFusionTransformer.load_from_checkpoint(ARQ_CKPT)
    prev = _prever_janelas(modelo, estado["parametros_dataset"], frame, dados, estado["escala"],
                           emissao_min=sp.inicio_teste, emissao_max=dados.ultimo_dado)
    for (serie, h), corr in estado["conformal"].items():
        m = (prev["serie"] == serie) & (prev["horizonte"] == h)
        prev.loc[m, "p10"] -= corr
        prev.loc[m, "p90"] += corr
    prev = prev.dropna(subset=["p10", "p50", "p90"])
    ensure(DIR)
    prev.to_parquet(ARQ_PREVISOES, index=False)
    return (f"{len(prev):,} previsões TFT fora da amostra (emissões de {sp.inicio_teste:%Y-%m-%d} "
            f"até {dados.ultimo_dado:%Y-%m-%d %H:%M})")


def versao_config() -> str:
    """Hash da config do TFT + das seções da carga que definem o treino (mesma ideia do LightGBM)."""
    import hashlib

    definicao = {"tft": cfg(), "carga": {k: mc.cfg()[k] for k in ("series", "horizontes", "quantis",
                                                                  "split", "calibracao_dias")}}
    return "tft-" + hashlib.sha1(json.dumps(definicao, sort_keys=True).encode()).hexdigest()[:8]
