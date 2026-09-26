"""Contrato Backend <-> dashboard: src/contrato/modelos.py espelha Frontend/.../types.ts."""
import json

import pytest
from pydantic import ValidationError

from src.contrato.modelos import RECURSOS, CargaSnapshot, PontoPrevisao
from src.utils.paths import DASHBOARD_MOCK, FRONTEND


@pytest.mark.parametrize("recurso", sorted(RECURSOS))
def test_mocks_do_dashboard_passam_no_contrato_do_backend_sem_mudar_nada(recurso):
    """Se o Luiz mudar um campo no types.ts (e nos mocks) ou nós mudarmos aqui, este teste
    falha: os dois lados do contrato não têm como divergir em silêncio."""
    modelo, e_lista, _ = RECURSOS[recurso]
    dados = json.loads((DASHBOARD_MOCK / f"{recurso}.json").read_text(encoding="utf-8"))
    itens = dados if e_lista else [dados]
    ida_e_volta = [modelo.model_validate(x).para_json() for x in itens]
    assert ida_e_volta == itens  # mesmos nomes de campo, mesmos valores, mesmo formato de data


@pytest.mark.parametrize("recurso", sorted(RECURSOS))
def test_rota_do_backend_e_a_mesma_do_dashboard(recurso):
    """A rota de cada recurso (RECURSOS) aparece em ENDPOINTS do dataSource.ts: um lado mudar
    o caminho sem o outro vira falha de teste, não um 404 na tela."""
    fonte = (FRONTEND / "oraculo-dashboard" / "src" / "data" / "dataSource.ts").read_text(encoding="utf-8")
    rota = RECURSOS[recurso].rota
    fixa = rota.split("{")[0]  # /alertas/{id} -> no dashboard: `/alertas/${...}`
    assert (f"'{rota}'" in fonte) if fixa == rota else (f"`{fixa}$" in fonte), rota


def test_posicao_fora_do_brasil_e_recusada():
    """lat/lon trocados (ou com sinal errado) não chegam ao Mapa Híbrido."""
    risco = json.loads((DASHBOARD_MOCK / "riscos.json").read_text(encoding="utf-8"))[0]
    with pytest.raises(ValidationError):
        RECURSOS["riscos"].modelo.model_validate({**risco, "lat": risco["lon"], "lon": risco["lat"]})


def test_validacao_com_teste_antes_do_fim_do_treino_e_recusada():
    val = json.loads((DASHBOARD_MOCK / "validacao.json").read_text(encoding="utf-8"))
    val["modelo"]["periodoTeste"]["inicio"] = val["modelo"]["periodoTreino"]["fim"]
    with pytest.raises(ValidationError, match="split cronológico"):
        RECURSOS["validacao"].modelo.model_validate(val)


CARGA_OK = dict(mock=False, timestamp_utc="2026-09-25T02:30:00Z", carga_global_mw=100.0,
                mmgd_estimada_mw=30.0, carga_supervisionada_mw=70.0,
                percentual_mmgd_na_geracao=30.0, mmgd_sobre_capacidade_instalada=0.5)


def test_carga_incoerente_e_recusada():
    with pytest.raises(ValidationError, match="cargaGlobalMw − mmgdEstimadaMw"):
        CargaSnapshot(**{**CARGA_OK, "carga_supervisionada_mw": 50.0})


def test_timestamp_sem_fuso_e_recusado_e_saida_sempre_em_utc_z():
    with pytest.raises(ValidationError, match="sem fuso"):
        CargaSnapshot(**{**CARGA_OK, "timestamp_utc": "2026-09-25T02:30:00"})
    c = CargaSnapshot(**{**CARGA_OK, "timestamp_utc": "2026-09-24T23:30:00-03:00"})
    assert c.para_json()["timestampUtc"] == "2026-09-25T02:30:00Z"


def test_quantis_cruzados_sao_recusados():
    with pytest.raises(ValidationError, match="quantis"):
        PontoPrevisao(timestamp="2026-09-25T00:00:00Z", p10=10, p50=5, p90=20)


def test_schema_documentado_esta_atualizado():
    """docs/schema_contrato.json é gerado dos modelos; mudou o modelo, regenere o arquivo."""
    from src.contrato.esquema import ARQUIVO, texto
    assert ARQUIVO.exists(), "rode: python -m src.contrato.esquema"
    assert ARQUIVO.read_text(encoding="utf-8") == texto(), \
        "docs/schema_contrato.json desatualizado; rode: python -m src.contrato.esquema"


def test_campo_desconhecido_e_recusado():
    with pytest.raises(ValidationError):
        CargaSnapshot(**CARGA_OK, campo_novo=1)
