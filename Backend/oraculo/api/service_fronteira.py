# -*- coding: utf-8 -*-
"""Fachada da correlacao fronteira T-D: SED (ANEEL) x SE de fronteira (ONS).

Mixin proprio, pelo mesmo motivo dos anteriores (decisao D7): acrescentar a
secao nao altera nada que ja funciona.

A base agregada custa ~1 min para construir na primeira vez. A construcao
roda numa thread e publica o progresso por etapa; a interface consulta
`/api/fronteira/status` e so pede os paineis quando a base esta pronta. Com
base em cache, a resposta e imediata -- e, se o cache estiver velho, a
reconstrucao roda por tras sem tirar a tela do ar.
"""
from __future__ import annotations

import threading
import time

import numpy as np

from .. import config
from ..fronteira import base as B
from ..fronteira import correlacao as C
from ..fronteira.fontes import CLASSES

_LOCK = threading.Lock()


class BaseNotReady(RuntimeError):
    """A base ainda esta sendo construida."""


class FronteiraMixin:
    """Estado da secao Fronteira T-D."""

    _fr_base: dict | None = None
    _fr_result: C.Resultado | None = None
    _fr_key: tuple | None = None
    _fr_sens: tuple | None = None          # (chave, varredura)
    _fr_job: dict = {"state": "idle", "stage": "", "progress": 0.0,
                     "error": "", "started": 0.0}

    # ------------------------------------------------------------ base
    def _fr_demo(self) -> bool:
        # `mode()` responde "demo" enquanto o bundle do ONS nao foi carregado:
        # sem o `ensure`, a secao cairia no modo demonstrativo por engano.
        self.ensure()
        return self.mode() == "demo" or config.FORCE_OFFLINE

    def fronteira_status(self) -> dict:
        self._fr_ensure_started()
        job = dict(type(self)._fr_job)
        b = type(self)._fr_base
        stages = [{"key": k, "label": lbl} for k, lbl in B.STAGES]
        keys = [k for k, _ in B.STAGES]
        if job["state"] == "building" and job["stage"] in keys:
            i = keys.index(job["stage"])
            job["overall"] = round((i + job["progress"]) / len(keys), 3)
        return {
            "state": ("ready" if b is not None and job["state"] != "building"
                      else job["state"]),
            "rebuilding": job["state"] == "building" and b is not None,
            "stage": job["stage"], "progress": round(job["progress"], 3),
            "overall": job.get("overall", 1.0 if b else 0.0),
            "error": job["error"], "stages": stages,
            "base_mode": (b or {}).get("mode"),
            "built_at": (b or {}).get("built_at"),
            "build_seconds": (b or {}).get("build_seconds"),
            "elapsed_s": round(time.time() - job["started"], 1)
                         if job["state"] == "building" else None,
            "ttl_days": round(config.FRONTEIRA_TTL_SECONDS / 86400, 1),
        }

    def _fr_ensure_started(self, *, force: bool = False) -> None:
        """Carrega a base do cache ou dispara a construcao, sem bloquear."""
        cls = type(self)
        with _LOCK:
            if cls._fr_job["state"] == "building":
                return
            if self._fr_demo():
                if cls._fr_base is None or cls._fr_base.get("mode") != "demo":
                    frontier = self.registry_ensure().frontier()
                    cls._fr_base = B.demo_base(frontier)
                    cls._fr_result = None
                return
            if cls._fr_base is None or cls._fr_base.get("mode") == "demo":
                cached = B.load_cached()
                if cached is not None:
                    cached["mode"] = "cache"
                    cls._fr_base = cached
                    cls._fr_result = None
                elif cls._fr_base is not None:
                    cls._fr_base = None
            stale = not B.is_fresh(cls._fr_base)
            if not (force or cls._fr_base is None or stale):
                return
            if cls._fr_job["state"] == "error" and not force:
                return                    # nao insiste sozinho numa falha
            cls._fr_job = {"state": "building", "stage": B.STAGES[0][0],
                           "progress": 0.0, "error": "",
                           "started": time.time()}
        threading.Thread(target=self._fr_build, daemon=True,
                         name="fronteira-build").start()

    def _fr_build(self) -> None:
        cls = type(self)

        def prog(stage: str, frac: float) -> None:
            cls._fr_job["stage"] = stage
            cls._fr_job["progress"] = float(frac)

        try:
            b = B.build(progress=prog)
            with _LOCK:
                cls._fr_base = b
                cls._fr_result = None
                cls._fr_job = {"state": "ready", "stage": "", "progress": 1.0,
                               "error": "", "started": 0.0}
        except Exception as exc:  # rede, proxy, formato
            with _LOCK:
                cls._fr_job = {"state": "error",
                               "stage": cls._fr_job.get("stage", ""),
                               "progress": 0.0, "error": str(exc)[:300],
                               "started": 0.0}

    def fronteira_rebuild(self) -> dict:
        if self._fr_demo():
            raise ValueError("modo demonstrativo: não há o que reconstruir")
        type(self)._fr_job["state"] = "idle"
        self._fr_ensure_started(force=True)
        return self.fronteira_status()

    def _fr(self) -> C.Resultado:
        self._fr_ensure_started()
        cls = type(self)
        b = cls._fr_base
        if b is None:
            job = cls._fr_job
            if job["state"] == "error":
                raise BaseNotReady("falha ao construir a base: %s" % job["error"])
            raise BaseNotReady("base da fronteira T–D em construção")
        reg = self.registry_ensure()
        key = (id(b), id(reg), tuple(sorted((k, str(v)) for k, v in
                                            config.FRONTEIRA.items())))
        if cls._fr_result is None or cls._fr_key != key:
            cls._fr_result = C.correlate(b, reg.frontier())
            cls._fr_key = key
        return cls._fr_result

    def fronteira_mode(self) -> str:
        b = type(self)._fr_base
        return (b or {}).get("mode") or ("demo" if self._fr_demo() else "cache")

    def fronteira_provenance(self) -> list[dict]:
        b = type(self)._fr_base or {}
        reg = type(self)._registry
        out = list(b.get("provenance") or [])
        if reg is not None:
            out += reg.provenance_dicts()
        return out

    def fronteira_notes(self) -> list[str]:
        notes = [
            "A associação SED → SE de fronteira é INFERIDA por modelo "
            "gravitacional: nenhuma base pública traz a topologia de "
            "subtransmissão. Cada vínculo sai com probabilidade e alternativas.",
            "A BDGD publica só unidades consumidoras de pessoa jurídica em "
            "média e alta tensão. A baixa tensão vem do SAMP, rateada por "
            "população municipal.",
        ]
        if self.fronteira_mode() == "demo":
            notes.insert(0, "%s — correlação sobre base sintética, sem "
                            "correspondência com a rede real."
                         % config.DEMO_BANNER)
        return notes

    # ------------------------------------------------------------ resumo
    def fronteira_summary_payload(self, *, uf: str = "", subsystem: str = "",
                                  order: str = "energia") -> dict:
        r = self._fr()
        per = r.per_frontier
        if uf:
            per = [f for f in per if f["uf"] == uf]
        if subsystem:
            per = [f for f in per if f["subsystem"] == subsystem]
        keyf = {"energia": lambda f: -f["e_total_gwh"],
                "gd": lambda f: -(f["gd_penetration"] or 0.0),
                "carregamento": lambda f: -(f["loading"] or 0.0),
                "ambiguidade": lambda f: -(f["ambiguous_share"] or 0.0),
                "nome": lambda f: f["name"]}.get(order, lambda f: -f["e_total_gwh"])
        per = sorted(per, key=keyf)
        idx = {f["idx"] for f in per}

        rows = [_row(f) for f in per]
        seds_map = [{"lat": s["lat"], "lon": s["lon"], "f": lk.idx,
                     "p": round(lk.p, 2),
                     "e": round(sum(s["e_class"].values()) / 1e6, 2)}
                    for s, lk in zip(r.seds, r.links)
                    if (lk.idx in idx) or (lk.idx < 0 and (not uf or s["uf"] == uf))]
        tot_e = sum(f["e_total_gwh"] for f in per)
        tot_gd = sum(f["gd_kw"] for f in per)
        w = {c: sum(f["e_class_kwh"][c] for f in per) for c in CLASSES}
        tw = sum(w.values())
        return {
            "filters": {"uf": uf, "subsystem": subsystem, "order": order},
            "ufs": sorted({f["uf"] for f in r.per_frontier if f["uf"]}),
            "subsystems": sorted({f["subsystem"] for f in r.per_frontier
                                  if f["subsystem"]}),
            "kpis": {
                "frontier": len(per),
                "frontier_with_sed": sum(1 for f in per if f["n_sed"]),
                "seds": sum(f["n_sed"] for f in per),
                "energy_twh": round(tot_e / 1000.0, 2),
                "measured_share": round(sum(f["e_mtat_gwh"] for f in per) / tot_e, 4)
                                  if tot_e else None,
                "gd_mw": round(tot_gd / 1000.0, 1),
                "gd_direct_share": round(sum(f["gd_kw_direct"] for f in per) / tot_gd, 4)
                                   if tot_gd else None,
                "weights": {c: round(v / tw, 4) for c, v in w.items()} if tw else {},
                "ambiguous_rate": r.report["seds_ambiguous"] / r.report["seds_associated"]
                                  if r.report["seds_associated"] else None,
                "median_distance_km": (r.report["distance_km"] or {}).get("p50"),
            },
            "rows": rows,
            "map": {"frontier": [{"i": f["idx"], "id": f["sub_id"], "name": f["name"],
                                  "lat": f["lat"], "lon": f["lon"],
                                  "mva": f["frontier_mva"], "n": f["n_sed"],
                                  "e": f["e_total_gwh"], "load": f["loading"]}
                                 for f in per],
                    "seds": seds_map},
            "report": r.report,
            "premises": _premises(),
            "pipeline": [
                "SE de fronteira da rede básica (ONS · `subestacao` + "
                "`capacidade-transformacao`, secundário ≤ 138 kV)",
                "SED reconstruída das UCs de média e alta tensão que ela atende "
                "(ANEEL · BDGD UCMT/UCAT: código SUB, classe, 12 meses de "
                "energia e demanda, coordenada)",
                "distribuidora da SED identificada pelo município (voto "
                "ponderado no cadastro de GD)",
                "associação SED → SE de fronteira por modelo gravitacional, "
                "com probabilidade e alternativas",
                "baixa tensão: SAMP da distribuidora → municípios pela "
                "população (IBGE) → SEDs pelas UCs atendidas",
                "MMGD: vínculo direto pelo CEG_GD da UC; o restante, pelo "
                "município",
                "agregado por SE de fronteira → composição de carga e "
                "penetração de MMGD para o Modelo de Carga Composta",
            ],
        }

    # ------------------------------------------------------------ detalhe
    def fronteira_detail_payload(self, sub_id: str, *,
                                 compare: bool = True) -> dict:
        r = self._fr()
        f = next((x for x in r.per_frontier if x["sub_id"] == sub_id), None)
        if f is None:
            raise LookupError("SE de fronteira não encontrada: %s" % sub_id)
        names = {x["idx"]: x["name"] for x in r.per_frontier}
        seds = []
        for i in f["sed_idx"]:
            s, lk = r.seds[i], r.links[i]
            di = r.dist.get(s["dist"]) or {}
            e = sum(s["e_class"].values())
            cls = max(s["e_class"].items(), key=lambda kv: kv[1])[0] if e else ""
            seds.append({
                "key": s["key"], "sub": s["sub"], "dist": s["dist"],
                "distribuidora": di.get("sigla") or s["dist"],
                "dist_confidence": di.get("confianca"),
                "lat": s["lat"], "lon": s["lon"], "uf": s["uf"],
                "n_uc": s["n_mt"] + s["n_at"], "n_at": s["n_at"],
                "e_gwh": round(e / 1e6, 3), "dem_mw": round(s["dem_kw"] / 1000, 2),
                "dominant": cls, "spread_km": s["spread_km"],
                "d_km": round(lk.d_km, 1), "p": round(lk.p, 3),
                "ambiguous": lk.ambiguous, "same_uf": lk.same_uf,
                "agent_match": lk.agent_match, "candidates": lk.candidates,
                "n_ceg": s.get("n_ceg", 0),
                "gd_kw_direct": round(((type(self)._fr_base or {}).get("sed_gd")
                                       or {}).get(s["key"], {}).get("kw", 0.0), 1),
                "alternatives": [{"name": names.get(j, "?"), "p": round(p, 3),
                                  "d_km": round(d, 1)} for j, p, d in lk.alternatives],
            })
        seds.sort(key=lambda x: -x["e_gwh"])
        out = dict(f)
        out.pop("sed_idx", None)
        out["seds"] = seds
        out["clm"] = self._fr_clm_hint(f)
        out["comparison"] = self._fr_compare(sub_id, f) if compare else None
        out["months"] = ["jan", "fev", "mar", "abr", "mai", "jun", "jul",
                         "ago", "set", "out", "nov", "dez"]
        return out

    def _fr_clm_hint(self, f: dict) -> dict:
        from ..substations import mapper
        w = f["weights"]
        return {
            "composicao_classe": w,
            "fracao_motor_estimada": mapper.motor_fraction(w),
            "fracao_motor_premissas": dict(mapper.MOTOR_FRACTION),
            "mmgd_kw_instalada": f["gd_kw"],
            "mmgd_penetracao": f["gd_penetration"],
            "pdg_mw_meio_dia": round(f["gd_kw"] / 1000.0 * config.MMGD_PERFORMANCE_RATIO, 2),
            "carga_media_mw": f["mw_avg"],
            "parcela_medida": f["measured_share"],
            "fonte": "BDGD (UCMT/UCAT) + SAMP + cadastro de MMGD da ANEEL",
            "aviso": ("A composição vem de energia faturada real (média e alta "
                      "tensão por UC; baixa tensão por distribuidora, rateada). "
                      "Pdg ao meio-dia usa o performance ratio agregado de %.2f "
                      "sobre a potência instalada: é teto de céu claro, não "
                      "despacho." % config.MMGD_PERFORMANCE_RATIO),
        }

    def _fr_compare(self, sub_id: str, f: dict) -> dict | None:
        """Mesma SE, duas representacoes: Mapa Inteligente x BDGD/ANEEL."""
        try:
            d = self.substation_detail_payload(sub_id)
        except Exception:
            return None
        lc = d.get("load_class") or {}
        mm = d.get("mmgd") or {}
        wm = lc.get("weights") or {}
        wb = f["weights"]
        diff = {c: round(wb.get(c, 0.0) - wm.get(c, 0.0), 4) for c in CLASSES}
        return {
            "mapa": {"weights": wm, "dominant": lc.get("dominant"),
                     "confidence": lc.get("confidence"),
                     "mmgd_kw": mm.get("kwp_total"), "mmgd_level": mm.get("level"),
                     "method": "morfologia de ortoimagem sintética + prior "
                               "regional do subsistema"},
            "bdgd": {"weights": wb, "dominant": f["dominant"],
                     "measured_share": f["measured_share"],
                     "mmgd_kw": f["gd_kw"],
                     "method": "energia faturada por classe (BDGD + SAMP) e "
                               "cadastro de MMGD (ANEEL)"},
            "diff": diff,
            "l1": round(sum(abs(v) for v in diff.values()) / 2.0, 4),
            "mmgd_ratio": round(f["gd_kw"] / mm["kwp_total"], 3)
                          if mm.get("kwp_total") else None,
        }

    # ------------------------------------------------------------ qualidade
    def fronteira_quality_payload(self) -> dict:
        r = self._fr()
        per = r.per_frontier
        dists = [lk.d_km for lk in r.links if lk.idx >= 0]
        probs = [lk.p for lk in r.links if lk.idx >= 0]
        loads = [f["loading"] for f in per if f["e_total_gwh"] > 0]
        flagged = sorted([_row(f) for f in per if f["loading_flag"]
                          and f["loading_flag"] != "sem carga associada"],
                         key=lambda x: -(x["loading"] or 0))
        return {
            "report": r.report,
            "hist_distance": C.histogram(dists, [0, 5, 10, 20, 30, 50, 75, 100, 150]),
            "hist_probability": C.histogram(probs, [0, .2, .3, .4, .5, .6, .7, .8, .9, 1.0001]),
            "hist_loading": C.histogram(loads, [0, .05, .1, .15, .2, .3, .4, .6, 1.0, 5.0]),
            "ons_coverage": self._fr_ons_coverage(per),
            "sensitivity": self._fr_sensitivity(),
            "flagged": flagged[:40],
            "no_load": [_row(f) for f in per if f["e_total_gwh"] <= 0][:60],
            "premises": _premises(),
            "privacy": [
                "Cadastro de GD: CPF/CNPJ e nome do titular não são lidos.",
                "BDGD: endereço, CEP e CNAE da UC não são lidos.",
                "Arquivo bruto baixado em diretório temporário e apagado após "
                "a agregação. O cache guarda só agregados por SED, município e "
                "distribuidora.",
            ],
            "limits": [
                "A topologia de subtransmissão (qual SED é alimentada por qual "
                "SE) não é dado público: a associação é inferida e deve ser "
                "confirmada com o cadastro da distribuidora ou o SIGA/ONS.",
                "A posição da SED é a mediana das UCs de média e alta tensão "
                "que ela atende, não a coordenada do barramento.",
                "A BDGD aberta traz só pessoa jurídica. A baixa tensão "
                "residencial é rateada por população, não medida por SED.",
                "Carregamento é energia média sobre MVA nominal (FP 0,92): "
                "indicador de consistência, não de carregamento de ponta.",
            ],
        }

    def _fr_sensitivity(self) -> list[dict]:
        """Varredura alfa x lambda. Nove correlacoes: guardada por base."""
        cls = type(self)
        key = cls._fr_key
        if cls._fr_sens is None or cls._fr_sens[0] != key:
            reg = self.registry_ensure()
            cls._fr_sens = (key, C.sensitivity(cls._fr_base, reg.frontier()))
        return cls._fr_sens[1]

    def _fr_ons_coverage(self, per: list[dict]) -> list[dict]:
        """Energia alocada x carga verificada do ONS, por subsistema.

        E a validacao externa: nenhuma das bases da ANEEL foi usada para
        calcular a carga do ONS, e vice-versa. A razao fica abaixo de 1 por
        construcao -- perdas tecnicas e comerciais, autoconsumo da MMGD e
        carga ligada direto na rede basica nao aparecem no faturamento.
        """
        try:
            self.ensure()
        except Exception:
            return []
        ano = config.FRONTEIRA["samp_ano"]
        out = []
        for ss in ("SE", "S", "NE", "N"):
            st = self.areas.get(ss)
            alloc = sum(f["e_total_gwh"] for f in per if f["subsystem"] == ss)
            ons = None
            hours = 0
            if st is not None:
                years = st.index.astype("datetime64[Y]").astype(int) + 1970
                load = st.series.get("carga_supervisionada")
                m = (years == ano) & np.isfinite(load)
                hours = int(m.sum())
                if hours > 0:
                    # extrapola lacunas para o ano cheio, declarando as horas
                    ons = float(load[m].mean()) * C.HOURS_YEAR / 1000.0
            out.append({
                "subsystem": ss,
                "name": config.SUBSYSTEMS.get(ss, {}).get("name", ss),
                "allocated_gwh": round(alloc, 1),
                "ons_gwh": round(ons, 1) if ons else None,
                "ratio": round(alloc / ons, 4) if ons else None,
                "ons_hours": hours,
                "ano": ano,
            })
        return out

    # ------------------------------------------------------------ CLM
    def fronteira_clm_context(self, sub_id: str) -> dict:
        """O que o cartao CLM precisa, a partir da base BDGD/ANEEL."""
        d = self.fronteira_detail_payload(sub_id, compare=False)
        return {"name": d["name"], "uf": d["uf"], "subsystem": d["subsystem"],
                "frontier_mva": d["frontier_mva"],
                "secondary_kv": d["secondary_kv"], "weights": d["weights"],
                "gd_kw": d["gd_kw"], "measured_share": d["measured_share"],
                "clm": d["clm"], "n_sed": d["n_sed"]}


def _row(f: dict) -> dict:
    return {k: f[k] for k in (
        "sub_id", "name", "uf", "subsystem", "agent", "voltage_kv",
        "secondary_kv", "frontier_mva", "n_sed", "n_uc", "e_total_gwh",
        "e_mtat_gwh", "e_bt_gwh", "measured_share", "weights", "dominant",
        "mw_avg", "loading", "loading_flag", "ambiguous_share", "gd_kw",
        "gd_kw_direct", "gd_direct_share", "gd_penetration", "pop_served")}


def _premises() -> list[dict]:
    P = config.FRONTEIRA
    return [
        {"k": "Raio máximo de busca", "v": "%.0f km" % P["raio_max_km"]},
        {"k": "Escala de decaimento (λ)", "v": "%.0f km" % P["lambda_km"]},
        {"k": "Expoente da capacidade (α)", "v": "MVA^%.2g" % P["expoente_mva"]},
        {"k": "Bônus mesma UF", "v": "×%.1f" % P["bonus_uf"]},
        {"k": "Bônus mesmo grupo econômico", "v": "×%.1f" % P["bonus_agente"]},
        {"k": "Limiar de associação ambígua", "v": "p < %.2f" % P["limiar_ambiguo"]},
        {"k": "Faixa de carregamento plausível",
         "v": "%.0f%% a %.0f%%" % tuple(100 * x for x in P["carregamento_faixa"])},
        {"k": "SAMP", "v": "%d · Energia TUSD · BT · mercados Regular" % P["samp_ano"]},
        {"k": "Classes → CLM",
         "v": "poder, serviço e iluminação públicos → comercial"},
    ]
