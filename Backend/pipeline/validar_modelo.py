"""Revisão rápida do modelo YOLO de painéis solares sobre um conjunto de imagens de amostra.

Uso (de dentro de Backend/):
    python -m pipeline.validar_modelo --imagens data/raw/satelite/amostra [--modelo caminho.pt]

O que faz:
1. Carrega o modelo (ultralytics) e descobre SOZINHO se é de detecção (caixa) ou segmentação
   (máscara) por `model.task` — nada é assumido pelo nome do arquivo.
2. Roda a inferência em cada imagem e conta detecções e confiança média.
3. Salva cada imagem com as detecções desenhadas (revisão visual) em <imagens>/_anotadas/.
4. Diagnostica problemas óbvios (regras em diagnosticar(), testadas) e grava o relatório em
   docs/reports/visao_validacao_modelo.md.

Gabarito opcional: `gabarito.csv` na pasta das imagens (colunas imagem,n_paineis). Com ele, o
diagnóstico aponta falso positivo (imagem sem painel com detecção) e falso negativo. SEM ele o
relatório NUNCA diz "adequado": "nenhum aviso" sem gabarito só quer dizer sanidade ok — a
qualidade se confere nas imagens anotadas. Decisão tomada depois que o modelo (best.pt, versão antiga do treinamento) marcou
"solar-panel" em fotos de ônibus e pessoas (imagens de exemplo do ultralytics) com o
diagnóstico antigo dizendo "adequado".

Regra do plano (dia 21): é uma REVISÃO RÁPIDA. Se o diagnóstico não achar nada óbvio, o modelo
segue para a área piloto sem mais tempo gasto aqui.
"""
from __future__ import annotations

import argparse
import csv
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline import visao_comum as vc
from src.utils.paths import DOCS_REPORTS, ensure

RELATORIO = DOCS_REPORTS / "visao_validacao_modelo.md"
# Palavras que um modelo de PAINEL SOLAR deveria ter no nome de alguma classe.
TERMOS_CLASSE_PAINEL = ("solar", "panel", "painel", "pv", "fotovolt")
CONFIANCA_MEDIA_BAIXA = 0.40
GABARITO = "gabarito.csv"
PASTA_ANOTADAS = "_anotadas"


@dataclass
class ResultadoImagem:
    imagem: str
    deteccoes: int
    confianca_media: float | None
    gsd_m: float | None = None
    erro_georref: str | None = None
    esperado: int | None = None  # nº de painéis no gabarito (None = sem gabarito)


@dataclass
class Validacao:
    arquivo_modelo: str
    tarefa: str
    metadados: dict[str, Any]
    imagens: list[ResultadoImagem] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    pasta_anotadas: str | None = None

    @property
    def com_gabarito(self) -> bool:
        return bool(self.imagens) and all(i.esperado is not None for i in self.imagens)

    @property
    def veredito(self) -> str:
        """Três saídas, nunca "adequado" sem gabarito."""
        if self.avisos:
            return "ajustar"
        return "adequado" if self.com_gabarito else "sanidade_ok_sem_gabarito"


def ler_gabarito(pasta: Path) -> dict[str, int]:
    """gabarito.csv (imagem,n_paineis) -> {nome da imagem: nº esperado}; ausente -> {}."""
    arq = pasta / GABARITO
    if not arq.exists():
        return {}
    with arq.open(encoding="utf-8", newline="") as f:
        return {linha["imagem"].strip(): int(linha["n_paineis"]) for linha in csv.DictReader(f)}


def diagnosticar(tarefa: str, metadados: dict[str, Any], imagens: list[ResultadoImagem],
                 gsd_maximo_m: float) -> list[str]:
    """Problemas ÓBVIOS para ajustar antes da área piloto (lista vazia = seguir em frente)."""
    avisos: list[str] = []
    classes = [str(c).lower() for c in (metadados.get("classes") or {}).values()]
    if not any(t in c for c in classes for t in TERMOS_CLASSE_PAINEL):
        avisos.append(f"nenhuma classe parece ser painel solar: {classes or 'sem classes'}")
    if tarefa == "detect":
        avisos.append("modelo de DETECÇÃO (caixa): a área do painel sai do retângulo e superestima "
                      "arranjos inclinados/irregulares; o plano prevê segmentação (YOLOv8-seg)")
    fp = [i.imagem for i in imagens if i.esperado == 0 and i.deteccoes > 0]
    if fp:
        avisos.append(f"falso positivo em {len(fp)} imagem(ns) sem painel no gabarito (ex.: {fp[0]}): "
                      "subir a confiança mínima ou fazer fine-tuning com imagens da área")
    fn = [i.imagem for i in imagens if i.esperado and i.deteccoes == 0]
    if fn:
        avisos.append(f"falso negativo: {len(fn)} imagem(ns) com painel no gabarito e nenhuma detecção (ex.: {fn[0]})")
    sem_geo = [i.imagem for i in imagens if i.erro_georref]
    if sem_geo:
        avisos.append(f"{len(sem_geo)} de {len(imagens)} imagem(ns) sem georreferência (ex.: {sem_geo[0]}): "
                      "a Camada 1 da auditoria vai recusá-las (painel sem coordenada não entra)")
    total = sum(i.deteccoes for i in imagens)
    if imagens and total == 0:
        avisos.append("nenhuma detecção em nenhuma imagem: confira se há painéis nas amostras e se "
                      "a resolução é compatível (GSD) antes de concluir que o modelo falhou")
    confs = [i.confianca_media for i in imagens if i.confianca_media is not None]
    if confs and statistics.fmean(confs) < CONFIANCA_MEDIA_BAIXA:
        avisos.append(f"confiança média baixa ({statistics.fmean(confs):.2f} < {CONFIANCA_MEDIA_BAIXA}): "
                      "provável diferença de domínio (sensor/resolução) — candidato a fine-tuning")
    grossas = [i.imagem for i in imagens if i.gsd_m is not None and i.gsd_m > gsd_maximo_m]
    if grossas:
        avisos.append(f"{len(grossas)} imagem(ns) com pixel maior que {gsd_maximo_m} m "
                      f"(ex.: {grossas[0]}): painel residencial some nessa resolução")
    return avisos


def validar(arquivo_modelo: Path, pasta_imagens: Path, confianca: float) -> Validacao:
    modelo = vc.carregar_modelo(arquivo_modelo)
    tarefa = vc.tarefa_do_modelo(modelo)
    anotadas = ensure(pasta_imagens / PASTA_ANOTADAS)
    v = Validacao(str(arquivo_modelo), tarefa, vc.metadados_modelo(modelo), pasta_anotadas=str(anotadas))
    gabarito = ler_gabarito(pasta_imagens)
    for imagem in vc.listar_imagens(pasta_imagens):
        resultado = modelo.predict(source=str(imagem), conf=confianca, verbose=False)[0]
        resultado.save(filename=str(anotadas / imagem.name))  # revisão visual rápida
        dets = vc.deteccoes_do_resultado(resultado, tarefa)
        gsd, erro = None, None
        try:
            gsd = vc.georreferencia_da_imagem(imagem).gsd_m
        except vc.ErroVisao as e:  # validar não exige georreferência; a auditoria exige
            erro = str(e)
        v.imagens.append(ResultadoImagem(
            imagem.name, len(dets),
            statistics.fmean(d.confianca for d in dets) if dets else None, gsd, erro,
            gabarito.get(imagem.name)))
    v.avisos = diagnosticar(tarefa, v.metadados, v.imagens, vc.config()["modelo"]["gsd_maximo_m"])
    return v


def relatorio_md(v: Validacao, pasta_imagens: Path) -> str:
    m = v.metadados
    linhas = [
        "# Validação rápida do modelo de painéis solares",
        "",
        f"Gerado em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC por `python -m pipeline.validar_modelo`.",
        "",
        f"- Modelo: `{Path(v.arquivo_modelo).name}` · tarefa **{v.tarefa}** "
        f"({'máscara' if v.tarefa == 'segment' else 'caixa'}) · classes {m.get('classes')}",
        f"- Treino declarado no checkpoint: {m.get('data_treino')} · ultralytics {m.get('versao_ultralytics_treino')} "
        f"· dataset `{m.get('dataset_treino')}` · imgsz {m.get('imgsz')} · {m.get('epocas')} épocas",
        f"- Imagens: `{pasta_imagens}` ({len(v.imagens)})",
        "",
        f"- Imagens anotadas (revisão visual): `{v.pasta_anotadas}`",
        f"- Gabarito (`{GABARITO}`): {'sim' if v.com_gabarito else 'não — sem ele não há como medir falso positivo/negativo'}",
        "",
        "| imagem | detecções | esperado | confiança média | pixel (m) | georreferência |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for i in v.imagens:
        conf = f"{i.confianca_media:.2f}" if i.confianca_media is not None else "—"
        gsd = f"{i.gsd_m:.2f}" if i.gsd_m is not None else "—"
        esp = "—" if i.esperado is None else str(i.esperado)
        linhas.append(f"| {i.imagem} | {i.deteccoes} | {esp} | {conf} | {gsd} | {'ok' if i.erro_georref is None else 'ausente'} |")
    linhas += ["", "## Diagnóstico", ""]
    if v.veredito == "adequado":
        linhas.append("Nada óbvio para ajustar e gabarito conferido: **adequado para a área piloto** "
                      "(revisão rápida, sem mais tempo aqui).")
    elif v.veredito == "sanidade_ok_sem_gabarito":
        linhas.append("Sanidade ok, mas **sem gabarito não dá para afirmar qualidade**: confira as imagens "
                      f"anotadas em `{v.pasta_anotadas}` (ou crie `{GABARITO}`) antes de seguir.")
    else:
        linhas += ["Ajustar antes da área piloto:", ""] + [f"- {a}" for a in v.avisos]
    return "\n".join(linhas) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Revisão rápida do YOLO de painéis solares.")
    ap.add_argument("--imagens", required=True, help="pasta com imagens de amostra")
    ap.add_argument("--modelo", help="arquivo .pt (padrão: modelo.caminho em config/visao.yaml)")
    ap.add_argument("--conf", type=float, help="confiança mínima (padrão: config)")
    ap.add_argument("--saida", default=str(RELATORIO), help="relatório .md")
    args = ap.parse_args(argv)
    try:
        pasta = vc.caminho(args.imagens)
        v = validar(vc.resolver_caminho_modelo(args.modelo), pasta,
                    args.conf if args.conf is not None else vc.config()["modelo"]["confianca_minima"])
    except vc.ErroVisao as e:
        print(f"ERRO: {e}")
        return 2
    texto = relatorio_md(v, pasta)
    destino = Path(args.saida)
    ensure(destino.parent)
    destino.write_text(texto, encoding="utf-8")
    print(texto)
    print(f"relatório: {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
