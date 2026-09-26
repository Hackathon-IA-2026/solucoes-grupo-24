"""Orquestrador do run_heavywork.py com etapas falsas (sem rede, sem dados)."""
import pytest

from src.heavywork.orquestrador import Estado, Etapa, rodar, validar_config


class Contador:
    """Função de etapa que conta chamadas; `falhar=True` levanta erro."""

    def __init__(self, falhar=False):
        self.n, self.falhar = 0, falhar

    def __call__(self):
        self.n += 1
        if self.falhar:
            raise RuntimeError("quebrou")
        return "ok"


def status(resultados):
    return {r.nome: r.status for r in resultados}


def test_roda_na_primeira_vez_e_pula_quando_nada_mudou(tmp_path):
    f = Contador()
    etapa = [Etapa("proc", "d", executar=f, entradas=lambda: "v1")]
    assert status(rodar(etapa, Estado.ler(tmp_path / "e.json"))) == {"proc": "executada"}
    assert status(rodar(etapa, Estado.ler(tmp_path / "e.json"))) == {"proc": "pulada"}
    assert f.n == 1


def test_entrada_mudou_roda_de_novo(tmp_path):
    f, versao = Contador(), {"v": "v1"}
    etapa = [Etapa("proc", "d", executar=f, entradas=lambda: versao["v"])]
    rodar(etapa, Estado.ler(tmp_path / "e.json"))
    versao["v"] = "v2"
    assert status(rodar(etapa, Estado.ler(tmp_path / "e.json"))) == {"proc": "executada"}
    assert f.n == 2


def test_saida_apagada_roda_de_novo(tmp_path):
    saida = tmp_path / "tabela.csv"
    f = Contador()

    def gera():
        f()
        saida.write_text("x")

    etapa = [Etapa("proc", "d", executar=gera, entradas=lambda: "v1", saidas=(saida,))]
    rodar(etapa, Estado.ler(tmp_path / "e.json"))
    saida.unlink()
    assert status(rodar(etapa, Estado.ler(tmp_path / "e.json"))) == {"proc": "executada"}
    assert f.n == 2 and saida.exists()


def test_forcar_roda_mesmo_em_dia(tmp_path):
    f = Contador()
    etapa = [Etapa("proc", "d", executar=f, entradas=lambda: "v1")]
    rodar(etapa, Estado.ler(tmp_path / "e.json"))
    rodar(etapa, Estado.ler(tmp_path / "e.json"), forcar={"proc"})
    assert f.n == 2


def test_etapa_sem_entradas_sempre_roda(tmp_path):
    f = Contador()
    etapa = [Etapa("ingestao", "d", executar=f, entradas=None)]
    rodar(etapa, Estado.ler(tmp_path / "e.json"))
    rodar(etapa, Estado.ler(tmp_path / "e.json"))
    assert f.n == 2


def test_falha_interrompe_as_seguintes_e_nao_marca_como_concluida(tmp_path):
    depois = Contador()
    etapas = [Etapa("a", "d", executar=Contador(falhar=True), entradas=lambda: "v1"),
              Etapa("b", "d", executar=depois, entradas=lambda: "v1")]
    estado = Estado.ler(tmp_path / "e.json")
    assert status(rodar(etapas, estado)) == {"a": "falhou", "b": "nao_rodou"}
    assert depois.n == 0
    assert Estado.ler(tmp_path / "e.json").impressao("a") is None  # próxima execução tenta de novo


def test_nao_implementada_aparece_no_resumo_e_nao_bloqueia(tmp_path):
    f = Contador()
    etapas = [Etapa("treino", "futuro", executar=None),
              Etapa("proc", "d", executar=f, entradas=lambda: "v1")]
    assert status(rodar(etapas, Estado.ler(tmp_path / "e.json"))) == \
        {"treino": "nao_implementada", "proc": "executada"}


def test_desligada_no_config_nao_roda(tmp_path):
    f = Contador()
    etapas = [Etapa("proc", "d", executar=f, entradas=lambda: "v1")]
    assert status(rodar(etapas, Estado.ler(tmp_path / "e.json"), {"proc": False})) == {"proc": "desabilitada"}
    assert f.n == 0


def test_config_com_nome_de_etapa_errado_e_recusado():
    etapas = [Etapa("processamento", "d", executar=None)]
    with pytest.raises(ValueError, match="procesamento"):
        validar_config({"etapas": {"procesamento": False}}, etapas)
    with pytest.raises(ValueError):
        validar_config({"forcar": ["xyz"]}, etapas)
    assert validar_config({"etapas": {"processamento": False}, "forcar": []}, etapas) == \
        ({"processamento": False}, set())


def test_etapas_reais_batem_com_o_config():
    """config/heavywork.yaml e src/heavywork/etapas.py listam as mesmas etapas."""
    from src.heavywork.etapas import montar
    from src.utils.config import carregar
    ligadas, _ = validar_config(carregar("heavywork"), montar())
    assert set(ligadas) == set(carregar("heavywork")["etapas"])
