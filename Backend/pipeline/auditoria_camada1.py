"""Camada 1 da auditoria da MMGD — realidade física: painéis detectados em imagem de satélite.

Uso (de dentro de Backend/):
    python -m pipeline.auditoria_camada1 [--imagens PASTA] [--modelo caminho.pt]   # real
    python -m pipeline.auditoria_camada1 --mock                                      # sintético

Saída: GeoJSON (EPSG:4326), uma Feature por painel detectado, com o polígono (máscara, se o
modelo for de segmentação; retângulo da caixa, se for de detecção), a área estimada em m², a
confiança e a imagem de origem. É o insumo da Camada 2/3 (auditoria_camadas_2_3.py).

Modo --mock (enquanto não há imagem da área piloto): NÃO roda o modelo. Os painéis vêm de
pipeline/mock/camada1_paineis_mock.json (sintéticos, declarados à mão), passam pela MESMA
geometria do modo real (polígono lon/lat + área geodésica) e saem com is_mock=true, num
arquivo separado (output/auditoria/mock/). Decisão: rodar o YOLO em imagem "placeholder" não
testaria nada (sem painel, zero detecções) e o mock com coordenadas conhecidas deixa as camadas
2 e 3 testáveis de ponta a ponta.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline import visao_comum as vc


def _feature(id_: str, anel: list[tuple[float, float]], props: dict[str, Any]) -> dict[str, Any]:
    """Feature GeoJSON de um painel: polígono + área geodésica + centroide (usado no casamento)."""
    lat, lon = vc.centroide(anel)
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[list(p) for p in anel]]},
        "properties": {"id": id_, "area_m2": round(vc.area_m2(anel), 2),
                       "lat": round(lat, 7), "lon": round(lon, 7), **props},
    }


def deteccoes_mock(arquivo: Path) -> list[dict[str, Any]]:
    """Painéis sintéticos -> Features (is_mock=true em cada uma). Arquivo sem flag é recusado."""
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    if dados.get("mock") is not True:
        raise vc.ErroVisao(f"{arquivo}: mock sem \"mock\": true (regra: dado sintético sempre marcado)")
    return [
        _feature(p["id"], vc.retangulo_lonlat(p["lat"], p["lon"], p["largura_m"], p["altura_m"]),
                 {"imagem": p["imagem"], "confianca": p["confianca"], "classe": "solar-panel",
                  "geometria": "retangulo_sintetico", "is_mock": True})
        for p in dados["paineis"]
    ]


def deteccoes_reais(pasta: Path, arquivo_modelo: Path, confianca: float) -> list[dict[str, Any]]:
    """YOLO em cada imagem georreferenciada -> Features (is_mock=false)."""
    modelo = vc.carregar_modelo(arquivo_modelo)
    tarefa = vc.tarefa_do_modelo(modelo)
    geometria = "mascara" if tarefa == "segment" else "caixa"
    features = []
    for imagem in vc.listar_imagens(pasta):
        geo = vc.georreferencia_da_imagem(imagem)  # sem georreferência: erro (nada inventado)
        resultado = modelo.predict(source=str(imagem), conf=confianca, verbose=False)[0]
        for k, d in enumerate(vc.deteccoes_do_resultado(resultado, tarefa), start=1):
            features.append(_feature(
                f"{imagem.stem}-{k:03d}", vc.poligono_lonlat(d.poligono, geo),
                {"imagem": imagem.name, "confianca": round(d.confianca, 4), "classe": d.classe,
                 "geometria": geometria, "is_mock": False}))
    return features


def executar(mock: bool, imagens: str | None = None, modelo: str | None = None,
             saida: str | None = None) -> Path:
    cfg = vc.config()
    if mock:
        features = deteccoes_mock(vc.caminho(cfg["camada1"]["mock_paineis"]))
        destino = vc.caminho(saida or cfg["camada1"]["saida_mock"])
        origem = "mock"
    else:
        pasta = vc.caminho(imagens or cfg["imagens"]["area_piloto"])
        features = deteccoes_reais(pasta, vc.resolver_caminho_modelo(modelo), cfg["modelo"]["confianca_minima"])
        destino = vc.caminho(saida or cfg["camada1"]["saida"])
        origem = str(pasta)
    return vc.escrever_geojson(features, destino, {
        "camada": "1 · realidade física (satélite)",
        "is_mock": mock,
        "origem": origem,
        "gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_paineis": len(features),
        "area_total_m2": round(sum(f["properties"]["area_m2"] for f in features), 2),
    })


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Camada 1: painéis detectados -> GeoJSON.")
    ap.add_argument("--mock", action="store_true", help="painéis sintéticos (sem modelo nem imagem)")
    ap.add_argument("--imagens", help="pasta de imagens georreferenciadas (padrão: config)")
    ap.add_argument("--modelo", help="arquivo .pt (padrão: config)")
    ap.add_argument("--saida", help="GeoJSON de saída (padrão: config)")
    args = ap.parse_args(argv)
    try:
        destino = executar(args.mock, args.imagens, args.modelo, args.saida)
    except vc.ErroVisao as e:
        print(f"ERRO: {e}")
        return 2
    props = vc.ler_geojson(destino)["properties"]
    print(f"{props['n_paineis']} painéis, {props['area_total_m2']} m² (is_mock={props['is_mock']}) -> {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
