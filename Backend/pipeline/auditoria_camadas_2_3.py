"""Camadas 2 e 3 da auditoria da MMGD: desempate BDGD × cadastro ANEEL e fator de correção.

Uso (de dentro de Backend/):
    python -m pipeline.auditoria_camadas_2_3 --mock
    python -m pipeline.auditoria_camadas_2_3 --deteccoes det.geojson --bdgd bdgd.json --aneel aneel.json

Entradas:
- detecções da Camada 1 (GeoJSON de auditoria_camada1.py): o painel EXISTE, com área em m²;
- BDGD (topologia): unidades com GD cadastrada, com alimentador/transformador e potência, e a
  `data_referencia` da publicação;
- cadastro diário da ANEEL: empreendimentos homologados e a data de homologação.

Desempate (planejamento v2, Pilar 2), para cada painel detectado:
| BDGD  | ANEEL                               | classificação         | entra no fator? |
|-------|-------------------------------------|-----------------------|-----------------|
| casa  | —                                   | Cadastrada            | sim             |
| ausente | homologado DEPOIS da data da BDGD | Lag de Sistema        | sim             |
| ausente | homologado ANTES da data da BDGD  | Divergência cadastral | sim (homologada; vai para revisão) |
| ausente | ausente                           | Não homologada        | NÃO (exceção escalada) |

"Recente" = depois da data de referência da BDGD: é exatamente o caso em que o ciclo anual da
BDGD não teve como absorver o registro (a dor que o ONS declarou). Homologado antes e mesmo
assim fora da BDGD não é lag — é divergência entre bases, sinalizada à parte.

Fator de correção por mancha (nível em config/visao.yaml, padrão alimentador):
    fator = capacidade auditada (detecções que não são "Não homologada", área × kWp/m²)
            ÷ capacidade cadastrada na BDGD da mancha
Mancha sem capacidade cadastrada -> fator null com motivo (nunca infinito nem zero inventado).

Decisões:
- Casamento painel↔registro por distância geodésica ≤ raio, UM PARA UM (pares ordenados pela
  distância; cada painel e cada registro usados no máximo uma vez). Assim dois painéis vizinhos
  não "herdam" o mesmo cadastro.
- Painel sem casamento na BDGD fica na mancha da unidade BDGD mais próxima (proxy do
  transformador mais próximo), e o campo `mancha_por` diz isso.
- Flag de mock: se QUALQUER entrada for mock, a saída inteira é is_mock=true e vai para a pasta
  mock/ (dado sintético nunca contamina a saída real que o preditor consome).
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pipeline import visao_comum as vc
from src.utils.paths import ensure

CADASTRADA = "Cadastrada"
LAG = "Lag de Sistema"
DIVERGENCIA = "Divergência cadastral"
NAO_HOMOLOGADA = "Não homologada"
CLASSES = (CADASTRADA, LAG, DIVERGENCIA, NAO_HOMOLOGADA)
# Classes cuja capacidade entra no numerador do fator (tudo que é MMGD homologada).
NO_FATOR = frozenset({CADASTRADA, LAG, DIVERGENCIA})


@dataclass
class Painel:
    id: str
    lat: float
    lon: float
    area_m2: float
    is_mock: bool


@dataclass
class Resultado:
    id: str
    mancha: str
    mancha_por: str
    classificacao: str
    area_m2: float
    capacidade_estimada_kw: float
    bdgd_id: str | None
    distancia_bdgd_m: float | None
    aneel_codigo: str | None
    distancia_aneel_m: float | None
    data_homologacao: str | None
    entra_no_fator: bool


# --------------------------------------------------------------------------- leitura
def ler_json(caminho_arq: Path) -> dict[str, Any]:
    return json.loads(caminho_arq.read_text(encoding="utf-8"))


def paineis_da_camada1(colecao: dict[str, Any]) -> list[Painel]:
    ps = []
    for f in vc.iterar_features(colecao):
        p = f["properties"]
        ps.append(Painel(p["id"], p["lat"], p["lon"], float(p["area_m2"]), bool(p.get("is_mock", False))))
    if not ps:
        raise vc.ErroVisao("Camada 1 sem painéis detectados: nada a auditar")
    return ps


# --------------------------------------------------------------------------- casamento
def casar(paineis: list[Painel], registros: list[dict[str, Any]], raio_m: float, chave: str) -> dict[str, tuple[dict[str, Any], float]]:
    """{id do painel: (registro, distância)} — um para um, menor distância primeiro."""
    # chave de registro repetida quebraria a rastreabilidade (qual cadastro casou?)
    ids = [r[chave] for r in registros]
    if len(ids) != len(set(ids)):
        raise vc.ErroVisao(f"registros com {chave} repetido: {sorted({x for x in ids if ids.count(x) > 1})}")
    pares = sorted(
        (vc.distancia_m(p.lat, p.lon, r["lat"], r["lon"]), i, j)
        for i, p in enumerate(paineis) for j, r in enumerate(registros)
    )
    usados_p: set[int] = set()
    usados_r: set[int] = set()
    casados: dict[str, tuple[dict[str, Any], float]] = {}
    for d, i, j in pares:
        if d > raio_m:
            break
        if i in usados_p or j in usados_r:
            continue
        usados_p.add(i)
        usados_r.add(j)
        casados[paineis[i].id] = (registros[j], d)
    return casados


def mancha_mais_proxima(p: Painel, unidades: list[dict[str, Any]], nivel: str) -> str:
    return min(unidades, key=lambda u: vc.distancia_m(p.lat, p.lon, u["lat"], u["lon"]))[nivel]


# --------------------------------------------------------------------------- desempate
def classificar(tem_bdgd: bool, data_homologacao: date | None, data_ref_bdgd: date) -> str:
    """A regra do desempate, isolada (testada caso a caso)."""
    if tem_bdgd:
        return CADASTRADA
    if data_homologacao is None:
        return NAO_HOMOLOGADA
    return LAG if data_homologacao > data_ref_bdgd else DIVERGENCIA


def auditar(paineis: list[Painel], bdgd: dict[str, Any], aneel: dict[str, Any], raio_m: float,
            kwp_por_m2: float, nivel: str) -> dict[str, Any]:
    unidades = bdgd["unidades"]
    empreend = aneel["empreendimentos"]
    if not unidades:
        raise vc.ErroVisao("BDGD sem unidades: não há topologia para atribuir manchas")
    data_ref = date.fromisoformat(bdgd["data_referencia"])
    em_bdgd = casar(paineis, unidades, raio_m, "id")
    em_aneel = casar(paineis, empreend, raio_m, "codigo")

    resultados: list[Resultado] = []
    for p in paineis:
        ub, db = em_bdgd.get(p.id, (None, None))
        ea, da = em_aneel.get(p.id, (None, None))
        data_h = date.fromisoformat(ea["data_homologacao"]) if ea and ea.get("data_homologacao") else None
        classe = classificar(ub is not None, data_h, data_ref)
        resultados.append(Resultado(
            id=p.id,
            mancha=ub[nivel] if ub else mancha_mais_proxima(p, unidades, nivel),
            mancha_por="casamento" if ub else "bdgd_mais_proximo",
            classificacao=classe,
            area_m2=p.area_m2,
            capacidade_estimada_kw=round(p.area_m2 * kwp_por_m2, 3),
            bdgd_id=ub["id"] if ub else None,
            distancia_bdgd_m=round(db, 1) if db is not None else None,
            aneel_codigo=ea["codigo"] if ea else None,
            distancia_aneel_m=round(da, 1) if da is not None else None,
            data_homologacao=data_h.isoformat() if data_h else None,
            entra_no_fator=classe in NO_FATOR,
        ))

    casados_bdgd = {u["id"] for u, _ in em_bdgd.values()}
    manchas = []
    for m in sorted({u[nivel] for u in unidades} | {r.mancha for r in resultados}):
        rs = [r for r in resultados if r.mancha == m]
        cadastrada = sum(u["potencia_kw"] for u in unidades if u[nivel] == m)
        auditada = sum(r.capacidade_estimada_kw for r in rs if r.entra_no_fator)
        manchas.append({
            "mancha": m,
            "capacidade_cadastrada_bdgd_kw": round(cadastrada, 3),
            "capacidade_auditada_kw": round(auditada, 3),
            "fator_correcao": round(auditada / cadastrada, 4) if cadastrada > 0 else None,
            "motivo_sem_fator": None if cadastrada > 0 else "mancha sem capacidade cadastrada na BDGD",
            "capacidade_nao_homologada_kw": round(sum(r.capacidade_estimada_kw for r in rs if not r.entra_no_fator), 3),
            **{f"n_{c}": sum(r.classificacao == c for r in rs) for c in CLASSES},
            "bdgd_sem_deteccao": sorted(u["id"] for u in unidades if u[nivel] == m and u["id"] not in casados_bdgd),
        })

    return {
        "parametros": {"raio_casamento_m": raio_m, "kwp_por_m2": kwp_por_m2, "nivel_mancha": nivel,
                       "data_referencia_bdgd": data_ref.isoformat(),
                       "data_extracao_aneel": aneel.get("data_extracao")},
        "resumo": {c: sum(r.classificacao == c for r in resultados) for c in CLASSES},
        "deteccoes": [asdict(r) for r in resultados],
        "manchas": manchas,
        # exceções: escaladas, NUNCA incorporadas em silêncio à previsão
        "excecoes_nao_homologadas": [r.id for r in resultados if r.classificacao == NAO_HOMOLOGADA],
    }


def executar(mock: bool, deteccoes: str | None = None, bdgd: str | None = None,
             aneel: str | None = None, saida: str | None = None) -> Path:
    cfg_vis = vc.config()
    cfg = cfg_vis["auditoria"]
    arq_det = vc.caminho(deteccoes or (cfg_vis["camada1"]["saida_mock"] if mock else cfg_vis["camada1"]["saida"]))
    arq_bdgd = vc.caminho(bdgd or cfg["mock"]["bdgd"]) if (bdgd or mock) else None
    arq_aneel = vc.caminho(aneel or cfg["mock"]["aneel"]) if (aneel or mock) else None
    if arq_bdgd is None or arq_aneel is None:
        raise vc.ErroVisao("modo real precisa de --bdgd e --aneel (ingestão da BDGD da área piloto: Fase 6)")
    if mock and not arq_det.exists():
        # conveniência do modo mock: gera a Camada 1 sintética se ainda não existir
        from pipeline import auditoria_camada1
        auditoria_camada1.executar(mock=True, saida=str(arq_det))

    colecao = vc.ler_geojson(arq_det)
    b, a = ler_json(arq_bdgd), ler_json(arq_aneel)
    paineis = paineis_da_camada1(colecao)
    is_mock = (bool(colecao.get("properties", {}).get("is_mock")) or any(p.is_mock for p in paineis)
               or b.get("mock") is True or a.get("mock") is True)
    if is_mock and not mock and saida is None:
        raise vc.ErroVisao("alguma entrada é mock: rode com --mock (a saída real nunca recebe dado sintético)")

    resultado = auditar(paineis, b, a, cfg["raio_casamento_m"], cfg["kwp_por_m2"], cfg["nivel_mancha"])
    destino = vc.caminho(saida or (cfg["mock"]["saida"] if is_mock else cfg["saida"]))
    ensure(destino.parent)
    destino.write_text(json.dumps({
        "is_mock": is_mock,
        "gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entradas": {"deteccoes": str(arq_det), "bdgd": str(arq_bdgd), "aneel": str(arq_aneel)},
        **resultado,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return destino


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Camadas 2 e 3: desempate BDGD × ANEEL e fator de correção.")
    ap.add_argument("--mock", action="store_true", help="usa os mocks de pipeline/mock/")
    ap.add_argument("--deteccoes", help="GeoJSON da Camada 1")
    ap.add_argument("--bdgd", help="JSON da BDGD (unidades com GD + data_referencia)")
    ap.add_argument("--aneel", help="JSON do cadastro diário da ANEEL")
    ap.add_argument("--saida", help="JSON de saída (padrão: config)")
    args = ap.parse_args(argv)
    try:
        destino = executar(args.mock, args.deteccoes, args.bdgd, args.aneel, args.saida)
    except vc.ErroVisao as e:
        print(f"ERRO: {e}")
        return 2
    r = ler_json(destino)
    print(f"is_mock={r['is_mock']} · {r['resumo']}")
    for m in r["manchas"]:
        print(f"  {m['mancha']}: fator {m['fator_correcao']} "
              f"({m['capacidade_auditada_kw']} kW auditados / {m['capacidade_cadastrada_bdgd_kw']} kW na BDGD)")
    print(f"-> {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
