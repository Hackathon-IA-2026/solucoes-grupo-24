"""Harness de integração ponta a ponta: bases ONS → modelos → JSON do contrato → dashboard → alerta.

Uso (de dentro de Backend/):
    python -m pipeline.teste_e2e            # relatório no terminal + docs/reports/teste_e2e.md

QUANDO O TIAGO ENTREGAR A SAÍDA REAL (TFT, classificadores, excedentes): não há chave para
trocar. A publicação (src/publicacao/montar.py) passa a gravar `mock: false` nos recursos que
ficaram reais, e este relatório — que LÊ a flag de cada registro — muda sozinho de "mock" para
"real". O dashboard não muda nada: ele consome a API, que valida tudo contra o mesmo contrato.
(O pedido original previa um data_sources_config.json com "mock"/"real" escrito à mão por
etapa; foi trocado por config/e2e.yaml só com caminhos, porque uma chave manual pode dizer
"real" enquanto o dado diz mock:true — o relatório mentiria. Ver o cabeçalho de config/e2e.yaml.)

Etapas e como o status é decidido:
| etapa      | real quando                                   | mock/ausente quando                   |
|------------|-----------------------------------------------|---------------------------------------|
| bases ONS  | as tabelas processadas existem                | faltam (máquina sem os dados)         |
| modelos    | os diretórios de modelos existem              | faltam                                |
| contrato   | registros com mock:false                      | mock:true (ou só os mocks do dashboard)|
| dashboard  | o contrato valida no espelho Pydantic (o mesmo da API) e alerta↔risco batem              |
| alerta     | texto gerado pelo pipeline, coerente com o risco (probabilidade e MW)                     |
| auditoria  | saída real da auditoria (is_mock:false)       | roda o fluxo mock das camadas 1→2/3   |

Cenário "dia_dos_pais_2024" (prova documental): o dia em que o ONS comandou pela primeira vez a
restrição total de eólicas e fotovoltaicas por baixa demanda. Com as bases na máquina, extrai do
dado REAL a carga supervisionada mínima do SIN e a fração de usinas com corte por semi-hora; sem
elas, mostra só os valores de referência do PAR/PEL 2025, rotulados como tal (nada é estimado).
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.utils.config import carregar
from src.utils.log import console_utf8
from src.utils.paths import DASHBOARD_MOCK, RAIZ, RAIZ_REPO, ensure

CABECALHO_ALERTA = "⚠ ALERTA — Risco de Curtailment"


@dataclass
class Etapa:
    nome: str
    status: str            # real | mock | parcial | ausente | ok | erro
    origem: str
    detalhes: list[str] = field(default_factory=list)


def _cfg() -> dict[str, Any]:
    return carregar("e2e")


def _abs(rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else RAIZ / p


def _rel(p: Path) -> str:
    """Caminho relativo à raiz do repositório (o relatório é compartilhado: nada de C:\\Users\\...)."""
    try:
        return Path(p).resolve().relative_to(RAIZ_REPO).as_posix()
    except ValueError:
        return str(p)


def _mw(v: float) -> str:
    """39024.3 -> "39.024" (milhar com ponto, pt-BR), só no número — nunca no texto em volta."""
    return f"{v:,.0f}".replace(",", ".")


def _eh_mock(valor: Any) -> list[bool]:
    itens = valor if isinstance(valor, list) else [valor]
    return [bool(i.get("mock")) for i in itens]


# --------------------------------------------------------------------------- etapas
def etapa_artefatos(nome: str, cfg_etapa: dict[str, Any]) -> Etapa:
    """Etapa que é real quando todos os artefatos existem (tabelas processadas, modelos)."""
    presentes = {a: _abs(a).exists() for a in cfg_etapa["artefatos"]}
    faltam = [a for a, ok in presentes.items() if not ok]
    status = "real" if not faltam else ("parcial" if len(faltam) < len(presentes) else "ausente")
    detalhes = [f"{'ok   ' if ok else 'falta'} {a}" for a, ok in presentes.items()]
    if faltam:
        detalhes.append("-> rode `python run_heavywork.py` nesta máquina (dados do ONS)")
    return Etapa(nome, status, cfg_etapa["descricao"], detalhes)


def mocks_do_dashboard() -> dict[str, Any]:
    """Os recursos do contrato a partir dos mocks do dashboard (mesmos arquivos da publicação).

    Reaproveita ler_mock() da publicação (DRY): item sem "mock": true derruba a leitura.
    """
    from src.contrato.modelos import RECURSOS
    from src.publicacao.montar import ler_mock

    return {r: ler_mock(r) for r in RECURSOS}


def carregar_contrato(cfg: dict[str, Any], bases_ok: bool, modelos_ok: bool) -> tuple[dict[str, Any], str]:
    """Contrato publicado > contrato montado agora > mocks do dashboard (nessa ordem)."""
    arq = _abs(cfg["etapas"]["contrato"]["arquivo"])
    if arq.exists():
        return json.loads(arq.read_text(encoding="utf-8"))["recursos"], _rel(arq)
    if bases_ok and modelos_ok:
        from src.publicacao.montar import montar_contrato

        recursos, _ = montar_contrato()
        return recursos, "montar_contrato() (publicação sem gravar no banco)"
    return mocks_do_dashboard(), f"mocks do dashboard ({_rel(DASHBOARD_MOCK)})"


def etapa_contrato(recursos: dict[str, Any], origem: str) -> Etapa:
    detalhes, flags = [], []
    for nome, valor in recursos.items():
        f = _eh_mock(valor)
        flags += f
        n_mock = sum(f)
        rotulo = "real" if n_mock == 0 else ("mock" if n_mock == len(f) else "parcial")
        detalhes.append(f"{nome:15s} {rotulo:7s} ({len(f)} registro(s), {n_mock} com mock:true)")
    status = "real" if not any(flags) else ("mock" if all(flags) else "parcial")
    return Etapa("contrato JSON", status, origem, detalhes)


def etapa_dashboard(recursos: dict[str, Any]) -> Etapa:
    """Valida cada registro no espelho Pydantic do contrato (o mesmo que a API usa)."""
    from pydantic import ValidationError

    from src.contrato.modelos import RECURSOS

    erros = []
    for nome, definicao in RECURSOS.items():
        if nome not in recursos:
            erros.append(f"recurso ausente no contrato: {nome}")
            continue
        itens = recursos[nome] if definicao.lista else [recursos[nome]]
        for i, item in enumerate(itens):
            try:
                definicao.modelo.model_validate(item)
            except ValidationError as e:
                erros.append(f"{nome}[{i}]: {e.errors()[0]['msg']} em {e.errors()[0]['loc']}")
    ids_risco = {r["id"] for r in recursos.get("riscos", [])}
    orfaos = [a["riscoUsinaId"] for a in recursos.get("alertas", []) if a["riscoUsinaId"] not in ids_risco]
    if orfaos:
        erros.append(f"alertas sem risco correspondente (Detalhe do Alerta daria 'não encontrado'): {orfaos}")
    detalhes = erros or [f"{len(RECURSOS)} recursos validam no contrato; todo alerta aponta para um risco"]
    return Etapa("dashboard (contrato)", "erro" if erros else "ok", "src/contrato/modelos.py (espelho do types.ts)", detalhes)


def etapa_alerta(recursos: dict[str, Any]) -> Etapa:
    """Texto do alerta coerente com o risco: cabeçalho, probabilidade e montante do mesmo registro."""
    riscos = {r["id"]: r for r in recursos.get("riscos", [])}
    alertas = recursos.get("alertas", [])
    if not alertas:
        return Etapa("alerta", "ausente", "recurso alertas", ["contrato sem alertas"])
    problemas = []
    for a in alertas:
        texto, r = a["textoAlerta"], riscos.get(a["riscoUsinaId"])
        if not texto.startswith(CABECALHO_ALERTA):
            problemas.append(f"{a['riscoUsinaId']}: texto sem o cabeçalho padrão")
        if r and f"{round(r['probabilidadePct'])}%" not in texto:
            problemas.append(f"{a['riscoUsinaId']}: probabilidade do texto ≠ do risco ({r['probabilidadePct']}%)")
    flags = [bool(a.get("mock")) for a in alertas]
    status = "erro" if problemas else ("mock" if all(flags) else "real" if not any(flags) else "parcial")
    exemplo = alertas[0]["textoAlerta"].splitlines()
    return Etapa("alerta", status, "pipeline/explicabilidade.py::gerar_texto_alerta",
                 problemas or [f"{len(alertas)} alertas coerentes com os riscos; exemplo:"] + [f"  {l}" for l in exemplo])


def etapa_auditoria(cfg: dict[str, Any]) -> Etapa:
    """Saída real da auditoria da MMGD, se existir; senão exercita o fluxo mock 1 → 2/3."""
    arq_real = _abs(cfg["etapas"]["auditoria"]["arquivo_real"])
    if arq_real.exists():
        r = json.loads(arq_real.read_text(encoding="utf-8"))
        origem, status = _rel(arq_real), "mock" if r.get("is_mock") else "real"
    else:
        from pipeline import auditoria_camada1, auditoria_camadas_2_3

        auditoria_camada1.executar(mock=True)
        destino = auditoria_camadas_2_3.executar(mock=True)
        r = json.loads(destino.read_text(encoding="utf-8"))
        origem, status = f"fluxo mock (camada 1 sintética + BDGD/ANEEL mock) -> {_rel(destino)}", "mock"
    detalhes = [f"classificação: {r['resumo']}"] + [
        f"{m['mancha']}: fator {m['fator_correcao']} ({m['capacidade_auditada_kw']} / {m['capacidade_cadastrada_bdgd_kw']} kW)"
        for m in r["manchas"]]
    detalhes.append(f"não homologadas (exceção, fora do fator): {r['excecoes_nao_homologadas']}")
    return Etapa("auditoria MMGD", status, origem, detalhes)


# --------------------------------------------------------------------------- cenário
def cenario_dia_dos_pais(cfg_cen: dict[str, Any], carga_csv: Path, rotulos_parquet: Path) -> dict[str, Any]:
    """Carga supervisionada mínima e restrição generalizada no dia, a partir do dado real."""
    dia = date.fromisoformat(cfg_cen["data"])
    ref = cfg_cen["referencia"]
    linhas = [f"Referência documental ({ref['fonte']}): carga supervisionada mínima "
              f"{_mw(ref['carga_supervisionada_minima_mw'])} MW; MMGD instalada {_mw(ref['mmgd_instalada_mw'])} MW."]
    resultado: dict[str, Any] = {"data": dia.isoformat(), "real": {}, "linhas": linhas}

    # split do classificador: o dia cai no treino? (então previsão do modelo seria in-sample)
    split = carregar("modelos_curtailment")["split"]
    if split["inicio_treino"][:10] <= dia.isoformat() <= split["fim_treino"][:10]:
        linhas.append(f"Atenção: {dia} está DENTRO do treino do classificador ({split['inicio_treino'][:10]} → "
                      f"{split['fim_treino'][:10]}): o que o modelo disser deste dia é in-sample — serve como caso "
                      "documentado, não como backtest.")

    if carga_csv.exists():
        import pandas as pd

        c = pd.read_csv(carga_csv, usecols=["subsistema", "timestamp", "carga_supervisionada", "mmgd_estimada"],
                        parse_dates=["timestamp"])
        c = c[c["timestamp"].dt.date == dia]
        completos = c.groupby("timestamp").filter(lambda g: g["carga_supervisionada"].notna().sum() == 4)
        sin = completos.groupby("timestamp")[["carga_supervisionada", "mmgd_estimada"]].sum()
        if len(sin):
            t_min = sin["carga_supervisionada"].idxmin()
            v_min = float(sin.loc[t_min, "carga_supervisionada"])
            resultado["real"]["carga_supervisionada_minima_mw"] = round(v_min, 1)
            resultado["real"]["instante_minimo"] = t_min.strftime("%H:%M")
            dif = v_min - ref["carga_supervisionada_minima_mw"]
            linhas.append(f"Dado real (carga verificada do ONS, SIN = 4 subsistemas, média de 30 min): mínima de "
                          f"{_mw(v_min)} MW às {t_min:%H:%M}; MMGD estimada {_mw(sin.loc[t_min, 'mmgd_estimada'])} MW "
                          f"(diferença de {'+' if dif >= 0 else '−'}{_mw(abs(dif))} MW para a referência, que é valor instantâneo).")
        else:
            linhas.append(f"carga_supervisionada.csv não tem o SIN completo em {dia}.")
    else:
        linhas.append("Carga real indisponível nesta máquina (falta data/processed/carga_supervisionada.csv).")

    if rotulos_parquet.exists():
        import pandas as pd

        ini = pd.Timestamp(dia)
        r = pd.read_parquet(rotulos_parquet, filters=[("timestamp", ">=", ini), ("timestamp", "<", ini + timedelta(days=1))])
        flags = [col for col in r.columns if col.startswith("flag_")]
        cortes = [col for col in r.columns if col.startswith("corte_MW_")]
        r["cortando"] = r[flags].fillna(False).any(axis=1)
        por = r.groupby("timestamp").agg(usinas=("chave", "nunique"), cortando=("cortando", "sum"),
                                         **{c: (c, "sum") for c in cortes})
        por["fracao"] = por["cortando"] / por["usinas"]
        limiar = cfg_cen["limiar_fracao_usinas_cortadas"]
        gerais = por[por["fracao"] >= limiar]
        t_max = por["fracao"].idxmax()
        resultado["real"].update({
            "fracao_maxima_usinas_cortadas": round(float(por["fracao"].max()), 3),
            "instante_fracao_maxima": t_max.strftime("%H:%M"),
            "semi_horas_restricao_generalizada": int(len(gerais)),
            **{f"{c}_max": round(float(por[c].max()), 1) for c in cortes},
        })
        linhas.append(f"Dado real (bases tm de constrained-off): até {por['fracao'].max():.0%} das usinas com corte "
                      f"na mesma semi-hora ({t_max:%H:%M}); {len(gerais)} semi-hora(s) com ≥ {limiar:.0%} das usinas "
                      f"cortando; " + ", ".join(f"{c.removeprefix('corte_MW_')} máx. {_mw(por[c].max())} MWmed" for c in cortes) + ".")
    else:
        linhas.append("Rótulos de curtailment indisponíveis nesta máquina (falta data/processed/rotulos_curtailment.parquet).")

    resultado["status"] = "real" if resultado["real"] else "indisponível (só referência documental)"
    return resultado


# --------------------------------------------------------------------------- relatório
def executar(saida: Path | None = None) -> tuple[list[Etapa], dict[str, Any], Path]:
    cfg = _cfg()
    bases = etapa_artefatos("bases ONS", cfg["etapas"]["bases_ons"])
    modelos = etapa_artefatos("modelos", cfg["etapas"]["modelos"])
    recursos, origem = carregar_contrato(cfg, bases.status == "real", modelos.status == "real")
    etapas = [bases, modelos, etapa_contrato(recursos, origem), etapa_dashboard(recursos),
              etapa_alerta(recursos), etapa_auditoria(cfg)]
    art = cfg["etapas"]["bases_ons"]["artefatos"]
    cenario = cenario_dia_dos_pais(cfg["cenarios"]["dia_dos_pais_2024"], _abs(art[0]), _abs(art[1]))
    destino = saida or _abs(cfg["relatorio"])
    ensure(destino.parent)
    destino.write_text(relatorio_md(etapas, cenario), encoding="utf-8")
    return etapas, cenario, destino


def relatorio_md(etapas: list[Etapa], cenario: dict[str, Any]) -> str:
    linhas = [
        "# Teste ponta a ponta (bases ONS → modelos → contrato → dashboard → alerta)",
        "",
        f"Gerado em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC por `python -m pipeline.teste_e2e`. "
        "O status de cada etapa é LIDO dos dados (existência e flag `mock`), não declarado em config.",
        "",
        "| etapa | status | origem |",
        "|---|---|---|",
        *[f"| {e.nome} | **{e.status}** | {e.origem} |" for e in etapas],
        "",
    ]
    for e in etapas:
        linhas += [f"## {e.nome} — {e.status}", "", "```", *e.detalhes, "```", ""]
    linhas += [f"## Cenário dia_dos_pais_2024 ({cenario['data']}) — {cenario['status']}", "",
               *[f"- {l}" for l in cenario["linhas"]], ""]
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    console_utf8()
    ap = argparse.ArgumentParser(description="Harness ponta a ponta do O.R.A.C.U.L.O.")
    ap.add_argument("--saida", help="relatório .md (padrão: relatorio em config/e2e.yaml)")
    args = ap.parse_args(argv)
    etapas, cenario, destino = executar(Path(args.saida) if args.saida else None)
    largura = max(len(e.nome) for e in etapas)
    for e in etapas:
        print(f"{e.nome:{largura}s}  {e.status:8s}  {e.origem}")
        for d in e.detalhes:
            print(f"{'':{largura}s}    {d}")
    print(f"\ncenário dia_dos_pais_2024: {cenario['status']}")
    for l in cenario["linhas"]:
        print(f"  - {l}")
    print(f"\nrelatório: {destino}")
    return 1 if any(e.status == "erro" for e in etapas) else 0


if __name__ == "__main__":
    raise SystemExit(main())
