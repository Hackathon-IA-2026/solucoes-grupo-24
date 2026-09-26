# -*- coding: utf-8 -*-
"""Registro de subestacoes georreferenciadas.

O desafio pede como entrada "uma lista de subestacoes georreferenciadas". O ONS
publica exatamente isso no conjunto `subestacao`, com latitude e longitude
reais:

    id_subsistema;nom_subsistema;id_estado;nom_estado;nom_agente_principal;
    id_subestacao;nom_subestacao;val_niveltensao;id_estacao;num_barra;
    val_latitude;val_longitude

A capacidade de transformacao vem de `capacidade-transformacao` e dimensiona a
area de influencia: uma subestacao de 300 MVA atende area maior que uma de
30 MVA.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..core.frame import Frame, Provenance
from ..ons import catalog, ckan, csvio

# Densidade de carga urbana tipica, em MVA por km2. Premissa de negocio usada
# apenas para dimensionar o raio de analise a partir da capacidade instalada.
MVA_PER_KM2 = 9.0
RADIUS_MIN_KM = 0.8
RADIUS_MAX_KM = 6.0

# Tensao secundaria que caracteriza transformacao de FRONTEIRA com a
# distribuicao. O conjunto `subestacao` do ONS cobre a rede de operacao,
# isto e, transmissao: subestacao de distribuicao propriamente dita esta
# na BDGD, que nao e dado aberto de acesso direto. A fronteira T-D, porem,
# esta aqui, e e exatamente onde o problema de observabilidade aparece.
FRONTIER_SECONDARY_KV_MAX = 138.0


@dataclass
class Substation:
    sub_id: str
    name: str
    uf: str
    state_name: str
    subsystem: str
    agent: str
    lat: float
    lon: float
    voltage_kv: float
    capacity_mva: float = 0.0
    transformers: int = 0
    tipo3_count: int = 0
    tipo3_mw: float = 0.0
    secondary_kv_min: float = 0.0
    frontier_mva: float = 0.0

    @property
    def is_frontier(self) -> bool:
        """Transformacao de fronteira com a rede de distribuicao."""
        return 0.0 < self.secondary_kv_min <= FRONTIER_SECONDARY_KV_MAX

    @property
    def radius_km(self) -> float:
        """Raio da area de influencia, a partir da capacidade de fronteira.

        Usa a capacidade que efetivamente desce para a distribuicao, nao a
        capacidade total: um transformador 765/500 kV nao atende carga,
        apenas interliga a transmissao.
        """
        base = self.frontier_mva if self.frontier_mva > 0 else self.capacity_mva
        if base <= 0:
            return 1.5
        area_km2 = base / MVA_PER_KM2
        r = float(np.sqrt(area_km2 / np.pi))
        return float(np.clip(r, RADIUS_MIN_KM, RADIUS_MAX_KM))

    @property
    def area_km2(self) -> float:
        return float(np.pi * self.radius_km ** 2)

    def to_dict(self) -> dict:
        return {
            "sub_id": self.sub_id,
            "name": self.name,
            "uf": self.uf,
            "state_name": self.state_name,
            "subsystem": self.subsystem,
            "agent": self.agent,
            "lat": round(self.lat, 6),
            "lon": round(self.lon, 6),
            "voltage_kv": round(self.voltage_kv, 1),
            "capacity_mva": round(self.capacity_mva, 1),
            "transformers": self.transformers,
            "radius_km": round(self.radius_km, 2),
            "area_km2": round(self.area_km2, 2),
            "tipo3_count": self.tipo3_count,
            "tipo3_mw": round(self.tipo3_mw, 2),
            "secondary_kv_min": round(self.secondary_kv_min, 1),
            "frontier_mva": round(self.frontier_mva, 1),
            "is_frontier": self.is_frontier,
        }


@dataclass
class Registry:
    items: list[Substation] = field(default_factory=list)
    provenance: list[Provenance] = field(default_factory=list)
    mode: str = "demo"
    report: dict = field(default_factory=dict)

    def by_id(self, sub_id: str) -> Substation | None:
        for s in self.items:
            if s.sub_id == sub_id:
                return s
        return None

    def filter(self, *, uf: str = "", subsystem: str = "",
               min_voltage: float = 0.0, frontier_only: bool = False
               ) -> list[Substation]:
        out = self.items
        if uf:
            out = [s for s in out if s.uf == uf]
        if subsystem:
            out = [s for s in out if s.subsystem == subsystem]
        if min_voltage:
            out = [s for s in out if s.voltage_kv >= min_voltage]
        if frontier_only:
            out = [s for s in out if s.is_frontier]
        return out

    def frontier(self) -> list[Substation]:
        return [s for s in self.items if s.is_frontier]

    def ufs(self) -> list[str]:
        return sorted({s.uf for s in self.items if s.uf})

    def provenance_dicts(self) -> list[dict]:
        return [p.to_dict() for p in self.provenance]


# ------------------------------------------------------------- carga
def _fetch(key: str) -> tuple[Frame | None, Provenance | None, str]:
    spec = catalog.CURATED[key]
    url = catalog.resource_url(key)
    name = url.rsplit("/", 1)[-1]
    res = ckan.fetch_resource(url, dataset=spec["package"], resource=name)
    if not res.ok:
        return None, None, res.error or "recurso indisponível"
    prov = Provenance(spec["package"], name, url, res.fetched_at, 0,
                      res.bytes_read, res.mode, spec["lag_note"])
    frame, rep = csvio.read_csv(res.payload, schema=spec["schema"],
                                time_column=None, provenance=prov)
    prov = Provenance(spec["package"], name, url, res.fetched_at, len(frame),
                      res.bytes_read, res.mode, spec["lag_note"])
    frame.provenance = [prov]
    return frame, prov, ""


def load_registry(*, force_demo: bool = False, limit: int = 0) -> Registry:
    """Monta o registro a partir dos dados abertos do ONS."""
    if force_demo:
        return _demo_registry()

    subs_frame, prov_sub, err = _fetch("subestacao")
    if subs_frame is None or len(subs_frame) == 0:
        reg = _demo_registry()
        reg.report = {"error": err, "fallback": "demo"}
        return reg

    # capacidade de transformacao por subestacao (soma dos transformadores)
    cap_by_name: dict[tuple, tuple[float, int]] = {}
    frontier_by_name: dict[tuple, float] = {}
    sec_by_name: dict[tuple, float] = {}
    cap_frame, prov_cap, cap_err = _fetch("capacidade_trafo")
    if cap_frame is not None and len(cap_frame):
        names = cap_frame["nom_subestacao"]
        pots = cap_frame["val_potencianominal_mva"]
        offs = cap_frame["dat_desativacao"]
        secs = cap_frame["val_tensaosecundario_kv"]
        cufs = cap_frame["id_estado"]
        # Chave composta (nome, UF): ha homonimos entre estados -- BANDEIRANTES
        # existe em GO e em SP. Casar so por nome somava a capacidade das duas.
        for nm, pot, off, sec, cuf in zip(names.tolist(), pots.tolist(),
                                          offs.tolist(), secs.tolist(),
                                          cufs.tolist()):
            if not nm or not np.isfinite(pot):
                continue
            if str(off).strip():
                continue          # transformador desativado nao soma capacidade
            k = (str(nm).strip().upper(), str(cuf).strip().upper())
            acc, cnt = cap_by_name.get(k, (0.0, 0))
            cap_by_name[k] = (acc + float(pot), cnt + 1)
            if np.isfinite(sec) and sec > 0:
                prev = sec_by_name.get(k)
                sec_by_name[k] = sec if prev is None else min(prev, float(sec))
                if sec <= FRONTIER_SECONDARY_KV_MAX:
                    frontier_by_name[k] = frontier_by_name.get(k, 0.0) + float(pot)

    # usinas Tipo III por estado (geracao conectada a distribuicao)
    tipo3_by_uf: dict[str, tuple[int, float]] = {}
    mod_frame, prov_mod, mod_err = _fetch("modalidade")
    if mod_frame is not None and len(mod_frame):
        modal = mod_frame["nom_modalidadeoperacao"]
        ufs = mod_frame["id_estado"]
        pot = mod_frame["val_potenciaautorizada"]
        for m, uf, p in zip(modal.tolist(), ufs.tolist(), pot.tolist()):
            if "TIPO III" not in str(m).upper():
                continue
            k = str(uf).strip().upper()
            c, s = tipo3_by_uf.get(k, (0, 0.0))
            tipo3_by_uf[k] = (c + 1, s + (float(p) if np.isfinite(p) else 0.0))

    items: list[Substation] = []
    skipped = 0
    for i in range(len(subs_frame)):
        lat = float(subs_frame["val_latitude"][i])
        lon = float(subs_frame["val_longitude"][i])
        if not (np.isfinite(lat) and np.isfinite(lon)):
            skipped += 1
            continue
        if not (-34.0 <= lat <= 6.0 and -74.0 <= lon <= -34.0):
            skipped += 1          # fora do territorio brasileiro
            continue
        name = str(subs_frame["nom_subestacao"][i]).strip()
        key_cap = (name.upper(), str(subs_frame["id_estado"][i]).strip().upper())
        cap, ntr = cap_by_name.get(key_cap, (0.0, 0))
        uf = str(subs_frame["id_estado"][i]).strip()
        t3c, t3mw = tipo3_by_uf.get(uf, (0, 0.0))
        items.append(Substation(
            sub_id=str(subs_frame["id_subestacao"][i]).strip(),
            name=name,
            uf=uf,
            state_name=str(subs_frame["nom_estado"][i]).strip().title(),
            subsystem=str(subs_frame["id_subsistema"][i]).strip(),
            agent=str(subs_frame["nom_agente_principal"][i]).strip().title(),
            lat=lat, lon=lon,
            voltage_kv=float(subs_frame["val_niveltensao"][i])
                       if np.isfinite(subs_frame["val_niveltensao"][i]) else 0.0,
            capacity_mva=cap, transformers=ntr,
            tipo3_count=t3c, tipo3_mw=t3mw,
            secondary_kv_min=sec_by_name.get(key_cap, 0.0),
            frontier_mva=frontier_by_name.get(key_cap, 0.0),
        ))

    # remove duplicatas de barra: a mesma subestacao aparece por nivel de tensao
    seen: dict[str, Substation] = {}
    for s in items:
        key = "%s|%s" % (s.name.upper(), s.uf)
        prev = seen.get(key)
        if prev is None or s.voltage_kv > prev.voltage_kv:
            seen[key] = s
    unique = sorted(seen.values(), key=lambda s: (s.uf, s.name))
    if limit:
        unique = unique[:limit]

    prov = [p for p in (prov_sub, prov_cap, prov_mod) if p is not None]
    mode = "live" if any(p.mode == "live" for p in prov) else (
        "cache" if any(p.mode == "cache" for p in prov) else "demo")
    return Registry(items=unique, provenance=prov, mode=mode, report={
        "rows_read": len(subs_frame),
        "skipped_no_coords": skipped,
        "unique_substations": len(unique),
        "with_capacity": sum(1 for s in unique if s.capacity_mva > 0),
        "frontier_substations": sum(1 for s in unique if s.is_frontier),
        "capacity_source_rows": 0 if cap_frame is None else len(cap_frame),
        "tipo3_states": len(tipo3_by_uf),
        "capacity_error": cap_err,
        "modalidade_error": mod_err,
    })


# ------------------------------------------------------------- demo
_DEMO = [
    # (id, nome, uf, estado, subsistema, lat, lon, kV, MVA)
    ("BAJUAZ", "JUAZEIRO", "BA", "Bahia", "NE", -9.4160, -40.5030, 230.0, 450.0),
    ("CEFTZ2", "FORTALEZA II", "CE", "Ceará", "NE", -3.8180, -38.5920, 500.0, 1200.0),
    ("MTNMUT", "NOVA MUTUM", "MT", "Mato Grosso", "SE", -13.8280, -56.0870, 230.0, 150.0),
    ("MTBRSN", "BRASNORTE", "MT", "Mato Grosso", "SE", -12.1480, -57.9810, 230.0, 100.0),
    ("MGBHZ4", "BELO HORIZONTE 4", "MG", "Minas Gerais", "SE", -19.9200, -43.9380, 345.0, 800.0),
    ("SPBAR2", "BARUERI", "SP", "São Paulo", "SE", -23.5110, -46.8760, 345.0, 900.0),
    ("RJGRAJ", "GRAJAU", "RJ", "Rio de Janeiro", "SE", -22.9260, -43.2620, 345.0, 750.0),
    ("PRCUR2", "CURITIBA NORTE", "PR", "Paraná", "S", -25.3670, -49.2270, 230.0, 400.0),
    ("RSPAL2", "PORTO ALEGRE 2", "RS", "Rio Grande do Sul", "S", -30.0690, -51.1780, 230.0, 500.0),
    ("GOANP2", "ANAPOLIS", "GO", "Goiás", "SE", -16.3280, -48.9530, 230.0, 300.0),
    ("PIPIC2", "PICOS", "PI", "Piauí", "NE", -7.0770, -41.4670, 230.0, 180.0),
    ("RNNAT3", "NATAL 3", "RN", "Rio Grande do Norte", "NE", -5.8100, -35.2250, 230.0, 250.0),
    ("PABEL3", "BELEM 3", "PA", "Pará", "N", -1.4450, -48.4700, 230.0, 400.0),
    ("MSCGR2", "CAMPO GRANDE 2", "MS", "Mato Grosso do Sul", "SE", -20.4620, -54.6160, 230.0, 220.0),
]


def _demo_registry() -> Registry:
    items = [Substation(sub_id=i, name=n, uf=uf, state_name=st, subsystem=ss,
                        agent="Agente demonstrativo", lat=la, lon=lo,
                        voltage_kv=kv, capacity_mva=mva, transformers=2,
                        tipo3_count=12, tipo3_mw=18.5,
                        secondary_kv_min=69.0, frontier_mva=mva * 0.6)
             for (i, n, uf, st, ss, la, lo, kv, mva) in _DEMO]
    prov = Provenance("subestacao", "gerador determinístico", "",
                      Provenance.now_iso(), len(items), 0, "demo",
                      "Dados demonstrativos: coordenadas aproximadas.")
    return Registry(items=items, provenance=[prov], mode="demo",
                    report={"unique_substations": len(items),
                            "fallback": "demo"})
