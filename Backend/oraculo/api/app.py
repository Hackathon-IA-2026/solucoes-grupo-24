# -*- coding: utf-8 -*-
"""Aplicacao ASGI do O.R.A.C.U.L.O.

Starlette em vez de FastAPI porque e o que existe no ambiente-alvo (ver
03-arquitetura.md, decisao D4). O contrato esta em 05-api.md.
"""
from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from .. import config
from . import envelope
from .service import SERVICE

JSON = "application/json; charset=utf-8"
LEGADO_URL = "/legado"


def _json(payload: dict, status: int = 200) -> Response:
    return Response(envelope.dumps(payload), status_code=status, media_type=JSON,
                    headers={"Cache-Control": "no-store"})


def _wrap(data) -> Response:
    return _json(envelope.ok(data, mode=SERVICE.mode(),
                             provenance=SERVICE.provenance(),
                             notes=SERVICE.notes()))


def _fail(exc: Exception) -> Response:
    code = "INSUFFICIENT_DATA" if isinstance(exc, (ValueError, LookupError)) else "INTERNAL"
    hint = ("Execute POST /api/ingest ou verifique a conectividade com o "
            "Portal de Dados Abertos do ONS.")
    return _json(envelope.error(code, str(exc)[:400], hint),
                 envelope.status_for(code))


def _area(request: Request) -> str:
    a = (request.query_params.get("area") or config.DEFAULT_AREA).upper()
    return a if a in config.SUBSYSTEMS else config.DEFAULT_AREA


def _flag(request: Request, name: str, default: bool = True) -> bool:
    raw = request.query_params.get(name)
    if raw is None:
        return default
    return raw not in ("0", "false", "no")


def _int(request: Request, name: str, default: int) -> int:
    try:
        return int(request.query_params.get(name, default))
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------------ rotas
async def health(request: Request) -> Response:
    try:
        return _wrap(SERVICE.health())
    except Exception as exc:  # pragma: no cover
        return _fail(exc)


async def catalog_route(request: Request) -> Response:
    try:
        return _wrap(SERVICE.catalog_payload(refresh=_flag(request, "refresh", False)))
    except Exception as exc:
        return _fail(exc)


async def package_route(request: Request) -> Response:
    pkg = request.path_params.get("pkg", "")
    if not pkg:
        return _json(envelope.error("BAD_REQUEST", "informe o conjunto"), 400)
    try:
        return _wrap(SERVICE.package_detail(pkg))
    except Exception as exc:
        return _fail(exc)


async def series_route(request: Request) -> Response:
    try:
        return _wrap(SERVICE.series_payload(_area(request),
                                            last_hours=_int(request, "hours", 24 * 30)))
    except Exception as exc:
        return _fail(exc)


async def decomposition_route(request: Request) -> Response:
    try:
        return _wrap(SERVICE.decomposition_payload(_area(request),
                                                   hours=_int(request, "hours", 48)))
    except Exception as exc:
        return _fail(exc)


async def forecast_route(request: Request) -> Response:
    horizon = request.query_params.get("horizon", "3h")
    if horizon not in config.HORIZONS:
        return _json(envelope.error("BAD_REQUEST",
                                    "horizonte inválido: %s" % horizon,
                                    "use 30min, 3h ou d1"), 400)
    try:
        return _wrap(SERVICE.forecast_payload(_area(request), horizon,
                                              asymmetric=_flag(request, "asymmetric")))
    except Exception as exc:
        return _fail(exc)


async def profiles_route(request: Request) -> Response:
    try:
        return _wrap(SERVICE.profiles_payload(_area(request)))
    except Exception as exc:
        return _fail(exc)


async def risk_route(request: Request) -> Response:
    horizon = request.query_params.get("horizon", "d1")
    if horizon not in config.HORIZONS:
        return _json(envelope.error("BAD_REQUEST",
                                    "horizonte inválido: %s" % horizon), 400)
    try:
        mp = float(request.query_params.get("min_probability", 0.0))
    except ValueError:
        mp = 0.0
    try:
        return _wrap(SERVICE.risk_payload(
            horizon, request.query_params.get("level", "estado"), mp))
    except Exception as exc:
        return _fail(exc)


async def validation_route(request: Request) -> Response:
    try:
        return _wrap(SERVICE.validation_payload(_area(request),
                                                asymmetric=_flag(request, "asymmetric")))
    except Exception as exc:
        return _fail(exc)


async def triangulation_route(request: Request) -> Response:
    try:
        return _wrap(SERVICE.triangulation_payload())
    except Exception as exc:
        return _fail(exc)


async def provenance_route(request: Request) -> Response:
    try:
        return _wrap(SERVICE.provenance_payload())
    except Exception as exc:
        return _fail(exc)


async def ingest_route(request: Request) -> Response:
    try:
        body = await request.json()
    except Exception:
        body = {}
    year = body.get("year")
    months = body.get("months")
    if isinstance(months, list):
        try:
            months = [int(m) for m in months]
        except (TypeError, ValueError):
            months = None
    try:
        return _wrap(SERVICE.ingest_payload(year=int(year) if year else None,
                                            months=months,
                                            force=bool(body.get("force"))))
    except Exception as exc:
        return _fail(exc)


async def meta_route(request: Request) -> Response:
    """Metadados estaticos consumidos pela interface na inicializacao."""
    return _wrap({
        "app": config.APP_NAME,
        "subtitle": config.APP_SUBTITLE,
        "team": config.TEAM,
        "version": config.VERSION,
        "areas": [{"id": k, "name": v["name"]} for k, v in config.SUBSYSTEMS.items()],
        "horizons": list(config.HORIZONS.keys()),
        "patamares": {k: list(v) for k, v in config.PATAMARES.items()},
        "weights": {k: {"subestimacao": v[0], "superestimacao": v[1]}
                    for k, v in config.ASYMMETRIC_WEIGHTS.items()},
        "quantiles": list(config.QUANTILES),
        "sources": config.SOURCES,
        "demo_banner": config.DEMO_BANNER,
        "disclaimer": config.DISCLAIMER,
    })


# ===================================================== Mapa Inteligente
# Desafio Radix + AXIA + Cepel. Rotas novas: nenhuma rota anterior muda.
PNG = "image/png"


def _png(payload: bytes) -> Response:
    return Response(payload, media_type=PNG,
                    headers={"Cache-Control": "public, max-age=600"})


async def substations_route(request: Request) -> Response:
    try:
        return _wrap(SERVICE.substations_payload(
            uf=(request.query_params.get("uf") or "").upper(),
            subsystem=(request.query_params.get("subsystem") or "").upper(),
            frontier_only=_flag(request, "frontier_only", True),
            limit=_int(request, "limit", 24),
            offset=_int(request, "offset", 0),
            analyse=_flag(request, "analyse", True)))
    except Exception as exc:
        return _fail(exc)


async def substation_detail_route(request: Request) -> Response:
    sub_id = request.path_params.get("sub_id", "")
    if not sub_id:
        return _json(envelope.error("BAD_REQUEST", "informe a subestação"), 400)
    try:
        return _wrap(SERVICE.substation_detail_payload(sub_id))
    except LookupError as exc:
        return _json(envelope.error("NOT_FOUND", str(exc)), 404)
    except Exception as exc:
        return _fail(exc)


async def substation_scene_route(request: Request) -> Response:
    sub_id = (request.path_params.get("sub_id") or "").replace(".png", "")
    try:
        return _png(SERVICE.substation_scene_png(
            sub_id,
            overlay=_flag(request, "overlay", True),
            truth=_flag(request, "truth", False),
            tiles_grid=_flag(request, "tiles", False),
            channel=request.query_params.get("channel", "")))
    except LookupError as exc:
        return _json(envelope.error("NOT_FOUND", str(exc)), 404)
    except Exception as exc:
        return _fail(exc)


async def vision_route(request: Request) -> Response:
    try:
        return _wrap(SERVICE.vision_payload(
            refresh=_flag(request, "refresh", False)))
    except Exception as exc:
        return _fail(exc)


async def vision_real_route(request: Request) -> Response:
    """Detector do protótipo sobre imagem de satélite REAL (Esri) em volta de lat/lon."""
    from ..vision import satelite_real as SR
    try:
        lat = float(request.query_params["lat"])
        lon = float(request.query_params["lon"])
    except (KeyError, ValueError):
        return _json(envelope.error("BAD_REQUEST", "informe lat e lon numéricos"), 400)
    try:
        lado = float(request.query_params.get("lado_m", SR.LADO_PADRAO_M))
        d = SR.analisar(lat, lon, lado)
    except ValueError as exc:
        return _json(envelope.error("BAD_REQUEST", str(exc)[:400]), 400)
    except Exception as exc:
        return _json(envelope.error("UPSTREAM_UNAVAILABLE", str(exc)[:400], "Sem acesso à imagem de satélite da Esri."), 502)
    prov = [{"dataset": "Esri World Imagery", "resource": "zoom %d, %d ladrilhos" % (d["imagem"]["zoom"], d["imagem"]["ladrilhos"]),
             "url": SR.URL_LADRILHO, "fetched_at": d["analisado_em"], "mode": "cache" if d["cache"] else "live",
             "lag_note": SR.ATRIBUICAO}]
    return _json(envelope.ok(d, mode="cache" if d["cache"] else "live", provenance=prov, notes=[d["aviso"]]))


async def bench_png_route(request: Request) -> Response:
    try:
        return _png(SERVICE.bench_png(
            truth=_flag(request, "truth", False),
            tiles_grid=_flag(request, "tiles", False),
            channel=request.query_params.get("channel", ""),
            urban_class=request.query_params.get("urban_class", "misto"),
            seed=_int(request, "seed", 11)))
    except Exception as exc:
        return _fail(exc)


async def classes_route(request: Request) -> Response:
    try:
        return _wrap(SERVICE.classes_payload())
    except Exception as exc:
        return _fail(exc)


async def clm_spec_route(request: Request) -> Response:
    try:
        return _wrap(SERVICE.clm_spec_payload())
    except Exception as exc:
        return _fail(exc)


async def clm_curves_route(request: Request) -> Response:
    q = request.query_params

    def num(nome: str, padrao: float) -> float:
        try:
            return float(q.get(nome, padrao))
        except (TypeError, ValueError):
            return padrao

    try:
        return _wrap(SERVICE.clm_curves_payload(
            vstall=num("vstall", 0.60), rstall=num("rstall", 0.124),
            xstall=num("xstall", 0.114), vd1=num("vd1", 0.80),
            vd2=num("vd2", 0.70), frcel=num("frcel", 0.0),
            comppf=num("comppf", 0.97), p1c=num("p1c", 1.0),
            p1e=num("p1e", 2.0), p2c=num("p2c", 0.0), p2e=num("p2e", 1.0)))
    except Exception as exc:
        return _fail(exc)


async def clm_card_route(request: Request) -> Response:
    q = request.query_params
    try:
        ac = float(q.get("ac_factor", 1.0))
    except (TypeError, ValueError):
        ac = 1.0
    mix = {}
    for classe in ("residencial", "comercial", "industrial", "rural"):
        if classe in q:
            try:
                mix[classe] = float(q[classe])
            except (TypeError, ValueError):
                pass
    try:
        return _wrap(SERVICE.clm_card_payload(q.get("sub_id", ""),
                                              ac_factor=ac, mix=mix or None,
                                              fonte=q.get("fonte", "")))
    except LookupError as exc:
        return _json({"ok": False, "erro": str(exc)}, status=404)
    except Exception as exc:
        return _fail(exc)


async def clm_validation_route(request: Request) -> Response:
    try:
        return _wrap(SERVICE.clm_validation_payload())
    except Exception as exc:
        return _fail(exc)



# ---------------------------------------------- fronteira T-D (SED x SE ONS)
def _wrap_fr(data) -> Response:
    """Envelope com a proveniencia PROPRIA da secao (ANEEL + IBGE + ONS)."""
    return _json(envelope.ok(data, mode=SERVICE.fronteira_mode(),
                             provenance=SERVICE.fronteira_provenance(),
                             notes=SERVICE.fronteira_notes()))


def _fail_fr(exc: Exception) -> Response:
    from .service_fronteira import BaseNotReady
    if isinstance(exc, BaseNotReady):
        return _json(envelope.error(
            "UPSTREAM_UNAVAILABLE", str(exc),
            "Acompanhe em /api/fronteira/status. A primeira construção baixa "
            "~270 MB da ANEEL e leva cerca de 1 minuto."), 503)
    if isinstance(exc, LookupError):
        return _json(envelope.error("NOT_FOUND", str(exc)), 404)
    return _fail(exc)


async def fronteira_status_route(request: Request) -> Response:
    try:
        return _wrap_fr(SERVICE.fronteira_status())
    except Exception as exc:
        return _fail_fr(exc)


async def fronteira_summary_route(request: Request) -> Response:
    q = request.query_params
    try:
        return _wrap_fr(SERVICE.fronteira_summary_payload(
            uf=(q.get("uf") or "").upper(),
            subsystem=(q.get("subsystem") or "").upper(),
            order=q.get("order", "energia")))
    except Exception as exc:
        return _fail_fr(exc)


async def fronteira_detail_route(request: Request) -> Response:
    try:
        return _wrap_fr(SERVICE.fronteira_detail_payload(
            request.path_params.get("sub_id", ""),
            compare=_flag(request, "compare", True)))
    except Exception as exc:
        return _fail_fr(exc)


async def fronteira_quality_route(request: Request) -> Response:
    try:
        return _wrap_fr(SERVICE.fronteira_quality_payload())
    except Exception as exc:
        return _fail_fr(exc)


async def fronteira_rebuild_route(request: Request) -> Response:
    try:
        return _wrap_fr(SERVICE.fronteira_rebuild())
    except ValueError as exc:
        return _json(envelope.error("BAD_REQUEST", str(exc)), 400)
    except Exception as exc:
        return _fail_fr(exc)



# ---------------------------------------------- investimento: alocacao de BESS
def _wrap_bs(data) -> Response:
    return _json(envelope.ok(data, mode=SERVICE.bess_mode(),
                             provenance=SERVICE.bess_provenance(),
                             notes=SERVICE.bess_notes()))


def _weights(request: Request) -> dict | None:
    """Pesos da pontuacao vindos da tela: w_energia, w_mmgd, w_recorrencia, w_local."""
    out = {}
    for k in ("energia", "mmgd", "recorrencia", "local"):
        raw = request.query_params.get("w_" + k)
        if raw is None:
            continue
        try:
            out[k] = max(0.0, float(raw))
        except ValueError:
            pass
    return out or None


def _fail_bs(exc: Exception) -> Response:
    from .service_fronteira import BaseNotReady
    if isinstance(exc, BaseNotReady):
        return _json(envelope.error(
            "UPSTREAM_UNAVAILABLE", str(exc),
            "Acompanhe em /api/bess/status. A primeira carga baixa 12 meses de "
            "constrained-off (FV e eólica) do ONS."), 503)
    if isinstance(exc, LookupError):
        return _json(envelope.error("NOT_FOUND", str(exc)), 404)
    return _fail(exc)


async def bess_status_route(request: Request) -> Response:
    try:
        return _wrap_bs(SERVICE.bess_status())
    except Exception as exc:
        return _fail_bs(exc)


async def bess_ranking_route(request: Request) -> Response:
    q = request.query_params
    try:
        return _wrap_bs(SERVICE.bess_ranking_payload(
            weights=_weights(request), uf=(q.get("uf") or "").upper(),
            source=q.get("fonte", ""), limit=_int(request, "limit", 60)))
    except Exception as exc:
        return _fail_bs(exc)


async def bess_site_route(request: Request) -> Response:
    try:
        return _wrap_bs(SERVICE.bess_site_payload(
            request.path_params.get("code", ""), weights=_weights(request)))
    except Exception as exc:
        return _fail_bs(exc)


async def bess_method_route(request: Request) -> Response:
    try:
        return _wrap_bs(SERVICE.bess_method_payload())
    except Exception as exc:
        return _fail_bs(exc)


async def bess_rebuild_route(request: Request) -> Response:
    try:
        return _wrap_bs(SERVICE.bess_rebuild())
    except ValueError as exc:
        return _json(envelope.error("BAD_REQUEST", str(exc)), 400)
    except Exception as exc:
        return _fail_bs(exc)



# ---------------------------------------------- projecao do corte ENE e BESS futuro
def _wrap_ene(data) -> Response:
    return _json(envelope.ok(data, mode=SERVICE.ene_mode(),
                             provenance=SERVICE.ene_provenance(),
                             notes=SERVICE.ene_notes()))


async def ene_status_route(request: Request) -> Response:
    try:
        return _wrap_ene(SERVICE.ene_status())
    except Exception as exc:
        return _fail_bs(exc)


async def ene_projection_route(request: Request) -> Response:
    """Cenario personalizado pela query: g_vre, g_mmgd, g_load, flex_gw."""
    custom = {}
    for k in ("g_vre", "g_mmgd", "g_load", "flex_gw"):
        raw = request.query_params.get(k)
        if raw is None:
            continue
        try:
            v = float(raw)
        except ValueError:
            continue
        lo, hi = (-0.2, 1.0) if k != "flex_gw" else (0.0, 20.0)
        custom[k] = min(hi, max(lo, v))
    try:
        return _wrap_ene(SERVICE.ene_payload(custom or None))
    except Exception as exc:
        return _fail_bs(exc)



# ---------------------------------------------- curva do pato pelo tempo
def _wrap_tp(data) -> Response:
    return _json(envelope.ok(data, mode=SERVICE.tempo_mode(),
                             provenance=SERVICE.tempo_provenance(),
                             notes=SERVICE.tempo_notes()))


async def tempo_status_route(request: Request) -> Response:
    try:
        return _wrap_tp(SERVICE.tempo_status())
    except Exception as exc:
        return _fail_bs(exc)


async def tempo_route(request: Request) -> Response:
    try:
        return _wrap_tp(SERVICE.tempo_payload())
    except Exception as exc:
        return _fail_bs(exc)


async def tempo_rebuild_route(request: Request) -> Response:
    try:
        return _wrap_tp(SERVICE.tempo_rebuild())
    except ValueError as exc:
        return _json(envelope.error("BAD_REQUEST", str(exc)), 400)
    except Exception as exc:
        return _fail_bs(exc)


async def docs_status_route(request: Request) -> Response:
    try:
        return _wrap(SERVICE.docs_payload())
    except Exception as exc:
        return _fail(exc)


async def docs_missing(request: Request) -> Response:
    """Resposta para /docs quando a documentacao nao foi construida.

    Existe para que a tecla F1 nunca abra um quadro em branco: se nao ha o
    que mostrar, mostra-se **como produzir** o que falta.
    """
    from .service_docs import COMO_CONSTRUIR
    html = (
        "<!doctype html><meta charset='utf-8'>"
        "<title>Documentação não construída</title>"
        "<style>body{font:14px/1.6 system-ui,sans-serif;margin:0;padding:40px;"
        "background:#0b1020;color:#e8edf8}code{background:#151f3c;padding:3px 7px;"
        "border-radius:4px;font-family:ui-monospace,Consolas,monospace;"
        "color:#4fd1c5}h1{font-size:17px;margin:0 0 14px}p{max-width:60ch;"
        "color:#b8c4e0}@media(prefers-color-scheme:light){body{background:#f4f6fb;"
        "color:#16203c}code{background:#fff;color:#0e7c74}p{color:#3d4a6b}}</style>"
        "<h1>Documentação ainda não construída</h1>"
        "<p>A ajuda contextual (F1) usa a documentação Sphinx do projeto, que "
        "é gerada sob demanda. Para produzi-la:</p>"
        "<p><code>%s</code></p>"
        "<p>Depois recarregue esta página. O diretório esperado é "
        "<code>%s</code>.</p>"
    ) % (COMO_CONSTRUIR, config.DOCS_DIR)
    return Response(html, status_code=200, media_type="text/html; charset=utf-8",
                    headers={"Cache-Control": "no-store"})


async def index(request: Request) -> Response:
    path = config.WEB_DIR / "index.html"
    if not path.exists():  # pragma: no cover
        return Response("interface não encontrada em %s" % path, status_code=404)
    return FileResponse(path, headers={"Cache-Control": "no-store"})


routes = [
    # Interface antiga (HTML/JS puro) do prototipo; a principal e o dashboard React.
    Route(LEGADO_URL, index),
    Route(LEGADO_URL + "/", index),
    Route("/api/health", health),
    Route("/api/meta", meta_route),
    Route("/api/catalog", catalog_route),
    Route("/api/catalog/{pkg}", package_route),
    Route("/api/series", series_route),
    Route("/api/decomposition", decomposition_route),
    Route("/api/forecast", forecast_route),
    Route("/api/profiles", profiles_route),
    Route("/api/risk", risk_route),
    Route("/api/validation", validation_route),
    Route("/api/triangulation", triangulation_route),
    Route("/api/provenance", provenance_route),
    Route("/api/ingest", ingest_route, methods=["POST"]),
    # ---- Mapa Inteligente de Perfis de Carga e Geração Distribuída
    Route("/api/mapa/substations", substations_route),
    Route("/api/mapa/substations/{sub_id}", substation_detail_route),
    Route("/api/mapa/scene/{sub_id}", substation_scene_route),
    Route("/api/mapa/bench.png", bench_png_route),
    Route("/api/mapa/vision", vision_route),
    Route("/api/mapa/vision/real", vision_real_route),
    Route("/api/mapa/classes", classes_route),
    Route("/api/clm/spec", clm_spec_route),
    Route("/api/clm/curvas", clm_curves_route),
    Route("/api/clm/cartao", clm_card_route),
    Route("/api/clm/validacao", clm_validation_route),
    # ---- Fronteira T-D: SED (ANEEL) x SE de fronteira da rede basica (ONS)
    Route("/api/fronteira/status", fronteira_status_route),
    Route("/api/fronteira/resumo", fronteira_summary_route),
    Route("/api/fronteira/se/{sub_id}", fronteira_detail_route),
    Route("/api/fronteira/qualidade", fronteira_quality_route),
    Route("/api/fronteira/reconstruir", fronteira_rebuild_route,
          methods=["POST"]),
    # ---- Investimento: alocacao de BESS pelo corte observado
    Route("/api/bess/status", bess_status_route),
    Route("/api/bess/ranking", bess_ranking_route),
    Route("/api/bess/sitio/{code}", bess_site_route),
    Route("/api/bess/metodo", bess_method_route),
    Route("/api/bess/reconstruir", bess_rebuild_route, methods=["POST"]),
    Route("/api/ene/status", ene_status_route),
    Route("/api/ene/projecao", ene_projection_route),
    Route("/api/tempo/status", tempo_status_route),
    Route("/api/tempo/pato", tempo_route),
    Route("/api/tempo/reconstruir", tempo_rebuild_route, methods=["POST"]),
    # ---- Ajuda contextual (tecla F1)
    Route("/api/docs/status", docs_status_route),
]

class RevalidatedStatic(StaticFiles):
    """Arquivos da interface com revalidacao obrigatoria.

    Sem `Cache-Control`, o navegador reaproveita por heuristica o JS antigo
    e um painel novo simplesmente nao aparece no menu. `no-cache` nao impede
    o cache: obriga a conferir o ETag, e a resposta vem 304 quando nada mudou.
    """

    def file_response(self, *args, **kwargs):
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-cache"
        return resp


if config.WEB_DIR.exists():
    routes.append(Mount("/css", RevalidatedStatic(directory=config.WEB_DIR / "css")))
    routes.append(Mount("/js", RevalidatedStatic(directory=config.WEB_DIR / "js")))

# A documentacao e montada apenas se existir. `StaticFiles` valida o
# diretorio na criacao, e montar um caminho ausente derrubaria a aplicacao
# inteira na subida -- o oposto do que se quer: a ajuda e acessorio, o painel
# e o essencial. Sem documentacao construida, /docs explica como construi-la.
if config.DOCS_DIR.exists():
    routes.append(Mount(config.DOCS_URL_PREFIX,
                        StaticFiles(directory=config.DOCS_DIR, html=True)))
else:  # pragma: no cover - depende do estado do diretorio irmao
    routes.append(Route(config.DOCS_URL_PREFIX, docs_missing))
    routes.append(Route(config.DOCS_URL_PREFIX + "/{path:path}", docs_missing))

app = Starlette(routes=routes)
