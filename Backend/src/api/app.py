"""Rotas da API. Uma por recurso do contrato, no formato exato de types.ts (via src/contrato).

Rotas (com o prefixo de config/api.yaml, padrão /api), GERADAS da tabela RECURSOS de
src/contrato/modelos.py — acrescentar recurso lá já cria a rota aqui:
    GET /carga/snapshot   -> CargaSnapshot
    GET /previsao         -> PrevisaoCurva[]   (os 3 horizontes; o dashboard filtra)
    GET /riscos           -> RiscoUsina[]
    GET /alertas/{id}     -> AlertaDetalhado   (404 se não houver alerta para o id)
    GET /excedentes       -> ExcedenteTsoDso[]
    GET /validacao        -> MetricasValidacao
    GET /mmgd/densidade   -> DensidadeMmgd
    GET /saude            -> estado do banco e da execução servida (fora do contrato)

Fora do prefixo: se o dashboard foi buildado (`npm run build` -> Frontend/.../dist, caminho em
config/api.yaml), o próprio serviço o entrega em "/" — demo com um servidor só, e o dashboard
chama /api na mesma origem (sem proxy e sem CORS).

Tudo vem da execução mais recente publicada pelo run_heavywork.py. Banco inexistente,
desatualizado ou vazio -> 503 com a instrução do que rodar, nunca um erro de SQL cru.
Execução publicada com um contrato ANTERIOR (campo novo ausente, recurso novo que ela não tem)
-> também 503 com a instrução de republicar, e não um 500 de validação: o contrato muda, e o
banco de quem ainda não rodou o run_heavywork.py depois da mudança continua legível.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from src.contrato.modelos import RECURSOS, DefRecurso
from src.db import migracoes, repositorio
from src.db.sessao import nova_sessao
from src.db.tabelas import Execucao
from src.utils.config import carregar
from src.utils.paths import RAIZ
from src.api.auditoria import rotas_auditoria
from src.api.conciliacao import rotas_conciliacao

INSTRUCAO = "rode `python run_heavywork.py` em Backend/ para publicar os dados no banco"


class Saude(BaseModel):
    """Resposta de /saude. Espelha `SaudeApiSchema` (Frontend/.../src/data/types.ts), que a
    pill "Dados de ..." da topbar valida; tipada aqui para a rota não mudar de forma sem aviso."""
    status: str
    execucaoId: int
    geradoEm: str
    instanteReferencia: str
    origem: str


def _sessao() -> Iterator[Session]:
    with nova_sessao() as s:
        yield s


def _execucao(sessao: Session = Depends(_sessao)) -> tuple[Session, Execucao]:
    """Execução mais recente; 503 explicado se o banco ainda não foi publicado."""
    if not migracoes.banco_em_dia():
        raise HTTPException(503, f"banco inexistente ou em versão antiga; {INSTRUCAO}")
    execucao = repositorio.ultima_execucao(sessao)
    if execucao is None:
        raise HTTPException(503, f"banco sem nenhuma publicação; {INSTRUCAO}")
    return sessao, execucao


def _conferido(tipo: str, forma, dado, execucao: Execucao):
    """Revalida o que saiu do banco contra o contrato ATUAL antes de responder.

    Mesmo um payload antigo no banco não sai fora do contrato: se não passar (ou se o recurso
    nem existir nessa execução), 503 dizendo para republicar.
    """
    try:
        return TypeAdapter(forma).validate_python(dado)
    except ValidationError as e:
        raise HTTPException(503, f"execução {execucao.id} publicada com um contrato anterior "
                                 f"({tipo}: {e.error_count()} campo(s) fora do atual); {INSTRUCAO}")


def _rota_recurso(r: APIRouter, tipo: str, d: DefRecurso) -> None:
    """Registra a rota de um recurso a partir da sua definição em RECURSOS."""
    if "{id}" in d.rota:  # item por id (alertas): 404 quando não houver
        @r.get(d.rota, response_model=d.modelo, name=tipo)
        def item(id: str, ctx=Depends(_execucao)):
            dado = repositorio.ler_item(ctx[0], tipo, id, ctx[1])
            if dado is None:  # o dashboard trata 404 como "sem item para este id"
                raise HTTPException(404, f"sem {tipo} para {id!r}")
            return _conferido(tipo, d.modelo, dado, ctx[1])
        return

    forma = list[d.modelo] if d.lista else d.modelo

    @r.get(d.rota, response_model=forma, name=tipo)
    def recurso(ctx=Depends(_execucao)):
        try:
            dado = repositorio.ler(ctx[0], tipo, ctx[1])
        except LookupError:  # recurso de objeto único ausente: execução anterior ao recurso
            dado = None
        return _conferido(tipo, forma, dado, ctx[1])


def _rotas() -> APIRouter:
    r = APIRouter()
    for tipo, definicao in RECURSOS.items():
        _rota_recurso(r, tipo, definicao)

    @r.get("/saude", response_model=Saude)
    def saude(ctx=Depends(_execucao)):
        _, e = ctx
        z = "%Y-%m-%dT%H:%M:%SZ"  # mesmo formato UTC dos timestamps do contrato
        return Saude(status="ok", execucaoId=e.id, geradoEm=e.gerado_em.strftime(z),
                     instanteReferencia=e.instante_referencia.strftime(z), origem=e.origem)

    return r


def criar_app(dashboard_dist: Path | None = None) -> FastAPI:
    """`dashboard_dist` só para testes; o padrão vem de config/api.yaml."""
    cfg = carregar("api")
    # Swagger em /api-docs: "/docs" é a documentação Sphinx do protótipo (ajuda F1 das telas).
    app = FastAPI(title="O.R.A.C.U.L.O. API",
                  description="Leitura dos recursos publicados pelo run_heavywork.py "
                              "(contrato: Frontend/oraculo-dashboard/src/data/types.ts), "
                              "auditoria da MMGD por visão computacional e os serviços do "
                              "protótipo O.R.A.C.U.L.O. (oraculo/: mapa, CLM, fronteira T–D, "
                              "BESS, projeção ENE, curva do pato).",
                  docs_url="/api-docs", redoc_url=None)
    # POST: as reconstruções do protótipo (fronteira, BESS, tempo) e a ingestão sob demanda.
    app.add_middleware(CORSMiddleware, allow_origins=cfg["cors_origens"],
                       allow_methods=["GET", "POST"], allow_headers=["*"])
    app.include_router(_rotas(), prefix=cfg["prefixo"])
    app.include_router(rotas_auditoria(), prefix=cfg["prefixo"])
    app.include_router(rotas_conciliacao(), prefix=cfg["prefixo"])
    _incluir_prototipo(app)
    dist = dashboard_dist if dashboard_dist is not None else RAIZ / cfg["dashboard_dist"]
    _servir_dashboard(app, dist.resolve(), cfg["prefixo"])
    return app


def _incluir_prototipo(app: FastAPI) -> None:
    """Rotas do protótipo O.R.A.C.U.L.O. (pacote `oraculo/`, Starlette) no mesmo servidor.

    Decisões:
    - As rotas do protótipo (/api/health, /api/mapa/..., /api/fronteira/..., /api/bess/...,
      /api/ene/..., /api/tempo/..., /api/clm/..., /docs, /legado) não colidem com as do
      contrato (/api/carga/snapshot, /api/previsao, /api/riscos, ... /api/saude).
    - Entram ANTES do dashboard: o catch-all do SPA nunca engole /docs nem /legado.
    - Import tardio e opcional: sem o pacote (checkout parcial), a API do contrato sobe igual.
    - O protótipo usa só numpy/scipy/httpx; nada da parte pesada (pandas, DuckDB) é carregado.
    """
    try:
        from oraculo.api.app import routes as rotas_oraculo
    except ImportError:  # pragma: no cover
        return
    app.router.routes.extend(rotas_oraculo)


def _servir_dashboard(app: FastAPI, dist: Path, prefixo: str) -> None:
    """Entrega o build do dashboard (SPA do React Router) em "/", se ele existir.

    Decisões:
    - Registrado DEPOIS das rotas da API: /api/... nunca é engolido pelo dashboard.
    - Caminho sob o prefixo que não é rota da API responde 404 em JSON, e não o index.html:
      senão um endpoint digitado errado no dataSource.ts voltaria "200 + HTML" e o erro
      apareceria como "JSON inválido" em vez de "rota inexistente".
    - Qualquer outro caminho sem arquivo correspondente devolve o index.html (as rotas
      /riscos, /alerta/:id... são do React Router, não arquivos).
    - Arquivo pedido é resolvido e checado DENTRO de dist/ (sem "../" para fora da pasta).
    - Sem build, nada é registrado: `npm run dev` (proxy do Vite) continua sendo o caminho
      do desenvolvimento, e a API segue funcionando sozinha.
    """
    index = dist / "index.html"
    if not index.is_file():
        return
    prefixo_api = prefixo.strip("/")

    @app.get("/{caminho:path}", include_in_schema=False)
    def dashboard(caminho: str):
        if caminho == prefixo_api or caminho.startswith(prefixo_api + "/"):
            raise HTTPException(404, f"rota inexistente na API: /{caminho}")
        alvo = (dist / caminho).resolve()
        if caminho and alvo.is_file() and alvo.is_relative_to(dist):
            return FileResponse(alvo)
        return FileResponse(index)
