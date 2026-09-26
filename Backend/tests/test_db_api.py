"""Banco (SQLAlchemy + Alembic) e API FastAPI, num SQLite temporário."""
import json
import subprocess
import sys
from datetime import datetime, timezone

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from fastapi.testclient import TestClient

from src.api.app import criar_app
from src.db import migracoes, repositorio
from src.db.sessao import engine, nova_sessao
from src.db.tabelas import Base
from src.utils.paths import DASHBOARD_MOCK, RAIZ

from src.contrato.modelos import RECURSOS


@pytest.fixture
def banco(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 't.db').as_posix()}")
    return tmp_path


def _recursos():
    return {r: json.loads((DASHBOARD_MOCK / f"{r}.json").read_text(encoding="utf-8")) for r in RECURSOS}


def _publicar(recursos=None):
    migracoes.atualizar_banco()
    with nova_sessao() as s:
        return repositorio.publicar(s, recursos or _recursos(),
                                    datetime(2026, 9, 25, 2, 30, tzinfo=timezone.utc), "teste")


def test_migrations_batem_com_os_modelos(banco):
    """Mudou src/db/tabelas.py sem gerar migration -> falha aqui, não em produção."""
    migracoes.atualizar_banco()
    with engine().connect() as c:
        diff = compare_metadata(MigrationContext.configure(c, opts={"render_as_batch": True}),
                                Base.metadata)
    assert diff == []


def test_api_sem_publicacao_responde_503_com_instrucao(banco):
    r = TestClient(criar_app()).get("/api/carga/snapshot")
    assert r.status_code == 503 and "run_heavywork.py" in r.json()["detail"]


def test_api_serve_exatamente_o_que_foi_publicado(banco):
    _publicar()
    cli, esperado = TestClient(criar_app()), _recursos()
    assert cli.get("/api/carga/snapshot").json() == esperado["carga"]
    assert cli.get("/api/previsao").json() == esperado["previsao"]
    assert cli.get("/api/riscos").json() == esperado["riscos"]
    assert cli.get("/api/excedentes").json() == esperado["excedentes"]
    assert cli.get("/api/validacao").json() == esperado["validacao"]
    alvo = esperado["alertas"][0]
    assert cli.get(f"/api/alertas/{alvo['riscoUsinaId']}").json() == alvo
    assert cli.get("/api/alertas/nao-existe").status_code == 404


def test_api_serve_a_execucao_mais_recente(banco):
    _publicar()
    novo = _recursos()
    mmgd = novo["carga"]["mmgdEstimadaMw"]
    novo["carga"] = {**novo["carga"], "cargaGlobalMw": 60000, "cargaSupervisionadaMw": 60000 - mmgd}
    ultima = _publicar(novo)
    cli = TestClient(criar_app())
    assert cli.get("/api/carga/snapshot").json()["cargaGlobalMw"] == 60000
    assert cli.get("/api/saude").json()["execucaoId"] == ultima


def test_instantes_voltam_do_banco_com_fuso_utc(banco):
    """SQLite não guarda fuso; o tipo UtcDateTime garante tz=UTC na leitura."""
    _publicar()
    with nova_sessao() as s:
        e = repositorio.ultima_execucao(s)
    assert e.instante_referencia == datetime(2026, 9, 25, 2, 30, tzinfo=timezone.utc)
    assert e.gerado_em.tzinfo is not None
    saude = TestClient(criar_app()).get("/api/saude").json()
    assert saude["instanteReferencia"] == "2026-09-25T02:30:00Z" and saude["geradoEm"].endswith("Z")


def test_publicacao_recusa_dado_fora_do_contrato_e_nao_grava_nada(banco):
    ruim = _recursos()
    ruim["carga"] = {**ruim["carga"], "cargaSupervisionadaMw": 1.0}  # quebra global − MMGD
    with pytest.raises(Exception, match="cargaGlobalMw"):
        _publicar(ruim)
    with nova_sessao() as s:
        assert repositorio.ultima_execucao(s) is None  # nada pela metade no banco


def test_publicacao_recusa_recurso_faltando(banco):
    incompleto = _recursos()
    del incompleto["validacao"]
    with pytest.raises(ValueError, match="validacao"):
        _publicar(incompleto)


def test_publicacao_recusa_id_repetido(banco):
    dup = _recursos()
    dup["alertas"] = dup["alertas"] + dup["alertas"][:1]
    with pytest.raises(Exception):
        _publicar(dup)
    with nova_sessao() as s:
        assert repositorio.ultima_execucao(s) is None


def test_servico_web_nao_carrega_a_parte_pesada():
    """main.py num processo limpo: nenhum módulo de ingestão/processamento/modelos/pandas."""
    pesados = ["pandas", "duckdb", "numpy", "pyarrow", "lightgbm", "torch", "src.ingestion",
               "src.processing", "src.heavywork", "src.publicacao"]
    codigo = f"import sys, main; print([m for m in {pesados!r} if m in sys.modules])"
    saida = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True,
                           text=True, check=True).stdout.strip()
    assert saida == "[]", f"main.py carregou módulos pesados: {saida}"


def test_api_serve_o_build_do_dashboard_sem_engolir_a_api(banco, tmp_path):
    """Com dist/ presente: "/" e rotas do React Router devolvem o index.html; /api continua
    sendo a API; rota inexistente sob /api é 404 JSON (nunca HTML com 200); sem sair de dist/."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "segredo.txt").write_text("fora do dist", encoding="utf-8")
    _publicar()
    cli = TestClient(criar_app(dashboard_dist=dist))
    assert "id=root" in cli.get("/").text
    assert "id=root" in cli.get("/riscos").text  # rota do React Router, não arquivo
    assert cli.get("/assets/app.js").text == "console.log(1)"
    assert "fora do dist" not in cli.get("/..%2Fsegredo.txt").text
    assert cli.get("/api/carga/snapshot").json() == _recursos()["carga"]
    r = cli.get("/api/nao-existe")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")


def test_api_sem_build_do_dashboard_so_serve_a_api(banco, tmp_path):
    cli = TestClient(criar_app(dashboard_dist=tmp_path / "nao-buildado"))
    assert cli.get("/").status_code == 404


def test_saude_tem_a_forma_que_o_dashboard_valida(banco):
    """Mesmos campos de SaudeApiSchema (Frontend/.../types.ts), timestamps UTC com Z."""
    _publicar()
    s = TestClient(criar_app()).get("/api/saude").json()
    assert set(s) == {"status", "execucaoId", "geradoEm", "instanteReferencia", "origem"}
    assert s["status"] == "ok" and s["instanteReferencia"] == "2026-09-25T02:30:00Z"


def test_execucao_de_contrato_anterior_responde_503_com_instrucao(banco):
    """Banco publicado antes de uma mudança do contrato (campo novo ausente, recurso novo que a
    execução não tem): 503 dizendo para republicar, nunca um 500 de validação."""
    from sqlalchemy import delete, select

    from src.db.tabelas import Recurso
    _publicar()
    with nova_sessao() as s, s.begin():
        risco = s.scalars(select(Recurso).where(Recurso.tipo == "riscos").limit(1)).one()
        risco.payload = {k: v for k, v in risco.payload.items() if k not in ("lat", "lon")}
        s.execute(delete(Recurso).where(Recurso.tipo == "mmgd_densidade"))
    cli = TestClient(criar_app())
    for rota in ("/api/riscos", "/api/mmgd/densidade"):
        r = cli.get(rota)
        assert r.status_code == 503 and "run_heavywork.py" in r.json()["detail"], rota
    assert cli.get("/api/carga/snapshot").status_code == 200  # o resto continua servido


def test_toda_rota_do_contrato_existe_na_api(banco):
    _publicar()
    cli, esperado = TestClient(criar_app()), _recursos()
    for tipo, d in RECURSOS.items():
        if "{id}" in d.rota:
            continue
        assert cli.get(f"/api{d.rota}").json() == esperado[tipo], tipo
