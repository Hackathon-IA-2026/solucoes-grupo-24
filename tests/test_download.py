"""Testes das partes puras do download (sem rede)."""
import math
from datetime import date

from src.ingestion.download import carga_para_dataframe, destino_data, janelas

# Trecho real devolvido pela API de carga do ONS (SECO, 2016-01-01): campos vazios sem valor.
RESPOSTA_API = """[
  {
    "cod_areacarga": "SECO",
    "din_atualizacao":"2020-09-24T12:52:27.000Z",
    "din_referenciautc": "2016-01-01T02:30:00.000Z",
    "val_cargaglobal": 32604.021,
    "val_cargaglobalsmmgd": ,
    "val_cargammgd": ,
    "val_consistencia": 0
  },  {"cod_areacarga": "SECO", "val_cargammgd":}
]"""


def test_json_tolerante_vazio_vira_nulo_e_nao_zero():
    df = carga_para_dataframe(RESPOSTA_API)
    assert len(df) == 2
    assert math.isnan(df.loc[0, "val_cargammgd"])  # ausente, não inventado como 0
    assert df.loc[0, "val_cargaglobal"] == 32604.021
    assert df.loc[0, "val_consistencia"] == 0
    # timestamps com ':' dentro de strings não podem ser tocados
    assert df.loc[0, "din_referenciautc"] == "2016-01-01T02:30:00.000Z"


def test_janelas_cobrem_periodo_sem_buraco_nem_sobreposicao():
    js = janelas(date(2016, 1, 1), date(2016, 12, 15), 3)
    assert js[0] == (date(2016, 1, 1), date(2016, 3, 31))
    assert js[-1] == (date(2016, 10, 1), date(2016, 12, 15))
    for (_, fim), (ini_prox, _) in zip(js, js[1:]):
        assert (ini_prox - fim).days == 1


def test_destino_data_particiona_por_ano():
    assert destino_data("x", "RESTRICAO_COFF_EOLICA_2021_10.parquet").parent.name == "ano=2021"
    assert destino_data("x", "GERACAO_TERMICA_DESPACHO_2013.parquet").parent.name == "ano=2013"
    assert destino_data("x", "CAPACIDADE_GERACAO.parquet").parent.name == "x"
