"""Único ponto de leitura de configuração (config/*.yaml).

Regra do CLAUDE.md: parâmetros (datas de corte, caminhos, pesos) ficam em YAML,
nunca hardcoded. Todo script importa daqui em vez de abrir YAML por conta própria.
"""
from functools import lru_cache
from typing import Any

import yaml

from pathlib import Path

from src.utils.paths import CONFIG, RAIZ

# Chaves obrigatórias de config/projeto.yaml (definidas em docs/contexto dos prompts.txt).
# Validar aqui transforma "chave esquecida" em erro imediato e explícito, e não em
# um KeyError perdido no meio de um pipeline longo.
CHAVES_PROJETO = {
    "area_piloto": str,
    "incluir_rel": bool,
    "bloco_espacial": str,
    "era5_disponivel": bool,
    "gpu": bool,
    "caminho_fator_correcao": str,
}


@lru_cache(maxsize=None)
def carregar(nome: str) -> dict[str, Any]:
    """Lê config/<nome>.yaml (com ou sem extensão) e devolve um dict."""
    arquivo = CONFIG / (nome if nome.endswith(".yaml") else f"{nome}.yaml")
    if not arquivo.exists():
        raise FileNotFoundError(f"configuração ausente: {arquivo}")
    with arquivo.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def projeto() -> dict[str, Any]:
    """config/projeto.yaml validado (tipos e valores permitidos)."""
    cfg = carregar("projeto")
    for chave, tipo in CHAVES_PROJETO.items():
        if chave not in cfg:
            raise KeyError(f"config/projeto.yaml sem a chave obrigatória '{chave}'")
        if not isinstance(cfg[chave], tipo):
            raise TypeError(f"config/projeto.yaml: '{chave}' deveria ser {tipo.__name__}")
    if cfg["bloco_espacial"] not in ("tiago", "luiz"):
        raise ValueError("bloco_espacial deve ser 'tiago' ou 'luiz'")
    return cfg


def razoes_curtailment() -> list[str]:
    """Razões de corte modeladas. REL só entra se incluir_rel=true (DRY: um só lugar)."""
    return ["ENE", "CNF", "REL"] if projeto()["incluir_rel"] else ["ENE", "CNF"]


def arquivo_direto(apelido: str) -> Path:
    """Caminho local de um arquivo direto de config/fontes_ons.yaml (ANEEL, IBGE...).

    Um lugar só para achar o destino do download: quem lê o arquivo nunca monta o caminho de
    novo, então trocar o destino na config não deixa leitor apontando para o arquivo velho.
    """
    for a in carregar("fontes_ons").get("arquivos_diretos", []):
        if a["apelido"] == apelido:
            return RAIZ / a["destino"]
    raise KeyError(f"config/fontes_ons.yaml sem o arquivo direto '{apelido}'")
