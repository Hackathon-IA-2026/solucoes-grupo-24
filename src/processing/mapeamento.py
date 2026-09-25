"""Gera data/processed/mapeamento_subsistema_area.csv e confere o agrupamento com dados.

Uso: python -m src.processing.mapeamento

Fonte: config/mapeamento_areas.yaml (transcrição da especificação oficial da API de carga
do ONS). Verificação: para cada subsistema, soma(áreas) + perdas deve reproduzir a carga
global do próprio subsistema, semi-hora a semi-hora. O erro relativo vai para
docs/reports/mapeamento_fechamento.csv e é citado em docs/mapeamento_subsistema_area.md.
"""
import pandas as pd

from src.utils.banco_analitico import conectar
from src.utils.config import carregar
from src.utils.joins import ARQUIVO_MAPEAMENTO
from src.utils.paths import DOCS_REPORTS, RAW_ONS, ensure


def montar_tabela() -> pd.DataFrame:
    cfg = carregar("mapeamento_areas")
    sub = cfg["subsistemas"]
    linhas = []
    for cod, s in sub.items():  # o próprio subsistema também é uma "área" na API
        linhas.append({"cod_areacarga": cod, "nom_areacarga": s["nome"], "tipo": "subsistema",
                       "cod_subsistema_api": cod, "id_subsistema": s["id_subsistema"], "ufs": None})
    for cod, (sapi, nome, ufs) in cfg["areas"].items():
        linhas.append({"cod_areacarga": cod, "nom_areacarga": nome, "tipo": "area",
                       "cod_subsistema_api": sapi, "id_subsistema": sub[sapi]["id_subsistema"],
                       "ufs": ";".join(ufs)})
    for cod, sapi in cfg["perdas"].items():
        linhas.append({"cod_areacarga": cod, "nom_areacarga": f"Perdas {sub[sapi]['nome']}",
                       "tipo": "perdas", "cod_subsistema_api": sapi,
                       "id_subsistema": sub[sapi]["id_subsistema"], "ufs": None})
    df = pd.DataFrame(linhas)
    assert df["cod_areacarga"].is_unique
    return df


def verificar_fechamento(tab: pd.DataFrame) -> pd.DataFrame:
    """Erro relativo |soma(áreas+perdas) − subsistema| / subsistema, por subsistema e ano."""
    fonte = (RAW_ONS / "carga_verificada").as_posix()
    carga = conectar().sql(f"""
        SELECT cod_areacarga, din_referenciautc AS t, val_cargaglobal AS v
        FROM read_parquet('{fonte}/**/*.parquet', hive_partitioning=false, union_by_name=true)
    """).df()
    carga = carga.merge(tab[["cod_areacarga", "tipo", "cod_subsistema_api"]], on="cod_areacarga")
    alvo = carga[carga["tipo"] == "subsistema"].set_index(["cod_subsistema_api", "t"])["v"]
    partes = (carga[carga["tipo"] != "subsistema"]
              .groupby(["cod_subsistema_api", "t"])
              .agg(soma=("v", "sum"), n_partes=("v", "count")))
    j = partes.join(alvo.rename("subsistema"), how="inner").reset_index()
    j["ano"] = j["t"].str[:4]
    j["erro_rel"] = (j["soma"] - j["subsistema"]).abs() / j["subsistema"].abs()
    return (j.groupby(["cod_subsistema_api", "ano"])
             .agg(semi_horas=("erro_rel", "size"), n_partes_mediana=("n_partes", "median"),
                  erro_rel_mediano=("erro_rel", "median"), erro_rel_p99=("erro_rel", lambda s: s.quantile(.99)))
             .reset_index())


def main() -> None:
    tab = montar_tabela()
    ensure(ARQUIVO_MAPEAMENTO.parent)
    tab.to_csv(ARQUIVO_MAPEAMENTO, index=False)
    print(f"gravado {ARQUIVO_MAPEAMENTO} ({len(tab)} linhas)")
    fech = verificar_fechamento(tab)
    ensure(DOCS_REPORTS)
    fech.to_csv(DOCS_REPORTS / "mapeamento_fechamento.csv", index=False)
    print(fech.to_string(index=False))


if __name__ == "__main__":
    main()
