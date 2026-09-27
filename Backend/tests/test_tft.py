"""TFT com perda assimétrica (Fase 5): a perda, o split e a AUSÊNCIA de vazamento temporal.

O teste de vazamento é o exigido pelo CLAUDE.md para toda etapa de modelagem: muda-se TUDO depois
de uma emissão e a previsão daquela emissão tem de sair idêntica.
"""
import copy

import numpy as np
import pandas as pd
import pytest

from src.features.carga import CODIGO_PATAMAR
from src.models import carga as mc
from src.models import perda_assimetrica as pa
from src.models import tft
from src.utils.paths import RAIZ
from tests.test_modelos_carga import _dados_sinteticos

torch = pa.torch


# --------------------------------------------------------------------------- perda
def _pinball_classica(prev, real, q):
    e = real[..., None] - prev
    return np.maximum(q * e, (q - 1) * e)


def test_com_pesos_unitarios_e_a_pinball():
    rng = np.random.default_rng(0)
    prev, real = rng.normal(size=(4, 6, 3)), rng.normal(size=(4, 6))
    codigo = rng.integers(0, len(CODIGO_PATAMAR), size=(4, 6))
    q = np.array([0.1, 0.5, 0.9])
    um = torch.ones(len(CODIGO_PATAMAR), dtype=torch.float64)
    L = pa.pinball_assimetrica(torch.tensor(prev), torch.tensor(real), torch.tensor(codigo),
                               torch.tensor(q), um, um)
    np.testing.assert_allclose(L.numpy(), _pinball_classica(prev, real, q))


def test_peso_na_subestimacao_desloca_o_quantil_para_cima():
    """Com pesos (a, b), o minimizador do quantil q é o quantil a·q / (a·q + b·(1−q)).
    P50 com (3, 1) -> P75: é o viés operativo pretendido (errar para cima na ponta)."""
    real = torch.tensor(np.random.default_rng(1).normal(size=20000))
    grade = torch.linspace(-2, 2, 801, dtype=torch.float64)
    codigo = torch.zeros(1, len(real), dtype=torch.long)
    perdas = [pa.pinball_assimetrica(torch.full((1, len(real), 1), float(c)), real[None, :], codigo,
                                     torch.tensor([0.5]), torch.tensor([3.0]), torch.tensor([1.0])).mean()
              for c in grade]
    melhor = float(grade[int(torch.stack(perdas).argmin())])
    assert melhor == pytest.approx(float(np.quantile(real.numpy(), 0.75)), abs=0.02)


def test_pesos_da_config_cobrem_todos_os_patamares():
    sub, sup = pa.tabela_pesos(tft.cfg()["perda"]["pesos"])
    assert len(sub) == len(sup) == len(CODIGO_PATAMAR)
    ponta = CODIGO_PATAMAR["ponta_noturna"]
    minima = CODIGO_PATAMAR["minima_diurna"]
    assert sub[ponta] > sup[ponta]      # na ponta, subestimar custa mais
    assert sup[minima] > sub[minima]    # na mínima diurna, superestimar custa mais


def test_pesos_incompletos_sao_recusados():
    pesos = dict(tft.cfg()["perda"]["pesos"])
    pesos.pop("ponta_noturna")
    with pytest.raises(ValueError, match="faltam"):
        pa.tabela_pesos(pesos)


# --------------------------------------------------------------------------- modelo pequeno
@pytest.fixture
def cfg_pequena(monkeypatch, tmp_path):
    cm = copy.deepcopy(mc.cfg())
    cm["split"] = {"inicio_treino": "2025-01-10 00:00", "fim_treino": "2025-02-28 23:30",
                   "inicio_teste": "2025-03-01 00:00"}
    cm["calibracao_dias"] = 14
    monkeypatch.setattr(mc, "cfg", lambda: cm)
    c = copy.deepcopy(tft.cfg())
    c["janela"]["encoder"] = 16
    c["rede"].update(hidden_size=4, attention_head_size=1, hidden_continuous_size=4)
    c["treino"].update(batch_size=32, max_epochs=1, lotes_por_epoca=3, lotes_validacao=2,
                       dias_parada_antecipada=7, batch_size_previsao=256)
    monkeypatch.setattr(tft, "cfg", lambda: c)
    monkeypatch.setattr(tft, "DIR", tmp_path)
    monkeypatch.setattr(tft, "ARQ_CKPT", tmp_path / "tft.ckpt")
    monkeypatch.setattr(tft, "ARQ_ESTADO", tmp_path / "estado.joblib")
    monkeypatch.setattr(tft, "ARQ_PREVISOES", tmp_path / "p.parquet")
    return c


@pytest.fixture
def treinado(cfg_pequena):
    dados = _dados_sinteticos()
    tft.treinar(dados)
    return dados


def test_previsoes_fora_da_amostra_e_com_semantica_de_horizonte(treinado):
    tft.prever(treinado)
    prev = pd.read_parquet(tft.ARQ_PREVISOES)
    assert set(prev["modelo"]) == {"tft"}
    assert set(prev["horizonte"]) == set(mc.cfg()["horizontes"])
    assert (prev["emissao"] >= pd.Timestamp("2025-03-01")).all()
    assert (prev["emissao"] <= treinado.ultimo_dado).all()
    passos = {k: v for k, v in mc.cfg()["horizontes"].items()}
    assert ((prev["alvo"] - prev["emissao"]) == prev["horizonte"].map(passos) * pd.Timedelta("30min")).all()
    assert (prev["p10"] <= prev["p50"]).all() and (prev["p50"] <= prev["p90"]).all()
    # o D+1 do agora chega a 48 passos além do último dado, sem real
    d1 = prev[(prev["serie"] == "SIN") & (prev["horizonte"] == "D+1")]
    assert d1["alvo"].max() == treinado.ultimo_dado + 48 * pd.Timedelta("30min")
    assert d1[d1["alvo"] > treinado.ultimo_dado]["real"].isna().all()


def test_previsao_nao_usa_nada_depois_da_emissao(treinado):
    """Perturba carga e MMGD de TODAS as séries depois da emissão E: a janela emitida em E
    (os 3 horizontes, as 5 séries) não pode mudar."""
    import joblib
    estado = joblib.load(tft.ARQ_ESTADO)
    modelo = tft.TemporalFusionTransformer.load_from_checkpoint(tft.ARQ_CKPT)
    emissao = pd.Timestamp("2025-03-10 13:00")

    def _janela(dados):
        frame = tft.montar_frame(dados, estado["escala"])
        p = tft._prever_janelas(modelo, estado["parametros_dataset"], frame, dados, estado["escala"],
                                emissao_min=emissao, emissao_max=emissao)
        return p.sort_values(["serie", "horizonte"]).reset_index(drop=True)

    original = _janela(treinado)
    mexido = copy.deepcopy(treinado)
    depois = mexido.y.index > emissao
    mexido.y.loc[depois] = mexido.y.loc[depois] * 3 + 500
    mexido.mmgd.loc[depois] = mexido.mmgd.loc[depois] * 10
    alterado = _janela(mexido)
    assert len(original) == 5 * len(mc.cfg()["horizontes"])
    np.testing.assert_allclose(original[["p10", "p50", "p90"]].to_numpy(),
                               alterado[["p10", "p50", "p90"]].to_numpy(), rtol=1e-6)


def test_prever_recusa_modelo_de_outro_split(treinado):
    mc.cfg()["split"]["fim_treino"] = "2025-02-27 23:30"
    with pytest.raises(RuntimeError, match="outro split"):
        tft.prever(treinado)


def test_torch_importa_depois_de_extensoes_cpp_num_processo_novo():
    """Regressão (run_heavywork.py de 2026-09-26): o LightGBM carregava o msvcp140 antigo do
    Anaconda antes do TFT e o torch falhava (WinError 1114). Com o runtime do sistema carregado
    no __init__ de `src`, a ordem do pipeline (LightGBM, scikit-learn, depois torch) funciona."""
    import subprocess
    import sys

    codigo = ("import src.models.carga, lightgbm, sklearn\n"
              "from src.utils.torch_windows import importar_torch\n"
              "print(importar_torch().ones(2).sum().item())")
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True,
                       cwd=str(RAIZ))
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip() == "2.0"
