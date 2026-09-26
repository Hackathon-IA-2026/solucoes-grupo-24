# -*- coding: utf-8 -*-
"""Gerador deterministico para o modo demonstrativo (RF-03).

Falha de rede nao derruba a aplicacao: todos os paineis carregam com dados
sinteticos claramente rotulados. As formas seguem o padrao documentado no
PAR/PEL 2025 -- vale diurno profundo, rampa vespertina severa, restricao
concentrada na janela solar -- mas os valores NAO sao verificados.
"""
from __future__ import annotations

import numpy as np

from ..config import RANDOM_SEED, SUBSYSTEMS, capacity_of
from ..core.calendar_br import typeday_array
from ..core.frame import Frame, Provenance
from ..core.timeutils import hour_of_day, hourly_grid
from ..models import solar

# Escala de carga por subsistema, em MWmed, ordem de grandeza realista.
BASE_LOAD_MW = {"SIN": 80_000.0, "SE": 44_000.0, "S": 14_000.0,
                "NE": 13_500.0, "N": 7_500.0}


def demo_provenance(dataset: str, note: str = "") -> Provenance:
    return Provenance(
        dataset=dataset,
        resource="gerador determinístico",
        url="",
        fetched_at=Provenance.now_iso(),
        rows=0,
        bytes_read=0,
        mode="demo",
        lag_note=note or "Dados demonstrativos: não são valores verificados.",
    )


def hourly_index(days: int = 120, end: str | None = None) -> np.ndarray:
    """Grade horaria terminando em `end` (ou numa data fixa, para determinismo)."""
    last = np.datetime64(end or "2026-09-13T23:00:00", "s")
    start = last - np.timedelta64(days * 24 - 1, "h")
    return hourly_grid(start, last)


def supervised_load(index: np.ndarray, area: str) -> np.ndarray:
    """Carga supervisionada sintetica com barriga diurna e rampa vespertina."""
    index = np.asarray(index, dtype="datetime64[s]")
    geo = SUBSYSTEMS.get(area, SUBSYSTEMS["SIN"])
    base = BASE_LOAD_MW.get(area, 20_000.0)
    hod = hour_of_day(index).astype("f8")
    kinds = typeday_array(index)

    # Forma diaria de consumo (carga global), com pico noturno.
    shape = (
        1.00
        + 0.16 * np.sin(2 * np.pi * (hod - 8.0) / 24.0)
        + 0.10 * np.sin(4 * np.pi * (hod - 5.0) / 24.0)
        + 0.06 * np.exp(-((hod - 19.5) ** 2) / 6.0)
    )
    weekday = np.where(kinds == "util", 1.00,
                       np.where(kinds == "sabado", 0.95, 0.89))
    doy = index.astype("datetime64[D]").astype("i8").astype("f8")
    seasonal = 1.0 + 0.05 * np.cos(2 * np.pi * (doy - 20) / 365.25)

    rng = np.random.default_rng(RANDOM_SEED + abs(hash(area)) % 997)
    noise = 1.0 + 0.012 * np.convolve(
        rng.normal(0, 1, len(index)), np.ones(4) / 4.0, mode="same"
    )
    global_load = base * shape * weekday * seasonal * noise

    # Subtrai a MMGD para chegar a carga supervisionada.
    cz = solar.cos_zenith(index, geo["lat"], geo["lon"])
    ghi = solar.clearsky_ghi(cz) / 1000.0
    cap = capacity_of(area)
    day_seed = np.unique(index.astype("datetime64[D]").astype("i8"))
    rng2 = np.random.default_rng(RANDOM_SEED + 1)
    lut = {int(d): float(v) for d, v in zip(day_seed, 0.45 + 0.45 * rng2.random(len(day_seed)))}
    k = np.array([lut[int(d)] for d in index.astype("datetime64[D]").astype("i8")])
    mmgd = cap * 0.78 * ghi * k
    return np.maximum(global_load - mmgd, base * 0.28)


def balanco_frame(days: int = 120, areas: list[str] | None = None) -> Frame:
    """Frame com o mesmo esquema do balanco de energia do ONS."""
    areas = areas or ["SIN", "SE", "S", "NE", "N"]
    index = hourly_index(days)
    cols_area: list = []
    cols_ts: list = []
    carga: list = []
    eol: list = []
    sol: list = []
    hid: list = []
    ter: list = []
    inter: list = []
    for area in areas:
        geo = SUBSYSTEMS.get(area, SUBSYSTEMS["SIN"])
        load = supervised_load(index, area)
        cz = solar.cos_zenith(index, geo["lat"], geo["lon"])
        ghi = solar.clearsky_ghi(cz) / 1000.0
        rng = np.random.default_rng(RANDOM_SEED + abs(hash("g" + area)) % 991)
        wind_cap = {"NE": 22_000.0, "N": 1_200.0, "S": 5_200.0,
                    "SE": 1_800.0, "SIN": 30_000.0}.get(area, 2_000.0)
        wind = wind_cap * np.clip(
            0.35 + 0.30 * np.sin(2 * np.pi * np.arange(len(index)) / 53.0)
            + 0.12 * rng.normal(0, 1, len(index)), 0.02, 0.95
        )
        solar_c = {"NE": 9_000.0, "SE": 6_000.0, "S": 1_200.0,
                   "N": 400.0, "SIN": 16_000.0}.get(area, 1_000.0) * ghi
        hydro = np.maximum(load * 0.45 - solar_c * 0.2, load * 0.15)
        thermal = np.maximum(load * 0.12, 200.0)
        cols_area.extend([area] * len(index))
        cols_ts.extend(list(index))
        carga.extend(load.tolist())
        eol.extend(wind.tolist())
        sol.extend(solar_c.tolist())
        hid.extend(hydro.tolist())
        ter.extend(thermal.tolist())
        inter.extend((load * 0.05).tolist())

    cols = {
        "id_subsistema": np.array(cols_area, dtype=object),
        "din_instante": np.array(cols_ts, dtype="datetime64[s]"),
        "val_carga": np.asarray(carga, dtype="f8"),
        "val_gereolica": np.asarray(eol, dtype="f8"),
        "val_gersolar": np.asarray(sol, dtype="f8"),
        "val_gerhidraulica": np.asarray(hid, dtype="f8"),
        "val_gertermica": np.asarray(ter, dtype="f8"),
        "val_intercambio": np.asarray(inter, dtype="f8"),
    }
    f = Frame(cols, [demo_provenance("balanco-energia-subsistema")])
    f.quality.update({"rows": len(cols_ts), "discarded_bad_time": 0,
                      "discarded_short_line": 0, "duplicates": 0})
    return f


def coff_frame(days: int = 120, states: list[str] | None = None) -> Frame:
    """Frame com o esquema do constrained-off, restricao concentrada no dia."""
    states = states or ["BA", "PI", "RN", "CE", "MG", "MT", "MS", "GO"]
    index = hourly_index(days)
    rng = np.random.default_rng(RANDOM_SEED + 31)

    a_sub, a_est, a_usina, a_id, a_ts = [], [], [], [], []
    v_ger, v_disp, v_ref, c_raz, c_ori, p_con = [], [], [], [], [], []

    sub_of = {"BA": "NE", "PI": "NE", "RN": "NE", "CE": "NE",
              "MG": "SE", "MT": "SE", "MS": "SE", "GO": "SE"}
    for st in states:
        geo = SUBSYSTEMS[sub_of.get(st, "NE")]
        cz = solar.cos_zenith(index, geo["lat"], geo["lon"])
        ghi = solar.clearsky_ghi(cz) / 1000.0
        n_plants = 3
        for pl in range(n_plants):
            cap = float(rng.integers(60, 420))
            avail = cap * np.clip(ghi * (0.85 + 0.15 * rng.random(len(index))), 0, 1)
            # Restricao mais provavel no platô solar e em domingos.
            kinds = typeday_array(index)
            hod = hour_of_day(index)
            p_cut = np.where((hod >= 9) & (hod <= 15), 0.45, 0.05)
            p_cut = np.where(kinds == "domingo_feriado", p_cut * 1.8, p_cut)
            hit = rng.random(len(index)) < p_cut
            depth = np.where(hit, 0.25 + 0.5 * rng.random(len(index)), 0.0)
            ger = avail * (1.0 - depth)
            reason = np.where(
                hit & ((hod >= 9) & (hod <= 15)), "ENE",
                np.where(hit, rng.choice(["CNF", "REL"], size=len(index)), "")
            )
            origin = np.where(reason == "ENE", "SIS", np.where(reason == "", "", "LOC"))
            keep = avail > 0.5
            m = int(keep.sum())
            a_sub.extend([sub_of.get(st, "NE")] * m)
            a_est.extend([st] * m)
            a_usina.extend(["UFV %s-%02d" % (st, pl + 1)] * m)
            a_id.extend(["%s_UFV%02d" % (st, pl + 1)] * m)
            a_ts.extend(list(index[keep]))
            v_ger.extend(ger[keep].tolist())
            v_disp.extend(avail[keep].tolist())
            v_ref.extend(avail[keep].tolist())
            c_raz.extend(reason[keep].tolist())
            c_ori.extend(origin[keep].tolist())
            p_con.extend(["SE %s %d - 230 kV" % (st, 100 + pl)] * m)

    cols = {
        "id_subsistema": np.array(a_sub, dtype=object),
        "id_estado": np.array(a_est, dtype=object),
        "nom_usina": np.array(a_usina, dtype=object),
        "id_ons": np.array(a_id, dtype=object),
        "din_instante": np.array(a_ts, dtype="datetime64[s]"),
        "val_geracao": np.asarray(v_ger, dtype="f8"),
        "val_disponibilidade": np.asarray(v_disp, dtype="f8"),
        "val_geracaoreferencia": np.asarray(v_ref, dtype="f8"),
        "cod_razaorestricao": np.array(c_raz, dtype=object),
        "cod_origemrestricao": np.array(c_ori, dtype=object),
        "nom_pontoconexao": np.array(p_con, dtype=object),
    }
    f = Frame(cols, [demo_provenance("restricao_coff_fotovoltaica")])
    f.quality.update({"rows": len(a_ts)})
    return f


def catalog_fallback() -> list[dict]:
    """Catalogo minimo quando a API CKAN nao esta acessivel."""
    from ..ons.catalog import CURATED, PLANNED
    out = []
    for key, spec in CURATED.items():
        out.append({"id": spec["package"], "title": spec["title"],
                    "notes": spec["role"], "curated": True,
                    "role": spec["role"], "resources": []})
    for p in PLANNED:
        out.append({"id": p["package"], "title": p["package"],
                    "notes": p["role"], "curated": False,
                    "role": p["role"], "resources": []})
    return out
