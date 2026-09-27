# -*- coding: utf-8 -*-
"""Mapa Inteligente de Perfis de Carga e Geracao Distribuida.

Responde, para cada subestacao georreferenciada, as duas perguntas do desafio:

  1. Qual e o perfil predominante de consumo da area atendida?
     Residencial, comercial, industrial ou misto, com percentual.

  2. Existe presenca relevante de geracao distribuida no entorno?
     Baixa, media ou alta penetracao de MMGD em telhados.

Pipeline, replicavel a cada atualizacao das bases:

    subestacao georreferenciada (ONS, real)
        -> area de influencia dimensionada pela capacidade de fronteira
        -> ortoimagem da area (sintetica no prototipo)
        -> deteccao de paineis por visao computacional
        -> kWp por km2  ->  indicador de penetracao de MMGD
        -> morfologia construida  +  perfil de carga do subsistema (ONS, real)
        -> composicao por classe de consumo, por NNLS
        -> registro com proveniencia e confianca
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..profiles import classes as C
from ..vision import detector as D
from ..vision import evaluate as EV
from ..vision import tiles as T
from .registry import Substation

# Limiares de penetracao de MMGD, em kWp por km2 de area analisada.
# Premissa de negocio, versionada: o desafio pede o indicador em tres niveis.
# Ancoragem: uma unidade com MMGD tem tipicamente 5 kWp; a densidade
# construida urbana fica entre 800 e 2.000 telhados por km2; a penetracao
# media brasileira e da ordem de 3% das unidades consumidoras, chegando a
# 8-10% nos municipios mais avancados. Isso coloca a faixa urbana tipica
# entre 150 e 900 kWp/km2, e e onde os limiares precisam cortar.
PENETRATION_BINS = [
    ("baixa", 0.0, 200.0),
    ("média", 200.0, 800.0),
    ("alta", 800.0, float("inf")),
]
PENETRATION_LABELS = {
    "baixa": "Baixa penetração de MMGD",
    "média": "Média penetração de MMGD",
    "alta": "Alta penetração de MMGD",
}

# Tamanho da ortoimagem analisada por subestacao, em pixels.
SCENE_PX = 768
# Resolucao de analise, fixa. NAO se estica o GSD para cobrir a area de
# influencia inteira: com raio de 6 km em 768 px o pixel teria 15 m e
# nenhum painel seria detectavel. Em vez disso a deteccao roda numa
# AMOSTRA da area, em resolucao real, e a densidade medida (kWp/km2) e
# extrapolada para a area de influencia. E como se faz na pratica:
# ortoimagem de 30 cm sobre 113 km2 por subestacao e inviavel.
ANALYSIS_GSD_M = 0.30
# Numero de janelas amostradas por subestacao.
SAMPLES_PER_SUBSTATION = 2

# Fracao efetivamente construida da area de influencia, por morfologia. A
# amostra e urbana por construcao; a area de influencia inteira nao e. Sem esse
# desconto, extrapolar a densidade da amostra para 113 km2 superestima o total
# por um fator grande. E premissa de negocio, declarada no payload.
BUILT_UP_FRACTION = {
    "comercial": 0.80,
    "residencial": 0.60,
    "industrial": 0.40,
    "misto": 0.55,
}


def penetration_class(kwp_per_km2: float) -> str:
    for name, lo, hi in PENETRATION_BINS:
        if lo <= kwp_per_km2 < hi:
            return name
    return "alta"


@dataclass
class SubstationProfile:
    """Saida do Mapa Inteligente para uma subestacao."""

    substation: Substation
    load_class: dict                      # composicao fundida
    mmgd: dict                            # indicador de penetracao
    vision: dict                          # resumo da deteccao
    evaluation: dict = field(default_factory=dict)
    scene_seed: int = 0
    urban_hint: str = "misto"
    notes: list[str] = field(default_factory=list)

    def to_dict(self, *, with_vision: bool = True) -> dict:
        out = {
            "substation": self.substation.to_dict(),
            "load_class": self.load_class,
            "mmgd": self.mmgd,
            "scene_seed": self.scene_seed,
            "urban_hint": self.urban_hint,
            "notes": self.notes,
        }
        if with_vision:
            out["vision"] = self.vision
            out["evaluation"] = self.evaluation
        else:
            out["vision"] = {
                "detector": self.vision.get("detector", {}).get("kind"),
                "kept_count": self.vision.get("kept_count"),
                "total_kwp": self.vision.get("total_kwp"),
            }
        return out

    def row(self) -> dict:
        """Linha compacta para a tabela do mapa."""
        s = self.substation
        return {
            "sub_id": s.sub_id, "name": s.name, "uf": s.uf,
            "subsystem": s.subsystem, "lat": round(s.lat, 6),
            "lon": round(s.lon, 6),
            "voltage_kv": round(s.voltage_kv, 1),
            "secondary_kv": round(s.secondary_kv_min, 1),
            "frontier_mva": round(s.frontier_mva, 1),
            "radius_km": round(s.radius_km, 2),
            "area_km2": round(s.area_km2, 2),
            "class_label": self.load_class.get("label"),
            "class_dominant": self.load_class.get("dominant"),
            "class_weights": self.load_class.get("weights"),
            "class_confidence": self.load_class.get("confidence"),
            "deviation_from_regional": self.load_class.get(
                "deviation_from_regional"),
            "mmgd_level": self.mmgd.get("level"),
            "mmgd_kwp": self.mmgd.get("kwp_total"),
            "mmgd_kwp_per_km2": self.mmgd.get("kwp_per_km2"),
            "mmgd_panels": self.mmgd.get("panels"),
            "mmgd_confidence": self.mmgd.get("confidence"),
            "mmgd_relative_to_sin": self.mmgd.get("relative_to_sin"),
            "real": bool(self.load_class.get("real")),
            "tipo3_mw": round(s.tipo3_mw, 1),
        }


# ------------------------------------------------------ dica de morfologia
# Agentes que sao distribuidoras: a presenca de uma delas como agente principal
# indica que a subestacao entrega carga, nao apenas interliga transmissao.
DISTRIBUTION_AGENT_HINTS = (
    "ENEL", "LIGHT", "CPFL", "ENERGISA", "NEOENERGIA", "COELBA", "CELPE",
    "COSERN", "CEMIG", "COPEL", "CELESC", "RGE", "EQUATORIAL", "CEEE",
    "ELEKTRO", "EDP", "AMAZONAS ENERGIA", "CEA", "RORAIMA", "SULGIPE",
    "CERON", "ELETROACRE", "CEB", "CELG", "ESCELSA", "BANDEIRANTE",
)


def is_distribution_agent(agent: str) -> bool:
    a = (agent or "").upper()
    return any(h in a for h in DISTRIBUTION_AGENT_HINTS)


def urban_hint_for(sub: Substation) -> str:
    """Morfologia urbana esperada, a partir de atributos REAIS e independentes.

    ATENCAO METODOLOGICA: a versao anterior usava densidade de carga
    (MVA/km2) — o que era circular, porque o raio da area de influencia e
    calculado A PARTIR do MVA, tornando a densidade constante por construcao.
    Os sinais usados agora sao independentes entre si e vindos do cadastro:

      * tensao secundaria — 13,8 ou 34,5 kV entrega direto na distribuicao
        (area urbana atendida); 69 ou 138 kV alimenta outras subestacoes
        (no de subtransmissao regional, perfil mais misto);
      * capacidade de fronteira — quanto de carga a area efetivamente puxa;
      * agente principal — distribuidora indica entrega de carga.

    LIMITE DECLARADO: discriminar INDUSTRIAL com seguranca exige base de
    classe de consumo (BDGD ou a Pesquisa de Posse e Habitos do IBGE). No
    prototipo, o industrial e identificado apenas pela morfologia da amostra
    (galpoes de grande area), nunca por este indicador cadastral.
    """
    sec = sub.secondary_kv_min
    mva = sub.frontier_mva if sub.frontier_mva > 0 else sub.capacity_mva
    dist_agent = is_distribution_agent(sub.agent)

    if sec <= 0 or mva <= 0:
        return "misto"

    if sec <= 34.5:                       # entrega direta na distribuicao
        if mva >= 500.0:
            return "comercial"            # centro urbano denso
        if mva >= 120.0:
            return "misto"
        return "residencial"              # bairro

    if sec <= 69.0:                        # subtransmissao proxima da carga
        if mva >= 700.0:
            return "comercial"
        return "residencial" if dist_agent else "misto"

    # 138 kV: no regional, alimenta varias subestacoes. NAO se afirma
    # industrial aqui: sem base de classe de consumo (BDGD ou IBGE PPH) esse
    # rotulo nao se sustenta no cadastro. O industrial aparece, quando aparece,
    # pela morfologia da amostra -- galpoes de grande area.
    return "misto"


def _seed_for(sub: Substation) -> int:
    """Semente estavel por subestacao: a cena e reprodutivel."""
    h = 0
    for ch in (sub.sub_id + "|" + sub.uf):
        h = (h * 131 + ord(ch)) % 2_147_483_647
    return h


# ------------------------------------------------------ analise
def analyse(sub: Substation, *, subsystem_index: np.ndarray | None = None,
            subsystem_load: np.ndarray | None = None,
            det: D.Detector | None = None,
            scene_px: int = SCENE_PX,
            with_evaluation: bool = True) -> SubstationProfile:
    """Executa o pipeline completo para uma subestacao."""
    det = det or D.build_detector()
    hint = urban_hint_for(sub)
    seed = _seed_for(sub)

    # A deteccao roda em amostras de resolucao real, dentro da area de
    # influencia. A cena principal (amostra 0) fica centrada na subestacao.
    scene = T.synth_scene(sub.lat, sub.lon, size_px=scene_px,
                          gsd_m=ANALYSIS_GSD_M, urban_class=hint,
                          panel_rate=_panel_rate(sub), seed=seed)
    scan = D.scan_scene(scene.rgb, scene.geo, det)
    vision = scan.to_dict(max_detections=250)
    evaluation = EV.evaluate_scene(scan, scene) if with_evaluation else {}

    # Amostras adicionais deslocadas, para reduzir a variancia da densidade
    # estimada sem multiplicar o custo.
    sample_scans = [scan]
    sample_scenes = [scene]
    for k in range(1, max(1, SAMPLES_PER_SUBSTATION)):
        off_km = sub.radius_km * 0.55
        ang = 2.0 * np.pi * k / max(1, SAMPLES_PER_SUBSTATION)
        dlat = (off_km * np.cos(ang)) / 111.0
        dlon = (off_km * np.sin(ang)) / (111.0 * np.cos(np.deg2rad(sub.lat)))
        sc2 = T.synth_scene(sub.lat + dlat, sub.lon + dlon, size_px=scene_px,
                            gsd_m=ANALYSIS_GSD_M, urban_class=hint,
                            panel_rate=_panel_rate(sub), seed=seed + 1000 * k)
        sample_scans.append(D.scan_scene(sc2.rgb, sc2.geo, det))
        sample_scenes.append(sc2)

    # ---- indicador de MMGD: densidade medida na amostra, extrapolada
    sample_km2 = sum(s.geo.extent_m[0] * s.geo.extent_m[1] / 1e6
                     for s in sample_scenes)
    kwp_sample = sum(s.total_kwp() for s in sample_scans)
    panels_sample = sum(s.kept_count for s in sample_scans)
    area_sample_m2 = sum(s.total_area_m2() for s in sample_scans)
    kwp_km2 = kwp_sample / sample_km2 if sample_km2 > 0 else 0.0
    level = penetration_class(kwp_km2)
    roof_count = sum(int(len(s.roof_boxes)) for s in sample_scenes)
    built = BUILT_UP_FRACTION.get(hint, 0.55)
    kwp_extrapolated = kwp_km2 * sub.area_km2 * built
    mmgd = {
        "level": level,
        "label": PENETRATION_LABELS[level],
        "kwp_per_km2": round(kwp_km2, 1),
        "kwp_sample": round(kwp_sample, 2),
        "kwp_total": round(kwp_extrapolated, 1),
        "panels": int(panels_sample),
        "panel_area_m2": round(area_sample_m2, 1),
        "roofs_detected": roof_count,
        "roof_penetration": round(panels_sample / roof_count, 4)
                            if roof_count else None,
        "sample_km2": round(sample_km2, 4),
        "samples": len(sample_scenes),
        "area_km2": round(sub.area_km2, 2),
        "extrapolation_factor": round(sub.area_km2 / sample_km2, 1)
                                if sample_km2 > 0 else None,
        "built_up_fraction": built,
        "sample_adequacy": ("boa" if roof_count >= 60 and panels_sample >= 4
                            else "limitada" if roof_count >= 20
                            else "insuficiente"),
        "sample_adequacy_note": ("Poucos telhados de grande área produzem"
                                 " variância alta na densidade estimada:"
                                 " a amostra precisa crescer nessas áreas."),
        "built_up_note": ("A área de influência não é toda construída. O total "
                          "aplica a fração construída típica da morfologia "
                          "identificada; o indicador de nível usa a densidade "
                          "medida na amostra, sem extrapolação."),
        "bins": [{"level": nm, "from_kwp_km2": lo,
                  "to_kwp_km2": None if hi == float("inf") else hi}
                 for nm, lo, hi in PENETRATION_BINS],
        "tipo3_mw_uf": round(sub.tipo3_mw, 2),
        "tipo3_count_uf": sub.tipo3_count,
        "confidence": _mmgd_confidence(evaluation, scan),
    }

    # ---- composicao por classe de consumo
    roof_areas = np.concatenate([
        ((s.roof_boxes[:, 2] - s.roof_boxes[:, 0]) *
         (s.roof_boxes[:, 3] - s.roof_boxes[:, 1]) * s.geo.pixel_area_m2())
        if len(s.roof_boxes) else np.array([])
        for s in sample_scenes]) if sample_scenes else np.array([])
    morph = C.from_morphology(roof_areas, sample_km2)

    # A curva de carga do subsistema NAO e uma segunda medida da mesma
    # grandeza: e um PRIOR regional. Compara-la de igual para igual com a
    # morfologia local produziria divergencia por construcao, porque o
    # subsistema agrega todas as classes. Ela entra com peso pequeno, e o
    # que se reporta e o DESVIO da area em relacao a media regional -- que
    # e a informacao util: onde esta area difere do seu subsistema.
    if subsystem_index is not None and subsystem_load is not None:
        load_mix = C.decompose(subsystem_index, subsystem_load)
        load_mix.method += "_prior_subsistema_%s" % sub.subsystem
        w_load = 0.25
    else:
        load_mix = C.ClassMix(weights={c: 0.25 for c in C.CLASSES},
                              dominant="residencial", residual=float("nan"),
                              r2=0.0, method="indisponivel")
        w_load = 0.0
    fused = C.combine(load_mix, morph, w_load=w_load)
    fused["regional_prior"] = fused.pop("from_load")
    fused["local_evidence"] = fused.pop("from_morphology")
    fused["deviation_from_regional"] = fused.pop("divergence")
    fused["prior_role"] = (
        "A curva de carga entra como prior regional do subsistema %s, com peso "
        "%.0f%%. O desvio indica quanto esta área difere da média regional."
        % (sub.subsystem, w_load * 100))
    fused.pop("sources_agree", None)

    notes = [
        "A ortoimagem é sintética; o detector é o mesmo que roda em imagem real.",
        "A detecção roda em %d amostra(s) de %d m de lado, em resolução de "
        "%.2f m/pixel. A densidade medida é extrapolada para a área de "
        "influência (fator %sx). Ortoimagem de 30 cm sobre a área inteira "
        "seria inviável." % (len(sample_scenes), int(scene_px * ANALYSIS_GSD_M),
                             ANALYSIS_GSD_M, mmgd.get("extrapolation_factor")),
        "A curva de carga entra na granularidade de SUBSISTEMA (dado real do "
        "ONS) como prior regional — não existe curva por subestação em dado "
        "aberto. A morfologia da amostra é a evidência local.",
    ]
    if fused["deviation_from_regional"] > 0.45:
        notes.append("Esta área difere muito do perfil médio do subsistema: "
                     "ponto onde vale aprofundar o estudo.")
    return SubstationProfile(substation=sub, load_class=fused, mmgd=mmgd,
                             vision=vision, evaluation=evaluation,
                             scene_seed=seed, urban_hint=hint, notes=notes)


# ------------------------------------------------------ perfil com dado real
# Nivel de MMGD pela razao capacidade cadastrada / carga media da SE, relativa
# a mesma razao no SIN (config.MMGD_CAPACITY_MWP["SIN"] / carga media do SIN,
# ambas dado real). Decisao: kWp/km2 dependeria da area servida, que nenhuma
# base publica traz; a razao pela carga e comparavel entre SEs de porte
# diferente. Limites em multiplos da referencia nacional (premissa declarada).
PENETRATION_REL_BINS = [("baixa", 0.0, 0.5), ("média", 0.5, 1.5), ("alta", 1.5, float("inf"))]


def _rel_level(rel: float) -> str:
    for name, lo, hi in PENETRATION_REL_BINS:
        if lo <= rel < hi:
            return name
    return "alta"


def with_frontier(prof: SubstationProfile, fr: dict, *, sin_ratio: float,
                  regional: dict | None = None) -> SubstationProfile:
    """Troca composicao e MMGD do perfil pelos da correlacao fronteira T-D (dado real).

    `fr`: fronteira_detail_payload da SE (energia faturada BDGD + SAMP das SEDs
    associadas; MMGD do cadastro da ANEEL). A composicao sai da energia por
    classe de consumo, nao da morfologia de ortoimagem sintetica; a MMGD sai do
    cadastro, nao de paineis detectados em cena sintetica. Sem SED associada
    (n_sed == 0): composicao e MMGD ficam SEM DADO -- nunca o numero sintetico.
    A amostra de visao continua no perfil so como demonstracao do detector.
    """
    n_sed = int(fr.get("n_sed") or 0)
    src = ("correlação fronteira T–D: energia faturada da BDGD (MT/AT por UC) + "
           "SAMP (BT) das %d SEDs associadas" % n_sed)
    if n_sed == 0 or not fr.get("dominant"):
        lc = {"weights": {c: None for c in C.CLASSES}, "dominant": None,
              "label": "Sem dado", "is_mixed": False, "confidence": None,
              "method": "sem_sed_associada", "source": src, "real": True,
              "deviation_from_regional": None, "regional_prior": regional,
              "prior_role": "Nenhuma subestação de distribuição da BDGD foi "
                            "associada a esta SE: não há consumo faturado para "
                            "compor o perfil."}
        mm = {"level": None, "label": "Sem dado", "kwp_total": None, "real": True,
              "source": "cadastro de MMGD da ANEEL associado às SEDs", "confidence": None}
    else:
        w = {c: float(fr["weights"].get(c, 0.0)) for c in C.CLASSES}
        mix = C.ClassMix(weights=w, dominant=fr["dominant"], residual=float("nan"), r2=float("nan"))
        dev = None
        if regional and regional.get("weights"):
            dev = round(sum(abs(w[c] - float(regional["weights"].get(c, 0.0)))
                            for c in C.CLASSES) / 2.0, 4)
        lc = {"weights": {c: round(v, 4) for c, v in w.items()}, "dominant": fr["dominant"],
              "label": mix.label(), "is_mixed": mix.is_mixed,
              # Parcela da energia medida por UC (MT/AT); o resto (BT) vem do SAMP
              # rateado por municipio. E a confianca honesta da composicao.
              "confidence": fr.get("measured_share"),
              "confidence_note": "parcela da energia medida por unidade consumidora (MT/AT)",
              "method": "energia_faturada_bdgd_samp", "source": src, "real": True,
              "deviation_from_regional": dev, "regional_prior": regional,
              "prior_role": "Composição pela energia faturada real. O desvio compara "
                            "com a composição da curva de carga do subsistema %s "
                            "(NNLS sobre perfis canônicos)." % prof.substation.subsystem}
        gd_mw = float(fr.get("gd_kw") or 0.0) / 1000.0
        mw_avg = float(fr.get("mw_avg") or 0.0)
        ratio = gd_mw / mw_avg if mw_avg > 0 else None
        rel = ratio / sin_ratio if ratio is not None and sin_ratio > 0 else None
        lvl = _rel_level(rel) if rel is not None else None
        mm = {"level": lvl, "label": PENETRATION_LABELS.get(lvl, "Sem dado"),
              "kwp_total": round(gd_mw * 1000.0, 1), "gd_n": fr.get("gd_n"),
              "mw_avg": round(mw_avg, 1),
              "ratio_to_load": round(ratio, 4) if ratio is not None else None,
              "ratio_to_load_sin": round(sin_ratio, 4),
              "relative_to_sin": round(rel, 3) if rel is not None else None,
              "direct_share": fr.get("gd_direct_share"),
              "confidence": fr.get("gd_direct_share"),
              "confidence_note": "parcela da MMGD localizada direto pela BDGD (o resto "
                                 "é rateado pelo município)",
              "bins": [{"level": n, "from_rel": lo, "to_rel": None if hi == float("inf") else hi}
                       for n, lo, hi in PENETRATION_REL_BINS],
              "source": "cadastro de MMGD da ANEEL nas SEDs associadas", "real": True,
              "tipo3_mw_uf": round(prof.substation.tipo3_mw, 2),
              "tipo3_count_uf": prof.substation.tipo3_count}
    notes = ["Composição e MMGD: dado real (%s)." % src,
             "A seção de visão computacional abaixo é uma amostra SINTÉTICA de "
             "demonstração do detector: não entra em nenhum número desta SE."]
    return SubstationProfile(substation=prof.substation, load_class=lc, mmgd=mm,
                             vision=prof.vision, evaluation=prof.evaluation,
                             scene_seed=prof.scene_seed, urban_hint=prof.urban_hint,
                             notes=notes)


def _panel_rate(sub: Substation) -> float:
    """Fracao de telhados com painel na cena, em ordem de grandeza real.

    A penetracao media brasileira e da ordem de 3% das unidades consumidoras
    (cerca de 3 milhoes de unidades com MMGD em torno de 90 milhoes de
    consumidores), chegando a 8-10% nos municipios mais avancados. A cena usa
    essa faixa, modulada pela geracao Tipo III declarada na UF -- que e dado
    real e preserva a ordem relativa entre estados.
    """
    base = 0.020
    if sub.tipo3_mw > 0:
        base += min(0.055, sub.tipo3_mw / 100_000.0)
    if sub.subsystem in ("SE", "S"):
        base += 0.015
    return float(np.clip(base, 0.015, 0.10))


def _mmgd_confidence(evaluation: dict, scan) -> float:
    """Confianca do indicador: qualidade medida da deteccao e do casamento."""
    if not evaluation:
        return 0.5
    m = evaluation.get("match") or {}
    f1 = m.get("f1")
    iou = evaluation.get("mask_iou")
    area = (evaluation.get("area") or {}).get("rel_error")
    parts = []
    if f1 is not None:
        parts.append(float(f1))
    if iou is not None:
        parts.append(float(iou))
    if area is not None:
        parts.append(float(np.clip(1.0 - abs(area), 0.0, 1.0)))
    return round(float(np.mean(parts)) if parts else 0.5, 4)


# ------------------------------------------------------ lote
def analyse_many(subs: list[Substation], *, subsystem_series: dict | None = None,
                 det: D.Detector | None = None, scene_px: int = SCENE_PX,
                 with_evaluation: bool = True) -> list[SubstationProfile]:
    """Aplica o pipeline a uma lista — o modo de uso periodico da solucao."""
    det = det or D.build_detector()
    out: list[SubstationProfile] = []
    for s in subs:
        ser = (subsystem_series or {}).get(s.subsystem) or {}
        out.append(analyse(s, subsystem_index=ser.get("index"),
                           subsystem_load=ser.get("load"), det=det,
                           scene_px=scene_px, with_evaluation=with_evaluation))
    return out


def aggregate(profiles: list[SubstationProfile]) -> dict:
    """Sumario do lote, para o painel do mapa."""
    if not profiles:
        return {}
    by_class: dict[str, int] = {}
    by_level: dict[str, int] = {}
    kwp = 0.0
    panels = 0
    dev = 0.0
    for p in profiles:
        c = p.load_class.get("dominant") or "sem dado"
        by_class[c] = by_class.get(c, 0) + 1
        lv = p.mmgd.get("level") or "sem dado"
        by_level[lv] = by_level.get(lv, 0) + 1
        kwp += float(p.mmgd.get("kwp_total") or 0.0)
        panels += int(p.mmgd.get("panels") or 0)
        dev += float(p.load_class.get("deviation_from_regional") or 0.0)
    f1s = [(p.evaluation.get("match") or {}).get("f1") for p in profiles]
    f1s = [f for f in f1s if f is not None]
    ious = [p.evaluation.get("mask_iou") for p in profiles]
    ious = [i for i in ious if i is not None]
    return {
        "real": all(p.load_class.get("real") for p in profiles),
        "substations": len(profiles),
        "by_class": by_class,
        "by_mmgd_level": by_level,
        "total_kwp": round(kwp, 1),
        "total_panels": panels,
        "mean_deviation_from_regional": round(dev / len(profiles), 4),
        "detector_f1_mean": round(float(np.mean(f1s)), 4) if f1s else None,
        "detector_mask_iou_mean": round(float(np.mean(ious)), 4) if ious else None,
        "mixed_rate": round(
            sum(1 for p in profiles if p.load_class.get("is_mixed")) / len(profiles), 4),
    }


# Fracao de carga motora por classe de consumo. Premissa unica, usada tambem
# pela correlacao fronteira T-D: duas telas nao podem discordar da mesma
# grandeza.
MOTOR_FRACTION = {"residencial": 0.22, "comercial": 0.38,
                  "industrial": 0.62, "rural": 0.55}


def motor_fraction(weights: dict) -> float:
    return round(sum(MOTOR_FRACTION[c] * weights.get(c, 0.0)
                     for c in MOTOR_FRACTION), 4)


def clm_hint(profile: SubstationProfile) -> dict:
    """Insumo proposto para a parametrizacao do Modelo de Carga Composta.

    NAO sao parametros prontos para simulacao: sao as grandezas observadas que
    o especialista usa para escolher a composicao do Composite Load Model. A
    distincao esta declarada no proprio payload.
    """
    # Composicao "sem dado" (SE sem SED associada) vem com pesos None: fica vazia.
    w = {k: v for k, v in (profile.load_class.get("weights") or {}).items() if v is not None}
    mmgd = profile.mmgd
    return {
        "composicao_classe": {k: round(v, 4) for k, v in w.items()},
        "fracao_motor_estimada": motor_fraction(w),
        "mmgd_kwp_na_area": mmgd.get("kwp_total"),
        "mmgd_penetracao": mmgd.get("level"),
        "distributed_generation_flag": mmgd.get("level") in ("média", "alta"),
        "confianca": profile.load_class.get("confidence"),
        "aviso": ("Insumo para a parametrização do Composite Load Model. Não é "
                  "conjunto de parâmetros pronto para simulação no ORGANON: a "
                  "escolha final é do especialista."),
        "fracao_motor_premissas": dict(MOTOR_FRACTION),
    }
