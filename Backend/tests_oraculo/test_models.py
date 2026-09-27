# -*- coding: utf-8 -*-
"""Geometria solar, estimador de MMGD, decomposicao, baselines e quantis."""
from __future__ import annotations

import numpy as np
import pytest

from oraculo import config
from oraculo.core.timeutils import hour_of_day, hourly_grid
from oraculo.features import builder
from oraculo.models import baselines, decomposition, mmgd, quantile, solar


# ============================================================ solar
def test_cos_zenith_negativo_a_noite_positivo_ao_meio_dia():
    ts = np.array(["2026-03-21T03:00:00", "2026-03-21T15:00:00"],
                  dtype="datetime64[s]")   # 00h e 12h locais (UTC-3)
    cz = solar.cos_zenith(ts, -15.8, -47.9, tz_offset=0.0)
    assert cz[0] < 0, "meia-noite deveria ter zenite negativo"
    assert cz[1] > 0


def test_clearsky_zero_quando_sol_abaixo_do_horizonte():
    cz = np.array([-0.5, 0.0, 0.5])
    ghi = solar.clearsky_ghi(cz)
    assert ghi[0] == 0.0
    assert ghi[1] == 0.0
    assert ghi[2] > 0.0


def test_clearsky_nunca_excede_constante_solar():
    cz = np.linspace(0.01, 1.0, 200)
    assert solar.clearsky_ghi(cz).max() < solar.SOLAR_CONSTANT


def test_maximo_de_irradiancia_ocorre_perto_do_meio_dia_solar():
    day = hourly_grid(np.datetime64("2026-06-21T00:00:00", "s"),
                      np.datetime64("2026-06-21T23:00:00", "s"))
    lat, lon = -21.5, -45.5
    ghi = solar.clearsky_ghi(solar.cos_zenith(day, lat, lon))
    peak_hour = int(hour_of_day(day)[int(np.argmax(ghi))])
    noon = solar.solar_noon_hour(day[0], lon)
    assert abs(peak_hour - noon) <= 1.5, (
        "pico em %dh, meio-dia solar em %.2fh" % (peak_hour, noon))


def test_verao_do_hemisferio_sul_tem_mais_energia_que_inverno():
    lat, lon = -21.5, -45.5
    total = {}
    for label, d0 in (("verao", "2026-01-15"), ("inverno", "2026-07-15")):
        day = hourly_grid(np.datetime64(d0 + "T00:00:00", "s"),
                          np.datetime64(d0 + "T23:00:00", "s"))
        total[label] = float(solar.clearsky_ghi(solar.cos_zenith(day, lat, lon)).sum())
    assert total["verao"] > total["inverno"]


# ============================================================ MMGD
def test_mmgd_e_zero_a_noite(sin_state):
    est = sin_state["mmgd"]
    night = ~est.is_day
    assert night.any()
    assert np.all(est.mmgd_mw[night] == 0.0), "MMGD nao pode gerar sem sol"


def test_mmgd_respeita_limite_de_capacidade(sin_state):
    est = sin_state["mmgd"]
    teto = est.capacity_mwp * est.performance_ratio
    assert est.mmgd_mw.max() <= teto + 1e-6
    assert est.mmgd_mw.min() >= 0.0


def test_fator_de_nebulosidade_dentro_dos_limites(sin_state):
    est = sin_state["mmgd"]
    k = est.cloud_factor[est.is_day]
    assert k.min() >= config.MMGD_CLOUD_FACTOR_MIN - 1e-9
    assert k.max() <= config.MMGD_CLOUD_FACTOR_MAX + 1e-9


def test_envelope_e_maior_ou_igual_a_carga_na_maior_parte_do_tempo(sin_state):
    est = sin_state["mmgd"]
    if est.envelope is None:
        pytest.skip("metodo sem envelope")
    load = sin_state["load"]
    ok = np.isfinite(est.envelope) & np.isfinite(load)
    frac = float(np.mean(est.envelope[ok] >= load[ok]))
    assert frac > 0.7, "o envelope deveria dominar a carga: %.2f" % frac


def test_metodo_proxy_e_deterministico():
    ts = hourly_grid(np.datetime64("2026-05-01T00:00:00", "s"),
                     np.datetime64("2026-05-10T23:00:00", "s"))
    a = mmgd.estimate(ts, None, "SE", method="proxy")
    b = mmgd.estimate(ts, None, "SE", method="proxy")
    assert np.allclose(a.mmgd_mw, b.mmgd_mw)


def test_summary_declara_o_vies_do_metodo(sin_state):
    s = sin_state["mmgd"].summary()
    assert s["night_is_zero"] is True
    assert s["bias_note"]
    assert 0.0 <= s["capacity_factor"] <= 1.0


# ============================================================ decomposicao
def test_identidade_da_carga_fecha_exatamente(sin_state):
    dec = sin_state["dec"]
    assert dec.identity_residual_max == pytest.approx(0.0, abs=1e-9)


def test_derivados_da_decomposicao_sao_coerentes(sin_state):
    d = sin_state["dec"].to_dict()
    assert d["min_supervised_mw"] <= d["max_supervised_mw"]
    assert d["daily_amplitude_mw"] >= 0
    assert 0.0 <= d["mmgd_share_peak"] <= 1.0


def test_perfis_por_dia_tipo_cobrem_24_horas(sin_state):
    profs = decomposition.typeday_profiles(
        sin_state["ts"], sin_state["dec"].carga_supervisionada,
        sin_state["dec"].mmgd_estimada)
    assert len(profs) == 3
    for p in profs:
        assert p["hours"] == list(range(24))
        assert len(p["carga_p50"]) == 24
        assert sum(p["samples"]) > 0


def test_clm_inputs_traz_os_campos_propostos(sin_state):
    c = decomposition.clm_inputs(sin_state["dec"])
    for k in ("load_factor", "solar_penetration_peak", "min_supervised_mw",
              "ramp_max_mw_h", "amplitude_mw", "samples"):
        assert k in c


# ============================================================ baselines
def test_persistencia_desloca_a_serie():
    y = np.arange(10.0)
    p = baselines.persistence(y, 3)
    assert np.isnan(p[:3]).all()
    assert p[3:].tolist() == y[:7].tolist()


def test_sazonal_ingenuo_usa_ciclo_anterior():
    y = np.arange(60.0)
    s = baselines.seasonal_naive(y, 3, period=24)
    assert np.isnan(s[:24]).all()
    assert s[30] == pytest.approx(y[6])


def test_skill_positivo_quando_modelo_ganha():
    assert baselines.skill(5.0, 10.0) == pytest.approx(0.5)
    assert baselines.skill(20.0, 10.0) == pytest.approx(-1.0)
    assert np.isnan(baselines.skill(1.0, 0.0))


# ============================================================ features
def test_matriz_de_projeto_tem_grupos_nomeados(sin_state):
    fm = sin_state["fm"]
    groups = {n.split(".")[0] for n in fm.names}
    for g in ("calendario", "fourier", "solar", "defasagem"):
        assert g in groups
    assert fm.n == len(fm.index)
    assert fm.valid.sum() > 0


def test_sem_tempo_observado_o_grupo_clima_fica_de_fora(sin_state):
    # Regra "nunca inventar dados": sem tempo real (fixture sem `weather`) o
    # builder nao gera temperatura sintetica; o grupo clima simplesmente some.
    assert not any(n.startswith("clima.") for n in sin_state["fm"].names)


def test_tempo_observado_entra_no_grupo_clima(sin_state):
    from oraculo.features import builder
    ts = sin_state["ts"]
    temp = np.full(len(ts), 25.0)
    temp[5] = np.nan                       # buraco do servico -> media, linha valida
    fm = builder.build(ts, area="SE", weather={"temperature": temp,
                                               "dewpoint": temp - 5.0})
    assert "clima.temperatura" in fm.names
    col = fm.X[:, fm.names.index("clima.temperatura")]
    assert np.isfinite(col).all() and col[5] == pytest.approx(25.0 / 40.0)


def test_tempo_por_area_alinha_na_grade_e_pondera_por_populacao(monkeypatch):
    from oraculo.tempo import clima
    pts = config.WEATHER_POINTS["S"]
    idx = np.arange(np.datetime64("2020-01-01T00:00:00"), np.datetime64("2020-01-01T04:00:00"),
                    np.timedelta64(1, "h")).astype("datetime64[s]")

    def fake_era5(points, start, end, hourly=clima.HOURLY, ttl=0):
        # Resposta no formato de _unpack: 3 horas (a ultima hora da grade falta).
        horas = ["2020-01-01T00:00", "2020-01-01T01:00", "2020-01-01T02:00"]
        temps = [[10.0 + i] * 3 for i in range(len(points))]
        return {"time": horas, "_": {"temperature_2m": temps, "dew_point_2m": temps}}

    monkeypatch.setattr(clima, "era5", fake_era5)
    w, prov = clima.weather_for_area(idx, "S")
    pesos = np.array([p["peso"] for p in pts])
    esperado = float(np.sum((10.0 + np.arange(len(pts))) * pesos) / pesos.sum())
    assert w["temperature"][0] == pytest.approx(esperado)
    assert np.isnan(w["temperature"][3])   # hora sem tempo nao e inventada
    assert prov["mode"] == "live" and prov["rows"] == 3


def test_tempo_indisponivel_devolve_none_sem_inventar(monkeypatch):
    from oraculo.tempo import clima

    def falha(*a, **k):
        raise ConnectionError("offline")

    monkeypatch.setattr(clima, "era5", falha)
    idx = np.array(["2020-01-01T00:00:00"], dtype="datetime64[s]")
    w, prov = clima.weather_for_area(idx, "SE")
    assert w is None and prov["mode"] == "demo"


def test_patamares_cobrem_as_faixas_configuradas(sin_state):
    fm = sin_state["fm"]
    hod = hour_of_day(fm.index)
    for i in range(0, len(hod), 97):
        assert fm.patamar[i] == config.patamar_of_hour(int(hod[i]))


def test_append_e_mask_preservam_alinhamento(sin_state):
    fm = sin_state["fm"]
    extra = np.ones(fm.n)
    fm2 = builder.append_column(fm, "regime.teste", extra)
    assert fm2.p == fm.p + 1
    assert len(fm2.index) == len(fm.index)
    mask = np.zeros(fm.n, dtype=bool)
    mask[: fm.n // 2] = True
    fm3 = builder.mask_valid(fm2, mask)
    assert fm3.valid.sum() <= mask.sum()
    assert len(fm3.index) == len(fm.index), "mask_valid nao deve reindexar"


def test_indice_de_desconforto_cresce_com_temperatura():
    a = builder.discomfort_index(np.array([25.0]), np.array([18.0]))
    b = builder.discomfort_index(np.array([35.0]), np.array([18.0]))
    assert b[0] > a[0]


# ============================================================ quantil
def test_pinball_penaliza_lados_conforme_o_peso():
    r = np.array([10.0, -10.0])                 # subestimou, superestimou
    sym = quantile.pinball(r, 0.5)
    asym = quantile.pinball(r, 0.5, w_under=3.0, w_over=1.0)
    assert asym[0] > sym[0], "peso de subestimacao deveria elevar a perda"
    assert asym[1] == pytest.approx(sym[1])


def test_pesos_por_patamar_refletem_a_configuracao():
    pat = np.array(["ponta_noturna", "minima_diurna", "base"], dtype=object)
    wu, wo = quantile.patamar_weights(pat)
    assert wu[0] == config.ASYMMETRIC_WEIGHTS["ponta_noturna"][0]
    assert wo[1] == config.ASYMMETRIC_WEIGHTS["minima_diurna"][1]
    assert (wu[2], wo[2]) == (1.0, 1.0)


def test_pesos_simetricos_quando_desligado():
    pat = np.array(["ponta_noturna"] * 4, dtype=object)
    wu, wo = quantile.patamar_weights(pat, asymmetric=False)
    assert np.all(wu == 1.0) and np.all(wo == 1.0)


def test_quantis_nao_se_cruzam(sin_state):
    fm, y = sin_state["fm"], sin_state["dec"].carga_supervisionada
    ok = fm.valid & np.isfinite(y)
    m = quantile.QuantileModel().fit(fm.X[ok], y[ok], fm.patamar[ok], names=fm.names)
    pred = m.predict(fm.X[ok])
    assert np.all(pred[0.10] <= pred[0.50] + 1e-9)
    assert np.all(pred[0.50] <= pred[0.90] + 1e-9)


def test_modelo_quantilico_aprende_relacao_linear():
    rng = np.random.default_rng(1)
    n = 900
    x = rng.normal(0, 1, n)
    y = 100.0 + 20.0 * x + rng.normal(0, 2.0, n)
    X = np.column_stack([np.ones(n), x])
    pat = np.array(["base"] * n, dtype=object)
    m = quantile.QuantileModel(quantiles=(0.5,), asymmetric=False).fit(X, y, pat)
    pred = m.predict(X)[0.5]
    assert float(np.mean(np.abs(pred - y))) < 4.0


def test_perda_assimetrica_desloca_o_vies_para_o_lado_seguro():
    """Na ponta noturna, subestimar e mais grave: o ajuste deve subir."""
    rng = np.random.default_rng(7)
    n = 1200
    x = rng.normal(0, 1, n)
    y = 50.0 + 5.0 * x + rng.normal(0, 6.0, n)
    X = np.column_stack([np.ones(n), x])
    pat = np.array(["ponta_noturna"] * n, dtype=object)
    base = np.array(["base"] * n, dtype=object)
    sym = quantile.QuantileModel(quantiles=(0.5,), asymmetric=False).fit(X, y, base)
    asym = quantile.QuantileModel(quantiles=(0.5,), asymmetric=True).fit(X, y, pat)
    bias_sym = float(np.mean(sym.predict(X)[0.5] - y))
    bias_asym = float(np.mean(asym.predict(X)[0.5] - y))
    assert bias_asym > bias_sym, (
        "assimetrica deveria superestimar mais que a simetrica: %.3f vs %.3f"
        % (bias_asym, bias_sym))


def test_describe_expoe_a_funcao_de_perda():
    m = quantile.QuantileModel()
    d = m.describe()
    assert d["loss"] == "pinball_assimetrico_por_patamar"
    assert "ponta_noturna" in d["weights_by_patamar"]


def test_fit_rejeita_amostra_insuficiente():
    X = np.ones((4, 6))
    y = np.arange(4.0)
    with pytest.raises(ValueError):
        quantile.QuantileModel().fit(X, y, np.array(["base"] * 4, dtype=object))


def test_pesos_por_grupo_sao_finitos_e_somam_um(sin_state):
    """Colunas de defasagem tem NaN nas primeiras horas; nanstd evita que o
    peso de TODOS os grupos vire NaN."""
    fm, y = sin_state["fm"], sin_state["dec"].carga_supervisionada
    ok = fm.valid & np.isfinite(y)
    m = quantile.QuantileModel().fit(fm.X[ok], y[ok], fm.patamar[ok], names=fm.names)
    w = m.drivers(fm)
    assert w, "drivers nao pode vir vazio"
    for g in w:
        assert g["weight"] is not None and np.isfinite(g["weight"]), g
        assert g["weight"] >= 0.0
    assert sum(g["weight"] for g in w) == pytest.approx(1.0, abs=1e-3)
