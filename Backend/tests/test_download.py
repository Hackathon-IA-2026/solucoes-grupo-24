"""Testes das partes puras do download (sem rede)."""
import math
from datetime import date

import pytest

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


# --------------------------------------------------------------------------- atualização
from datetime import datetime, timedelta, timezone  # noqa: E402

import duckdb  # noqa: E402

from src.ingestion.download import precisa_baixar, sql_consolidacao, vencido  # noqa: E402

REC = {"nome": "X_2026_08.parquet", "url": "u", "tamanho": 100, "modificado": "2026-09-01T00:00:00"}


def test_arquivo_novo_ou_que_falhou_e_baixado():
    assert precisa_baixar(None, REC) == "novo"
    assert precisa_baixar({"status": "erro: timeout"}, REC) == "falhou antes"


def test_arquivo_em_dia_nao_e_rebaixado():
    info = {"status": "ok", "bytes": 100, "portal_tamanho": 100, "portal_modificado": REC["modificado"]}
    assert precisa_baixar(info, REC) is None


def test_arquivo_republicado_no_portal_e_rebaixado():
    info = {"status": "ok", "bytes": 100, "portal_tamanho": 100, "portal_modificado": "2026-08-01T00:00:00"}
    assert precisa_baixar(info, REC) == "republicado no portal"
    assert precisa_baixar({**info, "portal_modificado": REC["modificado"], "portal_tamanho": 90}, REC) \
        == "tamanho mudou no portal"


def test_compara_portal_com_portal_e_nao_com_bytes_do_disco():
    # O CKAN pode informar um `size` que não bate com os bytes servidos. Se comparássemos portal
    # x disco, esse arquivo seria rebaixado em TODA execução. Portal x portal: em dia.
    info = {"status": "ok", "bytes": 97, "portal_tamanho": 100, "portal_modificado": REC["modificado"]}
    assert precisa_baixar(info, REC) is None


def test_registro_antigo_sem_metadados_do_portal():
    assert precisa_baixar({"status": "ok", "bytes": 100}, REC) is None  # só anota os metadados
    assert precisa_baixar({"status": "ok", "bytes": 80}, REC) == "tamanho difere do baixado"


def test_vencido():
    agora = datetime(2026, 9, 25, tzinfo=timezone.utc)
    assert not vencido((agora - timedelta(days=2)).isoformat(), 7, agora)
    assert vencido((agora - timedelta(days=8)).isoformat(), 7, agora)
    assert not vencido(None, None, agora)  # fonte que não expira
    assert vencido(None, 7, agora)         # sem data registrada: rebaixa


def test_consolidacao_mes_rebaixado_substitui_e_nao_duplica(tmp_path):
    """O mês republicado entra no lugar do antigo; os outros meses do consolidado ficam."""
    con = duckdb.connect()
    final = tmp_path / "consolidado"
    (final / "id_ons=U1").mkdir(parents=True)
    con.execute(f"""COPY (SELECT * FROM (VALUES
        (TIMESTAMP '2026-07-01 00:00', 1.0), (TIMESTAMP '2026-08-01 00:00', 2.0),
        (TIMESTAMP '2026-08-01 00:30', 3.0)) t(din_instante, val))
        TO '{(final / 'id_ons=U1' / 'a.parquet').as_posix()}' (FORMAT parquet)""")
    novo = tmp_path / "novo_2026_08.parquet"  # agosto republicado: 3 linhas, valores novos
    con.execute(f"""COPY (SELECT * FROM (VALUES
        ('U1', TIMESTAMP '2026-08-01 00:00', 20.0), ('U1', TIMESTAMP '2026-08-01 00:30', 30.0),
        ('U1', TIMESTAMP '2026-08-01 01:00', 40.0)) t(id_ons, din_instante, val))
        TO '{novo.as_posix()}' (FORMAT parquet)""")
    df = con.sql(sql_consolidacao(final, [novo.as_posix()])).df().sort_values("din_instante")
    assert len(df) == 4                              # 1 de julho + 3 de agosto (não 6)
    assert df["val"].tolist() == [1.0, 20.0, 30.0, 40.0]  # agosto é todo da versão nova
    assert not df.duplicated(["id_ons", "din_instante"]).any()


def test_rebaixar_conteudo_identico_nao_muda_a_impressao_digital():
    """A carga recente é rebaixada em toda execução; se a hora do download entrasse na
    impressão, o processamento seria refeito sempre. Só o conteúdo conta."""
    from src.ingestion.download import _versao
    antes = {"status": "ok", "conteudo": "abc", "bytes": 10, "baixado_em": "2026-09-25T10:00:00+00:00"}
    depois = {**antes, "baixado_em": "2026-09-25T11:00:00+00:00"}
    assert _versao(antes) == _versao(depois)
    assert _versao(antes) != _versao({**depois, "conteudo": "def"})


# --------------------------------------------------------------------------- status das fontes
def _manifesto(tmp_path, itens):
    import json
    arq = tmp_path / "_manifesto.json"
    arq.write_text(json.dumps(itens), encoding="utf-8")
    return arq


def test_status_fontes_agrupa_e_usa_o_download_mais_recente(tmp_path, monkeypatch):
    from src.ingestion import download
    monkeypatch.setattr(download, "MANIFESTO_PATH", _manifesto(tmp_path, {
        "a/1": {"conjunto": "a", "status": "ok", "baixado_em": "2026-09-20T10:00:00+00:00"},
        "a/2": {"conjunto": "a", "status": "ok", "baixado_em": "2026-09-25T10:00:00+00:00"},
        "b/1": {"conjunto": "b", "status": "erro: 500", "baixado_em": "2026-09-24T10:00:00+00:00"},
    }))
    st = {s["fonte"]: s for s in download.status_fontes({"A": ["a"], "B": ["b"]})}
    assert st["A"]["online"] and st["A"]["ultima_sincronizacao"].day == 25
    assert not st["B"]["online"]


def test_status_fontes_cobre_todas_as_fontes_declaradas():
    """As configs REAIS batem: toda fonte de fontes_ons.yaml tem grupo em publicacao.yaml.

    Sem este teste, fonte nova (ex.: BDGD, malhas do IBGE) só falhava na publicação, no fim
    de ~70 min de run_heavywork.
    """
    from src.ingestion import download
    from src.utils.config import carregar
    download.validar_grupos_fontes(carregar("publicacao")["status_fontes"])


def test_validar_grupos_fontes_recusa_sem_grupo_e_desconhecido(monkeypatch):
    from src.ingestion import download
    monkeypatch.setattr(download, "conjuntos_declarados", lambda: {"a", "b"})
    download.validar_grupos_fontes({"A": ["a"], "B": ["b"]})
    with pytest.raises(ValueError, match="sem grupo.*'b'"):
        download.validar_grupos_fontes({"A": ["a"]})
    with pytest.raises(ValueError, match="não existem.*'x'"):
        download.validar_grupos_fontes({"A": ["a", "b", "x"]})


def test_status_fontes_recusa_conjunto_sem_grupo(tmp_path, monkeypatch):
    from src.ingestion import download
    monkeypatch.setattr(download, "MANIFESTO_PATH", _manifesto(tmp_path, {
        "novo/1": {"conjunto": "novo", "status": "ok", "baixado_em": "2026-09-25T10:00:00+00:00"}}))
    with pytest.raises(ValueError, match="sem grupo"):
        download.status_fontes({"A": ["a"]})


def test_arquivo_direto_rebaixa_quando_a_url_muda(tmp_path, monkeypatch):
    """Nova edição da BDGD: mesma chave de destino não pode esconder a URL nova (o fim da URL
    do ArcGIS é sempre ".../data", e a chave antiga derivada dela não mudava)."""
    from src.ingestion import download
    monkeypatch.setattr(download, "RAIZ", tmp_path)
    (tmp_path / "x.zip").write_bytes(b"1")
    a = {"apelido": "bdgd_x", "url": "https://h/items/NOVO/data", "destino": "x.zip"}
    info = {"status": "ok", "caminho": "x.zip", "url": "https://h/items/VELHO/data", "baixado_em": None}
    assert download.chave_direta(a) == "bdgd_x/x.zip"
    assert download.precisa_baixar_direto(a, info) == "URL mudou na config"
    assert download.precisa_baixar_direto(a, {**info, "url": a["url"]}) is None  # sem validade: não expira
    assert download.precisa_baixar_direto(a, None) == "ausente"
    (tmp_path / "x.zip").unlink()
    assert download.precisa_baixar_direto(a, {**info, "url": a["url"]}) == "arquivo sumiu do disco"
