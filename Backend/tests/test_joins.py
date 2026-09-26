"""O cruzamento subsistema × área só pode acontecer por src/utils/joins.py."""
import pandas as pd
import pytest

from src.utils.joins import ARQUIVO_MAPEAMENTO, cruzar_subsistema_area
from src.utils.paths import RAIZ


def _exige_mapa():
    if not ARQUIVO_MAPEAMENTO.exists():
        pytest.skip("mapeamento não gerado: rode python -m src.processing.mapeamento")


def test_nenhum_outro_modulo_le_o_mapeamento_direto():
    # joins.py lê; mapeamento.py é quem gera o arquivo (e importa o caminho de joins.py)
    permitidos = {RAIZ / "src/utils/joins.py", RAIZ / "src/processing/mapeamento.py"}
    culpados = [p for p in (RAIZ / "src").rglob("*.py")
                if p not in permitidos and "mapeamento_subsistema_area.csv" in p.read_text(encoding="utf-8")]
    assert culpados == [], f"leitura direta do mapeamento fora de joins.py: {culpados}"


def test_traduz_codigo_da_api_para_codigo_do_portal():
    _exige_mapa()
    df = pd.DataFrame({"s": ["SECO", "S", "NE", "N"]})
    out = cruzar_subsistema_area(df, "s", de="cod_subsistema_api", para="id_subsistema")
    assert list(out["id_subsistema"]) == ["SE", "S", "NE", "N"]


def test_uf_ambigua_nao_e_atribuida_em_silencio():
    _exige_mapa()
    df = pd.DataFrame({"uf": ["BA", "CE"]})
    with pytest.raises(ValueError, match="ambígua"):
        cruzar_subsistema_area(df, "uf", de="uf", para="cod_areacarga")
    out = cruzar_subsistema_area(df, "uf", de="uf", para="cod_areacarga", ambiguos="marcar")
    assert out["cod_areacarga"].isna().iloc[0] and out["cod_areacarga_ambiguo"].iloc[0]
    assert out["cod_areacarga"].iloc[1] == "CE"


def test_valor_desconhecido_falha():
    _exige_mapa()
    with pytest.raises(ValueError, match="fora do mapeamento"):
        cruzar_subsistema_area(pd.DataFrame({"a": ["XX"]}), "a", de="cod_areacarga", para="id_subsistema")
