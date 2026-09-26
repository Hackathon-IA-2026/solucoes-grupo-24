# -*- coding: utf-8 -*-
"""Fixtures da suite.

Os testes NAO dependem de rede: usam o gerador deterministico. Um unico teste
marcado `network` exercita a API real do ONS e e ignorado sem conectividade.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Cache isolado: a suite nunca escreve no cache de trabalho.
os.environ.setdefault("ORACULO_CACHE", str(ROOT / ".cache-tests"))


def pytest_configure(config):
    config.addinivalue_line("markers", "network: exige acesso ao Portal do ONS")


@pytest.fixture(scope="session")
def demo_bundle():
    from oraculo.pipeline import ingest
    return ingest.load_bundle(force_demo=True)


@pytest.fixture(scope="session")
def sin_series(demo_bundle):
    from oraculo.pipeline import ingest
    return ingest.area_series(demo_bundle.balanco, "SIN")


@pytest.fixture(scope="session")
def sin_state(demo_bundle):
    """Estado completo de uma area: MMGD, decomposicao e features."""
    from oraculo.features import builder
    from oraculo.models import decomposition, mmgd
    from oraculo.pipeline import ingest

    ser = ingest.area_series(demo_bundle.balanco, "SE")
    ts, load = ser["index"], ser["carga_supervisionada"]
    est = mmgd.estimate(ts, load, "SE")
    dec = decomposition.decompose(ts, load, est.mmgd_mw, "SE")
    fm = builder.build(ts, area="SE", target=load, mmgd=est.mmgd_mw,
                       ger_eolica=ser.get("ger_eolica"),
                       margem_controlavel=ser.get("margem_controlavel"))
    return {"ts": ts, "load": load, "mmgd": est, "dec": dec, "fm": fm}


@pytest.fixture(scope="session")
def client():
    """Cliente ASGI sincrono sobre a aplicacao, em modo demonstrativo."""
    from starlette.testclient import TestClient

    from oraculo.api.app import app
    from oraculo.api.service import SERVICE

    SERVICE.ensure(force_demo=True)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def hourly_index():
    from oraculo.core.timeutils import hourly_grid
    return hourly_grid(np.datetime64("2026-03-01T00:00:00", "s"),
                       np.datetime64("2026-03-31T23:00:00", "s"))


def has_network() -> bool:
    from oraculo.ons import ckan
    return ckan.network_available()
