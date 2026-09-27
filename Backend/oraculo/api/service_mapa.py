# -*- coding: utf-8 -*-
"""Fachada do Mapa Inteligente de Perfis de Carga e Geracao Distribuida.

Desafio Radix + AXIA + Cepel. Implementado como mixin para nao tocar no
`Service` existente: as abas que ja funcionavam continuam identicas.
"""
from __future__ import annotations

import threading

import numpy as np

from .. import config
from ..profiles import classes as C
from ..profiles import medidos as M
from ..substations import mapper, registry
from ..vision import detector as D
from ..vision import evaluate as EV
from ..vision import render as R
from ..vision import tiles as T

_LOCK = threading.Lock()

# Classes urbanas usadas no banco de ensaio do detector.
BENCH_CLASSES = ("residencial", "comercial", "industrial", "misto")
BENCH_SEEDS = (11, 23, 37)

CHANNEL_KEYS = {"azul": "blue_excess", "borda": "edge_density",
                "luminancia": "luminance"}


def channel_key(channel: str) -> str:
    return CHANNEL_KEYS.get(channel, "blue_excess")


def _r(v: float | None, casas: int) -> float | None:
    """Arredonda para o JSON; NaN/None (ex.: sem domingo na serie) vira null."""
    return None if v is None or not np.isfinite(v) else round(float(v), casas)


class MapaMixin:
    """Rotas do Mapa Inteligente. Estado proprio, sem colisao com o resto."""

    _registry: registry.Registry | None = None
    _profiles: dict[str, mapper.SubstationProfile] = {}
    _bench: dict | None = None
    _scenes: dict[str, T.SyntheticScene] = {}
    # O PNG de 768x768 com ruido de sensor nao comprime: ~1 MB por imagem.
    # Vale guardar os bytes em memoria em vez de redesenhar a cada clique.
    _png_cache: dict[str, bytes] = {}
    # Composicao do subsistema (NNLS sobre a curva real) por subsistema: prior regional.
    _regional: dict[str, dict] = {}

    # ------------------------------------------------------------ registro
    def registry_ensure(self, *, refresh: bool = False) -> registry.Registry:
        with _LOCK:
            if self._registry is None or refresh:
                type(self)._registry = registry.load_registry(
                    force_demo=(self.mode() == "demo"))
                type(self)._profiles = {}
            return self._registry

    def _subsystem_series(self) -> dict:
        """Series de carga por subsistema, do dado real ja ingerido."""
        self.ensure()
        out: dict[str, dict] = {}
        for ss, st in self.areas.items():
            if ss == "SIN":
                continue
            out[ss] = {"index": st.index,
                       "load": st.decomposition.carga_supervisionada}
        return out

    # ------------------------------------------------------------ dado real
    def _real_profile(self, prof: mapper.SubstationProfile) -> mapper.SubstationProfile:
        """Composicao e MMGD reais (fronteira T-D) no lugar das da amostra sintetica.

        No modo demo, ou com a base da fronteira ainda em construcao, o perfil
        fica o da amostra sintetica, com `real: false` e a nota dizendo por que.
        """
        from .service_fronteira import BaseNotReady
        if self.mode() == "demo" or self._fr_demo():
            return self._flag_synthetic(prof, "modo demonstrativo")
        try:
            fr = self.fronteira_detail_payload(prof.substation.sub_id, compare=False)
        except BaseNotReady:
            return self._flag_synthetic(prof, "base BDGD/ANEEL da fronteira T–D em construção")
        except LookupError:
            return self._flag_synthetic(prof, "SE fora da base da fronteira T–D")
        return mapper.with_frontier(prof, fr, sin_ratio=self._sin_mmgd_ratio(),
                                    regional=self._regional_mix(prof.substation.subsystem))

    @staticmethod
    def _flag_synthetic(prof: mapper.SubstationProfile, motivo: str) -> mapper.SubstationProfile:
        prof.load_class["real"] = False
        prof.mmgd["real"] = False
        prof.notes = ["SEM DADO REAL (%s): composição e MMGD abaixo vêm da amostra "
                      "SINTÉTICA de ortoimagem — só demonstração." % motivo] + list(prof.notes)
        return prof

    def _sin_mmgd_ratio(self) -> float:
        """MMGD instalada / carga media do SIN: a referencia do nivel de penetracao."""
        self.ensure()
        st = self.areas.get(config.DEFAULT_AREA)
        load = float(np.nanmean(st.decomposition.carga_supervisionada)) if st else 0.0
        return config.capacity_of("SIN") / load if load > 0 else 0.0

    def _regional_mix(self, subsystem: str) -> dict | None:
        if subsystem not in self._regional:
            ser = self._subsystem_series().get(subsystem)
            if not ser:
                return None
            mix = C.decompose(ser["index"], ser["load"])
            d = mix.to_dict()
            type(self)._regional[subsystem] = {k: d[k] for k in ("weights", "dominant", "label", "r2")}
        return self._regional[subsystem]

    # ------------------------------------------------------------ lista
    def substations_payload(self, *, uf: str = "", subsystem: str = "",
                            frontier_only: bool = True, limit: int = 24,
                            offset: int = 0, analyse: bool = True) -> dict:
        reg = self.registry_ensure()
        pool = reg.filter(uf=uf, subsystem=subsystem, frontier_only=frontier_only)
        pool = sorted(pool, key=lambda s: (-s.frontier_mva, s.name))
        total = len(pool)
        page = pool[offset:offset + max(1, limit)]

        rows: list[dict] = []
        profiles: list[mapper.SubstationProfile] = []
        if analyse:
            series = self._subsystem_series()
            det = D.build_detector()
            for s in page:
                prof = self._profiles.get(s.sub_id)
                if prof is None:
                    ser = series.get(s.subsystem) or {}
                    prof = self._real_profile(mapper.analyse(
                        s, subsystem_index=ser.get("index"),
                        subsystem_load=ser.get("load"), det=det))
                    type(self)._profiles[s.sub_id] = prof
                profiles.append(prof)
                rows.append(prof.row())
        else:
            rows = [dict(s.to_dict()) for s in page]

        return {
            "total": total,
            "returned": len(rows),
            "offset": offset,
            "limit": limit,
            "frontier_only": frontier_only,
            "filters": {"uf": uf, "subsystem": subsystem},
            "ufs": reg.ufs(),
            "subsystems": sorted({s.subsystem for s in reg.items if s.subsystem}),
            "rows": rows,
            "summary": mapper.aggregate(profiles) if profiles else {},
            "registry_report": reg.report,
            "registry_mode": reg.mode,
            "pipeline": [
                "subestação georreferenciada (ONS · conjunto `subestacao`)",
                "SEDs da BDGD associadas à SE de fronteira (correlação T–D)",
                "energia faturada por classe (BDGD MT/AT + SAMP BT) → "
                "composição por classe de consumo",
                "cadastro de MMGD da ANEEL nas SEDs ÷ carga média da SE, "
                "relativo ao SIN → nível de penetração",
                "curva de carga do subsistema (ONS) → prior regional e desvio",
                "visão computacional: só amostra sintética de demonstração do "
                "detector (não entra nos números)",
            ],
            "penetration_rel_bins": [
                {"level": n, "from_rel": lo, "to_rel": None if hi == float("inf") else hi}
                for n, lo, hi in mapper.PENETRATION_REL_BINS],
            "sin_mmgd_ratio": round(self._sin_mmgd_ratio(), 4) if analyse else None,
            "penetration_bins": [
                {"level": n, "from_kwp_km2": lo,
                 "to_kwp_km2": None if hi == float("inf") else hi}
                for n, lo, hi in mapper.PENETRATION_BINS],
            "built_up_fraction": mapper.BUILT_UP_FRACTION,
            "analysis_gsd_m": mapper.ANALYSIS_GSD_M,
            "samples_per_substation": mapper.SAMPLES_PER_SUBSTATION,
        }

    # ------------------------------------------------------------ detalhe
    def substation_detail_payload(self, sub_id: str) -> dict:
        reg = self.registry_ensure()
        sub = reg.by_id(sub_id)
        if sub is None:
            raise LookupError("subestação não encontrada: %s" % sub_id)
        prof = self._profiles.get(sub_id)
        if prof is None:
            series = self._subsystem_series()
            ser = series.get(sub.subsystem) or {}
            prof = self._real_profile(mapper.analyse(
                sub, subsystem_index=ser.get("index"), subsystem_load=ser.get("load")))
            type(self)._profiles[sub_id] = prof
        out = prof.to_dict()
        out["clm"] = mapper.clm_hint(prof)
        out["image_url"] = "/api/mapa/scene/%s.png" % sub_id
        out["canonical"] = C.canonical_payload()
        return out

    def substation_scene_png(self, sub_id: str, *, overlay: bool = True,
                             truth: bool = False, tiles_grid: bool = False,
                             channel: str = "") -> bytes:
        """Ortoimagem da amostra, com as deteccoes desenhadas."""
        reg = self.registry_ensure()
        sub = reg.by_id(sub_id)
        if sub is None:
            raise LookupError("subestação não encontrada: %s" % sub_id)
        key = "%s|%s|%s|%s|%s" % (sub_id, overlay, truth, tiles_grid, channel)
        hit = self._png_cache.get(key)
        if hit is not None:
            return hit
        hint = mapper.urban_hint_for(sub)
        seed = mapper._seed_for(sub)
        scene = T.synth_scene(sub.lat, sub.lon, size_px=mapper.SCENE_PX,
                              gsd_m=mapper.ANALYSIS_GSD_M, urban_class=hint,
                              panel_rate=mapper._panel_rate(sub), seed=seed)
        det = D.build_detector()
        scan = D.scan_scene(scene.rgb, scene.geo, det)
        if channel:
            f = D.ClassicalPanelDetector.features(scene.rgb)
            cmap = {"azul": "teal", "borda": "amber",
                    "luminancia": "crimson"}.get(channel, "teal")
            out = R.feature_png(f[channel_key(channel)], cmap=cmap)
        else:
            out = R.scene_png(
                scene.rgb,
                detections=scan.detections if overlay else None,
                truth_boxes=scene.panel_boxes if truth else None,
                tiles=scan.tiles if tiles_grid else None,
            )
        if len(self._png_cache) > 40:
            type(self)._png_cache.clear()
        type(self)._png_cache[key] = out
        return out

    # ------------------------------------------------------------ visao
    def vision_payload(self, *, refresh: bool = False) -> dict:
        """Banco de ensaio do detector: metricas por classe urbana e semente."""
        if self._bench is not None and not refresh:
            return self._bench
        det = D.ClassicalPanelDetector()
        rows: list[dict] = []
        for urb in BENCH_CLASSES:
            for seed in BENCH_SEEDS:
                scene = T.synth_scene(-22.9, -43.2, size_px=768,
                                      urban_class=urb, panel_rate=0.22,
                                      seed=seed)
                scan = D.scan_scene(scene.rgb, scene.geo, det)
                ev = EV.evaluate_scene(scan, scene)
                m = ev["match"]
                rows.append({
                    "urban_class": urb, "seed": seed,
                    "truth": ev["count"]["truth"], "pred": ev["count"]["pred"],
                    "precision": m["precision"], "recall": m["recall"],
                    "f1": m["f1"], "iou_mean": m["iou_mean"],
                    "mask_iou": ev["mask_iou"],
                    "average_precision": ev["average_precision"],
                    "area_rel_error": (ev["area"] or {}).get("rel_error"),
                    "area_rel_error_raw": (ev["area_raw"] or {}).get("rel_error"),
                    "tiles": scan.to_dict()["tiles"],
                    "raw_count": scan.raw_count,
                    "kept_count": scan.kept_count,
                    "duplicates_removed": scan.raw_count - scan.kept_count,
                    "total_kwp": round(scan.total_kwp(), 2),
                })
        # curva PR da cena de referencia
        ref_scene = T.synth_scene(-22.9, -43.2, size_px=768,
                                  urban_class="misto", panel_rate=0.22, seed=11)
        ref_scan = D.scan_scene(ref_scene.rgb, ref_scene.geo, det)
        ref_eval = EV.evaluate_scene(ref_scan, ref_scene)

        def _agg(key):
            vals = [r[key] for r in rows if r[key] is not None]
            return round(float(np.mean(vals)), 4) if vals else None

        payload = {
            "backends": D.backends_status(),
            "active": D.build_detector().info().to_dict(),
            "rows": rows,
            "aggregate": {
                "precision": _agg("precision"), "recall": _agg("recall"),
                "f1": _agg("f1"), "mask_iou": _agg("mask_iou"),
                "average_precision": _agg("average_precision"),
                "area_rel_error": _agg("area_rel_error"),
                "area_rel_error_raw": _agg("area_rel_error_raw"),
                "scenes": len(rows),
            },
            "pr_curve": ref_eval["pr_curve"],
            "reference": {
                "urban_class": "misto", "seed": 11,
                # georreferencia da cena (centro, GSD, extensao): o mapa OSM da tela de
                # visao sobrepoe a imagem no lugar certo sem estimar pelas deteccoes
                "geo": ref_scene.geo.to_dict(),
                "truth": ref_eval["count"]["truth"],
                "pred": ref_eval["count"]["pred"],
                "detections": ref_scan.to_dict(max_detections=120)["detections"],
                "image_url": "/api/mapa/bench.png",
                "image_truth_url": "/api/mapa/bench.png?truth=1&tiles=1",
                "channel_urls": {
                    "azul": "/api/mapa/bench.png?channel=azul",
                    "borda": "/api/mapa/bench.png?channel=borda",
                    "luminancia": "/api/mapa/bench.png?channel=luminancia",
                },
            },
            "pipeline": [
                "ladrilhamento com sobreposição (256 px, 32 px de sobreposição)",
                "índice espectral de excesso de azul + luminância, suavizados",
                "densidade de borda por Sobel (textura dos módulos)",
                "morfologia binária: fechamento, abertura, preenchimento",
                "componentes conexas + filtro de área, retangularidade e "
                "alongamento",
                "refinamento em duas etapas no índice cru",
                "NMS e deduplicação na costura entre ladrilhos",
                "georreferência: pixel → lat/lon → área em m² → kWp",
            ],
            "area_calibration": {
                "factor": D.AREA_CALIBRATION,
                "source": D.AREA_CALIBRATION_SOURCE,
                "watt_per_m2": D.WATT_PER_M2,
            },
            "yolo_note": (
                "O adaptador YOLOv8-seg está implementado por completo — "
                "letterbox e sua inversa, decodificação das saídas, NMS, "
                "recorte de máscara por protótipos e transformação de "
                "coordenadas — e é testado. O que falta é o runtime: torch e "
                "onnxruntime não podem ser instalados aqui porque o proxy "
                "corporativo bloqueia o PyPI. Enquanto isso, o backend ativo é "
                "o detector clássico, que roda e é medido contra verdade "
                "fundamental."),
            "synthetic_note": (
                "A ortoimagem é sintética e a verdade fundamental é conhecida. "
                "As métricas são medições reais do detector; a imagem é de "
                "demonstração. Em imagem real, esperar degradação."),
        }
        type(self)._bench = payload
        return payload

    def bench_png(self, *, truth: bool = False, tiles_grid: bool = False,
                  channel: str = "", urban_class: str = "misto",
                  seed: int = 11) -> bytes:
        scene = T.synth_scene(-22.9, -43.2, size_px=768,
                              urban_class=urban_class, panel_rate=0.22,
                              seed=seed)
        if channel:
            f = D.ClassicalPanelDetector.features(scene.rgb)
            key = {"azul": "blue_excess", "borda": "edge_density",
                   "luminancia": "luminance"}.get(channel, "blue_excess")
            cmap = {"azul": "teal", "borda": "amber",
                    "luminancia": "crimson"}.get(channel, "teal")
            return R.feature_png(f[key], cmap=cmap)
        det = D.ClassicalPanelDetector()
        scan = D.scan_scene(scene.rgb, scene.geo, det)
        missed = None
        if truth:
            m = EV.match(np.array([d.box for d in scan.detections]).reshape(-1, 4),
                         scene.panel_boxes)
            hit = {j for _, j, _ in m.pairs}
            missed = np.array([b for k, b in enumerate(scene.panel_boxes)
                               if k not in hit]).reshape(-1, 4)
        return R.scene_png(scene.rgb, detections=scan.detections,
                           truth_boxes=scene.panel_boxes if truth else None,
                           tiles=scan.tiles if tiles_grid else None,
                           missed=missed)

    # ------------------------------------------------------------ classes
    def classes_payload(self) -> dict:
        """Perfis MEDIDOS por classe, composicao REAL por subsistema e validacao.

        Tres pecas, todas de dado real (ver oraculo/profiles/medidos.py):
          - forma horaria de cada classe: ANEEL CTR (campanhas de medicao);
          - composicao: energia faturada da base da fronteira T-D (BDGD + SAMP);
          - validacao: curva montada contra a curva de carga GLOBAL do ONS.
        Decisao: compara com a carga GLOBAL, nao a supervisionada. O CTR mede
        CONSUMO; a supervisionada desconta a MMGD e achata o meio-dia, o que
        faria a curva montada "errar" por um efeito que nao e de classe.
        Sem a base da fronteira (em construcao ou modo demo), a composicao
        NAO e estimada por outro caminho: o subsistema sai sem ela e a tela diz
        por que.
        """
        from .service_fronteira import BaseNotReady
        self.ensure()
        # Sem o CTR baixado (maquina nova), a pagina abre com o aviso de como
        # baixar -- nunca com perfis de outra origem no lugar.
        try:
            perfis, aviso_perfis = M.perfis(), None
        except FileNotFoundError as exc:
            perfis, aviso_perfis = None, str(exc)
        comp, cobertura, aviso = {}, {}, None
        if self._fr_demo():
            aviso = ("Modo demonstrativo: a base da fronteira T–D é sintética, "
                     "então a composição real por subsistema não é mostrada.")
        else:
            try:
                r = self._fr()
                comp = M.composicao_subsistemas(r.per_frontier, r.seds)
                cobertura = {c["subsystem"]: c for c in self._fr_ons_coverage(r.per_frontier)}
            except BaseNotReady as exc:
                aviso = "Composição indisponível: %s. Acompanhe em /api/fronteira/status." % exc

        subs = []
        for ss in ("SE", "S", "NE", "N"):
            st = self.areas.get(ss)
            if st is None:
                continue
            carga = st.decomposition.carga_global
            obs, n = C.hourly_shape(st.index, carga, "util")
            item = {
                "subsystem": ss,
                "name": config.SUBSYSTEMS.get(ss, {}).get("name", ss),
                "observed": [round(float(v), 5) for v in obs],
                "weekend_ratio_observed": _r(C.weekend_weekday_ratio(st.index, carga), 3),
                "samples": int(n),
                "composition": None,
            }
            c = comp.get(ss)
            if c is not None and perfis is not None:
                mont = M.montar(c["pesos"], perfis)
                r2 = M.r2(obs, mont["shape"])
                cov = cobertura.get(ss) or {}
                item.update({
                    "composition": c,
                    "dominant": max(c["pesos"], key=c["pesos"].get),
                    "assembled": [round(float(v), 5) for v in mont["shape"]],
                    "weekend_ratio_assembled": _r(mont["weekend_ratio"], 3),
                    "r2": round(r2, 4),
                    "fit_quality": M.qualidade(r2),
                    "coverage": cov.get("ratio"),
                    "coverage_year": cov.get("ano"),
                })
                if cov.get("ratio") is not None and cov["ratio"] < M.cfg()["cobertura_alerta"]:
                    item["fit_warning"] = (
                        "A distribuição (BDGD + SAMP) cobre só %.0f%% da energia do "
                        "ONS neste subsistema. O resto — consumidores ligados direto "
                        "na rede básica (eletrointensivos), perdas — não está na "
                        "composição, e costuma ser carga plana: a curva montada "
                        "sai mais ondulada que a observada." % (100 * cov["ratio"]))
            subs.append(item)

        return {
            "measured": M.payload_perfis() if perfis is not None else None,
            "measured_warning": aviso_perfis,
            "subsystems": subs,
            "composition_warning": aviso,
            # limiares de telhado da evidencia morfologica do Mapa: PREMISSA,
            # continuam em classes.py e sao rotulados como tal na tela
            "footprint_thresholds_m2": C.canonical_payload()["footprint_thresholds_m2"],
            "note": (
                "Formas horárias medidas pela ANEEL (CTR, campanhas das revisões "
                "tarifárias) e composição pela energia faturada real (BDGD + SAMP). "
                "A curva de carga global do ONS entra só como validação da "
                "composição × forma."),
        }

    def classes_provenance(self) -> list[dict]:
        """ONS (validacao) + ANEEL/IBGE da fronteira (composicao) + ANEEL CTR (forma)."""
        out = list(self.provenance())
        if not self._fr_demo():
            out += self.fronteira_provenance()
        return out + ([M.proveniencia()] if M.caminho_saida().exists() else [])
