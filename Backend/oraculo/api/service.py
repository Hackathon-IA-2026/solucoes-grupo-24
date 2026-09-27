# -*- coding: utf-8 -*-
"""Fachada de dominio consumida pelas rotas.

Nenhum modulo de dominio importa starlette; nenhuma rota faz calculo analitico.
Esta camada e a costura entre os dois, e e onde vive o cache em memoria do
bundle e dos modelos treinados.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

import numpy as np

from .. import config
from ..core.calendar_br import typeday_array
from ..core.frame import nan_to_none
from ..core.timeutils import hour_of_day, iso_list
from ..features import builder
from ..models import decomposition, mmgd, risk
from ..models.baselines import LABELS as BASELINE_LABELS
from ..models.baselines import persistence, seasonal_naive
from ..models.quantile import QuantileModel
from ..ons import cache, catalog, ckan
from ..pipeline import ingest
from ..tempo import clima
from ..triangulation import evidence
from ..validation import backtest, metrics
from .service_clm import ClmMixin
from .service_docs import DocsMixin
from .service_fronteira import FronteiraMixin
from .service_bess import BessMixin
from .service_ene import EneMixin
from .service_tempo import TempoMixin
from .service_mapa import MapaMixin

_LOCK = threading.Lock()


@dataclass
class AreaState:
    area: str
    index: np.ndarray
    series: dict[str, np.ndarray]
    mmgd_est: mmgd.MMGDEstimate
    decomposition: decomposition.Decomposition
    features: builder.FeatureMatrix
    gaps: int = 0
    models: dict[str, QuantileModel] = field(default_factory=dict)
    # Proveniencia do tempo observado (ERA5/Open-Meteo) do grupo "clima".
    weather_prov: dict = field(default_factory=dict)


class Service(MapaMixin, ClmMixin, DocsMixin, FronteiraMixin, BessMixin,
              EneMixin, TempoMixin):
    """Estado da aplicacao: bundle ingerido, series por area, modelos treinados.

    As rotas do Mapa Inteligente vivem em MapaMixin (service_mapa.py), para que
    as abas ja existentes permanecam intocadas.
    """

    def __init__(self) -> None:
        self.bundle: ingest.Bundle | None = None
        self.areas: dict[str, AreaState] = {}
        self._catalog: list[dict] | None = None
        # Um modelo de risco por horizonte (a memoria de restricao muda com ele).
        self._risk_cache: dict[str, dict] = {}
        # Tempo observado por area (sub)sistema, reaproveitado entre carga e risco.
        self._weather: dict[str, tuple[dict | None, dict]] = {}
        self._triang_cache: dict | None = None

    # ------------------------------------------------------------- setup
    def ensure(self, *, force_demo: bool = False, refresh: bool = False) -> None:
        with _LOCK:
            if self.bundle is not None and not refresh:
                return
            self.bundle = ingest.load_bundle(refresh=refresh, force_demo=force_demo)
            self.areas.clear()
            self._risk_cache = {}
            self._weather = {}
            self._triang_cache = None
            for area in ("SIN", "SE", "S", "NE", "N"):
                st = self._build_area(area)
                if st is not None:
                    self.areas[area] = st

    def _build_area(self, area: str) -> AreaState | None:
        assert self.bundle is not None
        ser = ingest.area_series(self.bundle.balanco, area)
        if not ser or "index" not in ser:
            return None
        ts = ser["index"]
        load = ser["carga_supervisionada"]
        if np.isfinite(load).sum() < 48:
            return None
        est = mmgd.estimate(ts, load, area)
        dec = decomposition.decompose(ts, load, est.mmgd_mw, area)
        weather, wprov = self._weather_for(ts, area)
        fm = builder.build(
            ts, area=area, target=load, mmgd=est.mmgd_mw,
            ger_eolica=ser.get("ger_eolica"),
            margem_controlavel=ser.get("margem_controlavel"),
            intercambio=ser.get("intercambio"),
            weather=weather,
        )
        gaps = int(ser.get("_gaps", np.array([0]))[0])
        return AreaState(area, ts, ser, est, dec, fm, gaps, weather_prov=wprov)

    def _weather_for(self, index: np.ndarray, area: str) -> tuple[dict | None, dict]:
        """Tempo observado (ERA5) na grade de `index`; None no modo demo/offline.

        No modo demo o resto do bundle ja e sintetico e rotulado; buscar tempo
        real para ele misturaria as duas coisas. Sem rede, weather_for_area
        devolve None e o grupo clima sai do modelo (nada inventado).
        """
        if self.bundle is None or self.bundle.mode == "demo":
            return None, {"dataset": "Open-Meteo · ERA5", "mode": "demo",
                          "lag_note": "modo demonstrativo: grupo clima fora do modelo"}
        key = "%s|%s|%s|%d" % (area, index[0], index[-1], len(index))
        if key not in self._weather:
            self._weather[key] = clima.weather_for_area(index, area)
        return self._weather[key]

    def mode(self) -> str:
        return self.bundle.mode if self.bundle else "demo"

    def provenance(self) -> list[dict]:
        out = self.bundle.provenance() if self.bundle else []
        # O tempo observado do grupo "clima" tambem e dado de entrada: entra no
        # envelope de proveniencia como os arquivos do ONS.
        st = self.areas.get(config.DEFAULT_AREA)
        if st is not None and st.weather_prov:
            out = list(out) + [dict(st.weather_prov)]
        return out

    def notes(self) -> list[str]:
        out = [config.DISCLAIMER]
        if self.mode() == "demo":
            out.insert(0, "%s — valores gerados deterministicamente, sem "
                          "correspondência com eventos verificados."
                       % config.DEMO_BANNER)
        st = self.areas.get(config.DEFAULT_AREA)
        if st is not None and st.mmgd_est.method == "envelope":
            out.append("MMGD estimada pelo método do envelope: valor "
                       "conservador (piso), não valor central.")
        if st is not None and not any(n.startswith("clima.") for n in st.features.names):
            out.append("Sem tempo observado (Open-Meteo/ERA5 indisponível): os "
                       "modelos rodam sem o grupo de variáveis climáticas.")
        return out

    def _area(self, area: str) -> AreaState:
        self.ensure()
        if area in self.areas:
            return self.areas[area]
        if config.DEFAULT_AREA in self.areas:
            return self.areas[config.DEFAULT_AREA]
        raise LookupError("nenhuma área disponível")

    # ------------------------------------------------------------- health
    def health(self) -> dict:
        self.ensure()
        cs = cache.stats()
        return {
            "version": config.VERSION,
            "app": config.APP_NAME,
            "team": config.TEAM,
            "network": ckan.network_available(),
            "mode": self.mode(),
            "cache_entries": cs["entries"],
            "cache_bytes": cs["bytes"],
            "areas_ready": sorted(self.areas.keys()),
            "datasets": self.bundle.reports_dicts() if self.bundle else [],
            "sources": config.SOURCES,
        }

    # ------------------------------------------------------------- catalog
    def catalog_payload(self, refresh: bool = False) -> dict:
        if self._catalog is not None and not refresh:
            packages = self._catalog
        else:
            names, mode = ckan.package_list(refresh=refresh)
            curated_by_pkg = {c["package"]: c for c in catalog.curated_summary()}
            packages = []
            if names:
                for n in sorted(names):
                    c = curated_by_pkg.get(n)
                    packages.append({
                        "id": n,
                        "title": c["title"] if c else n,
                        "notes": c["role"] if c else "",
                        "curated": bool(c),
                        "role": c["role"] if c else "",
                        "granularity": c["granularity"] if c else "",
                        "fields": c["fields"] if c else [],
                    })
            else:
                from ..demo.synthetic import catalog_fallback
                packages = catalog_fallback()
            self._catalog = packages
        return {
            "count": len(packages),
            "packages": packages,
            "curated": catalog.curated_summary(),
            "planned": catalog.PLANNED,
            "external": catalog.EXTERNAL,
            "reasons": catalog.RAZOES,
            "origins": catalog.ORIGENS,
            "cache": cache.stats(),
        }

    def package_detail(self, pkg_id: str) -> dict:
        data, mode = ckan.package_show(pkg_id)
        resources = []
        for r in (data.get("resources") or []):
            y, m = ckan.resource_period(r.get("name") or r.get("url") or "")
            resources.append({
                "name": r.get("name"),
                "format": r.get("format"),
                "url": r.get("url"),
                "year": y,
                "month": m,
                "size": r.get("size"),
            })
        resources.sort(key=lambda d: (d["year"] or 0, d["month"] or 0), reverse=True)
        return {
            "id": pkg_id,
            "title": data.get("title") or pkg_id,
            "notes": (data.get("notes") or "")[:1200],
            "resources": resources[:60],
            "resource_count": len(resources),
            "mode": mode,
        }

    # ------------------------------------------------------------- series
    def series_payload(self, area: str, last_hours: int = 24 * 30) -> dict:
        st = self._area(area)
        n = min(last_hours, len(st.index))
        sl = slice(len(st.index) - n, len(st.index))
        out = {
            "area": st.area,
            "area_name": config.SUBSYSTEMS.get(st.area, {}).get("name", st.area),
            "index": iso_list(st.index[sl]),
            "units": "MWmed",
            "gaps": st.gaps,
            "series": {
                "carga_supervisionada": nan_to_none(st.decomposition.carga_supervisionada[sl]),
                "mmgd_estimada": nan_to_none(st.decomposition.mmgd_estimada[sl]),
                "carga_global": nan_to_none(st.decomposition.carga_global[sl]),
            },
            "mmgd": st.mmgd_est.summary(),
        }
        for key in ("ger_eolica", "ger_solar_centralizada", "margem_controlavel",
                    "intercambio"):
            if key in st.series:
                out["series"][key] = nan_to_none(st.series[key][sl])
        if st.mmgd_est.envelope is not None:
            out["series"]["envelope_carga_global"] = nan_to_none(
                st.mmgd_est.envelope[sl])
        return out

    # -------------------------------------------------------- decomposition
    def decomposition_payload(self, area: str, hours: int = 48) -> dict:
        st = self._area(area)
        n = min(hours, len(st.index))
        sl = slice(len(st.index) - n, len(st.index))
        dec = st.decomposition
        window = decomposition.decompose(
            st.index[sl], dec.carga_supervisionada[sl], dec.mmgd_estimada[sl], st.area
        )
        payload = window.to_dict()
        payload.update({
            "index": iso_list(st.index[sl]),
            "carga_global": nan_to_none(window.carga_global),
            "mmgd_estimada": nan_to_none(window.mmgd_estimada),
            "carga_supervisionada": nan_to_none(window.carga_supervisionada),
            "mmgd_share": nan_to_none(window.mmgd_share),
            "cloud_factor": nan_to_none(st.mmgd_est.cloud_factor[sl]),
            "ghi_norm": nan_to_none(st.mmgd_est.ghi_norm[sl]),
            "full_period": {
                "start": str(st.index[0]), "end": str(st.index[-1]),
                "hours": int(len(st.index)),
            },
            "clm_inputs": decomposition.clm_inputs(dec),
            "mmgd": st.mmgd_est.summary(),
            "implied_capacity_mwp": (
                round(mmgd.implied_capacity(st.mmgd_est) or 0.0, 1)
                if mmgd.implied_capacity(st.mmgd_est) else None
            ),
        })
        return payload

    # ------------------------------------------------------------- forecast
    def forecast_payload(self, area: str, horizon: str = "3h",
                         asymmetric: bool = True) -> dict:
        st = self._area(area)
        steps = config.HORIZONS.get(horizon, 3)
        y = st.decomposition.carga_supervisionada
        y_t = backtest.shift_target(y, steps)
        valid = st.features.valid & np.isfinite(y_t)
        split = backtest.chronological_split(st.index, valid, embargo=steps)
        if len(split.train_idx) < st.features.p + 10 or len(split.test_idx) < 5:
            raise ValueError("dados insuficientes para o horizonte %s" % horizon)

        key = "%s|%s" % (horizon, "asym" if asymmetric else "sym")
        model = st.models.get(key)
        if model is None:
            model = QuantileModel(quantiles=config.QUANTILES, asymmetric=asymmetric)
            model.fit(st.features.X[split.train_idx], y_t[split.train_idx],
                      st.features.patamar[split.train_idx], names=st.features.names)
            st.models[key] = model

        # Metricas sobre TODO o conjunto de teste, para serem comparaveis ao
        # backtest. A serie devolvida a interface e apenas a janela recente.
        pred_all = model.predict(st.features.X[split.test_idx])
        y_all = y_t[split.test_idx]
        p50_all = pred_all[0.50]
        pers_all = persistence(y, steps)[split.test_idx]
        seas_all = seasonal_naive(y, steps)[split.test_idx]
        mae_model = metrics.mae(y_all, p50_all)

        show = split.test_idx[-min(len(split.test_idx), 24 * 7):]
        pred = model.predict(st.features.X[show])
        yte = y_t[show]
        p50 = pred[0.50]
        pers = persistence(y, steps)[show]
        seas = seasonal_naive(y, steps)[show]
        from ..models.baselines import skill as skill_fn
        return {
            "area": st.area,
            "horizon": horizon,
            "steps": steps,
            "asymmetric": asymmetric,
            "index": iso_list(st.index[show]),
            "observed": nan_to_none(yte),
            "p10": nan_to_none(pred[0.10]),
            "p50": nan_to_none(p50),
            "p90": nan_to_none(pred[0.90]),
            "baseline_persistence": nan_to_none(pers),
            "baseline_seasonal": nan_to_none(seas),
            "metrics": metrics.point_metrics(y_all, p50_all),
            "metrics_window": metrics.point_metrics(yte, p50),
            "by_patamar": metrics.by_patamar(
                y_all, p50_all, hour_of_day(st.index[split.test_idx])),
            "calibration": metrics.calibration(y_all, pred_all),
            "skill": {
                "vs_persistence": round(
                    skill_fn(mae_model, metrics.mae(y_all, pers_all)), 4),
                "vs_seasonal": round(
                    skill_fn(mae_model, metrics.mae(y_all, seas_all)), 4),
            },
            "drivers": model.drivers(st.features),
            "loss": model.describe(),
            "train": split.to_dict(),
        }

    # ------------------------------------------------------------- profiles
    def profiles_payload(self, area: str) -> dict:
        st = self._area(area)
        dec = st.decomposition
        return {
            "area": st.area,
            "area_name": config.SUBSYSTEMS.get(st.area, {}).get("name", st.area),
            "typedays": decomposition.typeday_profiles(
                st.index, dec.carga_supervisionada, dec.mmgd_estimada),
            "clm_inputs": decomposition.clm_inputs(dec),
            "period": {"start": str(st.index[0]), "end": str(st.index[-1])},
            "note": ("Insumos agregados propostos para a parametrização de "
                     "modelos equivalentes. Não são parâmetros do CLM prontos "
                     "para simulação."),
        }

    # ------------------------------------------------------------- risk
    def risk_payload(self, horizon: str = "d1", level: str = "estado",
                     min_probability: float = 0.0) -> dict:
        self.ensure()
        if horizon not in config.HORIZONS:
            horizon = "d1"
        if horizon not in self._risk_cache:
            self._risk_cache[horizon] = self._compute_risk(horizon)
        payload = self._risk_cache[horizon]
        out = dict(payload)
        out["horizon"] = horizon
        out["level"] = level
        out["events"] = [e for e in payload["events"]
                         if e["probability"] >= min_probability]
        return out

    def _compute_risk(self, horizon: str = "d1") -> dict:
        """Classificador de ocorrencia de restricao, por area, para um horizonte.

        O horizonte define o que o operador sabe no momento da previsao: a
        memoria de restricao (`regime.hist_restricao`) termina `lag` horas
        antes do instante alvo (config.HORIZONS: 30min -> 1 h, 3h -> 3 h,
        D+1 -> 24 h). Horizonte curto = informacao mais recente = modelo e
        AUC diferentes. Antes o horizonte so trocava o rotulo da resposta.
        """
        assert self.bundle is not None
        lag = int(config.HORIZONS[horizon])
        coff = self.bundle.coff
        area_field = "id_estado" if "id_estado" in coff else "id_subsistema"
        areas = [a for a in coff.unique(area_field).tolist() if a]
        sin = self.areas.get(config.DEFAULT_AREA)

        rows: list[dict] = []
        events: list[dict] = []
        model_info: dict = {"kind": "regressao_logistica_regularizada",
                            "horizon": horizon, "memory_lag_h": lag}

        for area in areas[:14]:
            labels = risk.build_labels(coff, area_field, area)
            if len(labels.index) < 72:
                continue
            y = labels.ocorreu.astype("f8")
            # SEM VAZAMENTO: nao se passa `target=corte_mw`, senao a defasagem
            # de 1 h do proprio rotulo entraria como variavel e o modelo
            # "acertaria" lendo a resposta. A memoria operativa legitima e a
            # historia de restricao defasada pelo HORIZONTE (`lag` horas):
            # e o que o operador de fato conhece ao emitir a previsao.
            ss = _subsystem_of(area)
            weather, _ = self._weather_for(labels.index, ss)
            fm = builder.build(labels.index, area=ss, weather=weather)
            hist = risk.occurrence_memory(y, min_lag=lag, window=7 * 24)
            fm = builder.append_column(fm, "regime.hist_restricao_%dh" % lag, hist)
            # Estado recente: fracao das 3 ultimas horas CONHECIDAS na emissao
            # (terminam `lag` h antes do alvo). E o sinal de persistencia que
            # separa o 30 min (corte em curso) do D+1 (so o historico).
            recent = risk.occurrence_memory(y, min_lag=lag, window=3)
            fm = builder.append_column(fm, "regime.restricao_recente_%dh" % lag, recent)
            # Restringe a janela solar: fora dela a resposta e trivial e
            # inflaria o AUC sem informar nada ao operador.
            ghi = fm.X[:, fm.names.index("solar.ghi_norm")]
            daylight = ghi > config.RISK_DAYLIGHT_GHI_MIN
            if config.RISK_DAYLIGHT_ONLY and daylight.sum() > 200:
                fm = builder.mask_valid(fm, daylight)
            valid = fm.valid & np.isfinite(y)
            split = backtest.chronological_split(labels.index, valid, embargo=1)
            auc = None
            prob = np.full(len(labels.index), float(np.mean(y)) if len(y) else 0.0)
            try:
                m = risk.LogisticModel()
                m.fit(fm.X[split.train_idx], y[split.train_idx])
                m.calibrate(fm.X[split.test_idx], y[split.test_idx])
                prob = m.probability(fm.X)
                auc = metrics.roc_auc(y[split.test_idx], m.raw_probability(fm.X[split.test_idx]))
                model_info.setdefault("per_area", {})[area] = {
                    "auc_oos": None if auc is None or np.isnan(auc) else round(auc, 4),
                    **m.info,
                }
            except (ValueError, np.linalg.LinAlgError):
                pass

            cond = risk.conditional_mean_cut(labels)
            # Janela prospectiva: ultimas 24 h da serie como proxy do D+1.
            tail = slice(max(0, len(labels.index) - 24), len(labels.index))
            p_area = float(np.nanmax(prob[tail])) if len(prob[tail]) else 0.0
            exp_mw = float(p_area * cond)
            hours = hour_of_day(labels.index[tail])
            peak_i = int(np.nanargmax(prob[tail])) if len(prob[tail]) else 0
            peak_hour = int(hours[peak_i]) if len(hours) else 12
            pat = config.patamar_of_hour(peak_hour)

            energy_signal = _energy_signal(sin, peak_hour)
            electric_signal = _electric_signal(sin)
            rw = risk.reason_weights(labels, hours, energy_signal, electric_signal)
            reason = risk.dominant_reason(rw)
            sev = risk.severity(p_area, exp_mw, area,
                                mw_reference=max(cond * 2.0, 100.0))

            idx_tail = labels.index[tail]
            window = [str(idx_tail[0]), str(idx_tail[-1])] if len(idx_tail) else ["", ""]
            rows.append({
                "area": area,
                "subsystem": _subsystem_of(area),
                "probability": round(p_area, 4),
                "expected_mw": round(exp_mw, 1),
                "severity": sev,
                "reason": reason,
                "reason_weights": rw,
                "window": window,
                "criticality": config.criticality_of(area),
                "history": labels.summary(),
                "auc_oos": None if auc is None or np.isnan(auc) else round(auc, 4),
                "hourly_probability": nan_to_none(prob[tail]),
                "hourly_index": iso_list(idx_tail),
            })

            poc = ""
            if "nom_pontoconexao" in coff:
                sel = coff.eq(area_field, area)
                vals = [v for v in sel["nom_pontoconexao"].tolist() if v]
                poc = vals[0] if vals else ""
            events.append({
                "id": "EV-%s-%02d" % (area, peak_hour),
                "area": area,
                "subsystem": _subsystem_of(area),
                "point_of_connection": poc,
                "probability": round(p_area, 4),
                "expected_mw": round(exp_mw, 1),
                "severity": sev,
                "reason": reason,
                "reason_label": risk.reason_label(reason),
                "reason_weights": rw,
                "patamar": pat,
                "window": window,
                "peak_hour": peak_hour,
                "evidence": risk.evidence_items(
                    probability=p_area, expected_mw=exp_mw,
                    ghi_norm=_ghi_at(sin, peak_hour),
                    margin_mw=_margin_at(sin),
                    reason=reason, reason_weights_=rw,
                    provenance_dataset=(self.bundle.coff.provenance[0].dataset
                                        if self.bundle.coff.provenance else "coff"),
                ),
                "recommended_actions": risk.recommended_actions(reason, exp_mw, pat),
            })

        rows.sort(key=lambda d: (-d["severity"], d["area"]))
        events.sort(key=lambda d: (-d["severity"], d["area"]))
        aucs = [r["auc_oos"] for r in rows if r["auc_oos"] is not None]
        model_info["auc_oos_median"] = round(float(np.median(aucs)), 4) if aucs else None
        model_info["areas_modeled"] = len(rows)
        return {"areas": rows, "events": events, "model": model_info,
                "reasons": catalog.RAZOES, "origins": catalog.ORIGENS}

    # ---------------------------------------------------------- validation
    def validation_payload(self, area: str, asymmetric: bool = True) -> dict:
        st = self._area(area)
        y = st.decomposition.carga_supervisionada
        res = backtest.run(st.features, y, asymmetric=asymmetric)
        res["area"] = st.area
        res["asymmetry_effect"] = backtest.compare_asymmetry(st.features, y, "3h")
        res["baseline_labels"] = BASELINE_LABELS
        res["patamares"] = {k: list(v) for k, v in config.PATAMARES.items()}
        res["weights"] = {k: {"subestimacao": v[0], "superestimacao": v[1]}
                          for k, v in config.ASYMMETRIC_WEIGHTS.items()}
        return res

    # -------------------------------------------------------- triangulation
    def triangulation_payload(self) -> dict:
        """Desempate das tres camadas de evidencia da MMGD.

        Modo real: empreendimentos do pipeline espacial (BDGD 2025 da LIGHT e da
        Enel RJ x cadastro de MMGD da ANEEL, src/spatial/mmgd.py), uma linha por
        CEG, com a camada 1 (satelite) declarada ausente. Modo demo: o gerador
        deterministico, rotulado como tal. Sem a tabela real (espacializacao
        ainda nao rodada) -> LookupError com o comando, nunca o gerador.
        """
        self.ensure()
        if self.mode() == "demo":
            return self._triangulation_demo()
        if self._triang_cache is None:
            self._triang_cache = self._triangulation_real()
        return self._triang_cache

    def _triangulation_real(self) -> dict:
        import pandas as pd

        from src.spatial.saidas import SAIDA_MMGD_EMPREENDIMENTOS as ARQ
        if not ARQ.exists():
            raise LookupError("tabela de empreendimentos de MMGD ainda não gerada: rode "
                              "`python -m src.spatial.construir` em Backend/ (ou o "
                              "run_heavywork, etapa espacial)")
        df = pd.read_parquet(ARQ)
        units = evidence.units_from_empreendimentos(df)
        agg = evidence.aggregate(units)
        for a in agg:
            # Capacidade implicada pela carga e por subsistema; aqui a area e a
            # distribuidora, sem serie de carga propria: nao se aplica.
            a["declared_config_mwp"] = None
            a["implied_capacity_mwp"] = None
            a["implied_over_declared"] = None
        ref = sorted(str(v)[:10] for v in df["data_bdgd"].dropna().unique())
        dmax = str(df["data"].max())[:10]
        prov = [{"dataset": "BDGD · %s" % ", ".join(sorted(df["distribuidora"].unique())),
                 "resource": "unidades geradoras de MMGD (UGBT/UGMT/UGAT), data de referência %s"
                             % ", ".join(ref),
                 "mode": "cache", "rows": int((df["categoria"] != "lag_sistema").sum()),
                 "lag_note": "Base anual: o que entrou depois da data de referência "
                             "aparece como defasagem de sistema."},
                {"dataset": "ANEEL · empreendimentos de micro e minigeração distribuída",
                 "resource": "cadastro até %s" % dmax, "mode": "cache",
                 "rows": int((df["categoria"] != "bdgd_sem_homologacao").sum()),
                 "lag_note": "Cruzamento pelo código do empreendimento (CEG_GD = "
                             "CodEmpreendimento), src/spatial/mmgd.py."}]
        return {
            "areas": agg,
            "layers": [dict(l, observed=(l["layer"] != 1)) for l in evidence.LAYERS],
            "layer1_available": False,
            "matrix": evidence.matrix_cells_two_layers(),
            "classes": {k: {"label": evidence.CLASS_LABELS[k],
                            "note": evidence.CLASS_NOTES[k],
                            "counts": evidence.counts_in_correction(k)}
                        for k in evidence.CLASSES},
            "sample": [u.to_dict() for u in evidence.sample_units(units)],
            "units_total": len(units),
            "provenance": prov,
            "note": ("Dado real: %d empreendimentos de MMGD da LIGHT e da Enel RJ, BDGD × "
                     "cadastro da ANEEL. A camada 1 (satélite) ainda não cobre a área: "
                     "o desempate usa topologia × cadastro, e nenhuma detecção é "
                     "presumida. A auditoria por satélite está na aba \"Visão · "
                     "auditoria 3 camadas\"." % len(units)),
        }

    def _triangulation_demo(self) -> dict:
        areas = sorted(self.areas.keys() - {"SIN"}) or ["SE", "S", "NE", "N"]
        units = evidence.demo_units(areas)
        agg = evidence.aggregate(units)
        for a in agg:
            declared = config.capacity_of(a["area"])
            a["declared_config_mwp"] = declared
            st = self.areas.get(a["area"])
            imp = mmgd.implied_capacity(st.mmgd_est) if st else None
            a["implied_capacity_mwp"] = round(imp, 1) if imp else None
            a["implied_over_declared"] = (
                round(imp / declared, 3) if imp and declared else None
            )
        return {
            "areas": agg,
            "layers": [dict(l, observed=True) for l in evidence.LAYERS],
            "layer1_available": True,
            "matrix": evidence.matrix_cells(),
            "classes": {k: {"label": evidence.CLASS_LABELS[k],
                            "note": evidence.CLASS_NOTES[k],
                            "counts": evidence.counts_in_correction(k)}
                        for k in evidence.CLASSES},
            "sample": [u.to_dict() for u in units[:40]],
            "units_total": len(units),
            "note": ("%s — conjunto demonstrativo com os campos e as cadências "
                     "reais; nenhuma unidade corresponde a um empreendimento."
                     % config.DEMO_BANNER),
        }

    # ---------------------------------------------------------- provenance
    def provenance_payload(self) -> dict:
        self.ensure()
        return {
            "cache": cache.stats(),
            "entries": cache.all_entries(),
            "bundle": self.provenance(),
            "reports": self.bundle.reports_dicts() if self.bundle else [],
            "mode": self.mode(),
        }

    def ingest_payload(self, *, year: int | None, months: list[int] | None,
                       force: bool) -> dict:
        self.ensure(refresh=True) if force else self.ensure()
        b = ingest.load_bundle(year=year, months=months, refresh=force)
        self.bundle = b
        self.areas.clear()
        self._risk_cache = {}
        self._weather = {}
        self._triang_cache = None
        for area in ("SIN", "SE", "S", "NE", "N"):
            st = self._build_area(area)
            if st is not None:
                self.areas[area] = st
        return {"mode": b.mode, "reports": b.reports_dicts(),
                "areas_ready": sorted(self.areas.keys())}


# ------------------------------------------------------------- helpers
_STATE_TO_SUB = {
    "BA": "NE", "PI": "NE", "RN": "NE", "CE": "NE", "PE": "NE", "PB": "NE",
    "AL": "NE", "SE": "NE", "MA": "NE",
    "MG": "SE", "SP": "SE", "RJ": "SE", "ES": "SE", "GO": "SE", "MT": "SE",
    "MS": "SE", "DF": "SE",
    "PR": "S", "SC": "S", "RS": "S",
    "PA": "N", "TO": "N", "AP": "N", "AM": "N", "RO": "N", "AC": "N", "RR": "N",
}


def _subsystem_of(area: str) -> str:
    if area in config.SUBSYSTEMS:
        return area
    return _STATE_TO_SUB.get(area, "SIN")


def _energy_signal(sin: AreaState | None, hour: int) -> float:
    """Excedente projetado versus margem controlavel, normalizado."""
    if sin is None:
        return 0.5
    hod = hour_of_day(sin.index)
    sel = hod == hour
    if not sel.any():
        return 0.5
    mmgd_h = float(np.nanmean(sin.decomposition.mmgd_estimada[sel]))
    load_h = float(np.nanmean(sin.decomposition.carga_supervisionada[sel]))
    if load_h <= 0:
        return 0.5
    return float(np.clip(mmgd_h / load_h * 3.0, 0.0, 1.0))


def _electric_signal(sin: AreaState | None) -> float:
    if sin is None or "intercambio" not in sin.series:
        return 0.3
    v = sin.series["intercambio"]
    v = v[np.isfinite(v)]
    if not len(v):
        return 0.3
    return float(np.clip(np.abs(v[-24:]).mean() / (np.abs(v).max() or 1.0), 0.0, 1.0))


def _ghi_at(sin: AreaState | None, hour: int) -> float:
    if sin is None:
        return 0.0
    hod = hour_of_day(sin.index)
    sel = hod == hour
    return float(np.nanmean(sin.mmgd_est.ghi_norm[sel])) if sel.any() else 0.0


def _margin_at(sin: AreaState | None) -> float:
    if sin is None or "margem_controlavel" not in sin.series:
        return 0.0
    v = sin.series["margem_controlavel"]
    v = v[np.isfinite(v)]
    return float(v[-24:].mean()) if len(v) else 0.0


SERVICE = Service()
