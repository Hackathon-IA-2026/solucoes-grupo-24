"""Download idempotente das bases do ONS (portal CKAN + API REST de carga) e da ANEEL.

Chamado pela etapa 1 do Backend/run_heavywork.py via `executar()`. A linha de comando
abaixo continua disponível para depuração (baixar só um conjunto, reconsolidar etc.).

Uso:
    python -m src.ingestion.download                 # tudo
    python -m src.ingestion.download --so-ckan       # só conjuntos do portal
    python -m src.ingestion.download --so-api        # só API de carga
    python -m src.ingestion.download --conjuntos coff_eolica_tm coff_solar_tm
    python -m src.ingestion.download --diretos bdgd_light bdgd_enel_rj   # só arquivos diretos
    python -m src.ingestion.download --so-ckan --conjuntos coff_solar_detail --recompactar coff_solar_detail

Decisões:
- Idempotência por MANIFESTO (data/raw/ons/_manifesto.json): cada arquivo baixado com
  sucesso é registrado com bytes e linhas. Rodar de novo pula o que já está lá, então um
  download interrompido retoma de onde parou sem rebaixar nada.
- Escrita atômica: baixa para `.part` e só renomeia no fim. Arquivo pela metade nunca
  fica com nome final, logo nunca é confundido com arquivo completo (classe de bug eliminada).
- A lista de arquivos vem da API CKAN (config/fontes_ons.yaml só diz QUAIS conjuntos),
  então meses novos publicados pelo ONS entram sozinhos numa nova execução.
- Arquivo REPUBLICADO pelo ONS com o mesmo nome (ex.: o mês corrente, que cresce ao longo do
  mês) é detectado pelo tamanho e pela data de alteração que o portal informa
  (`size`/`metadata_modified`), guardados no manifesto no momento do download. Mudou -> rebaixa.
  Ver `precisa_baixar()`.
- Consolidação das bases detail: os meses cobertos pelos arquivos novos SUBSTITUEM os mesmos
  meses do consolidado. Rebaixar um mês nunca duplica linhas (ver `sql_consolidacao()`).
- Arquivos diretos (cadastro de MMGD da ANEEL, atualizado diariamente) são rebaixados quando
  o download tem mais de `atualizar_apos_dias` dias (config/fontes_ons.yaml).
- Particionamento (regra do CLAUDE.md: dados grandes em Parquet particionado):
    data   -> <apelido>/ano=YYYY/<arquivo original>. Só o nível "ano" porque o ONS mistura
              arquivos anuais (até 2021) e mensais (2022+); com um único nível o Hive
              fica consistente e o nome do arquivo ainda carrega o mês.
    id_ons -> bases detail: baixa mensal em _landing/ e consolida em <apelido>/id_ons=<id>/
              com DuckDB. Depois de consolidar, o landing é apagado (disco apertado).
- API de carga: janelas de até 3 meses (limite da API). Janelas que terminaram há menos de
  `dias_para_fechar` dias são rebaixadas a cada execução, porque o ONS ainda consiste os
  dados recentes. O arquivo é nomeado pelo INÍCIO da janela, então rebaixar sobrescreve
  (nunca duplica) mesmo que o fim da janela tenha mudado.
- O log por arquivo (linhas, bytes, status) é regravado a partir do manifesto em
  docs/reports/download_log.csv; a sanidade por conjunto vai em download_sanidade.csv.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


import pandas as pd
import pyarrow.parquet as pq
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.utils import log as log_util
from src.utils.banco_analitico import conectar
from src.utils.config import carregar
from src.utils.impressao import de_objeto
from src.utils.paths import DOCS_REPORTS, RAIZ, ensure
from src.utils.trava import TravaDeProcesso

CFG = carregar("fontes_ons")
DESTINO = RAIZ / CFG["destino"]
LANDING = DESTINO / "_landing"
MANIFESTO_PATH = DESTINO / "_manifesto.json"

log = logging.getLogger("download")


# --------------------------------------------------------------------------- manifesto
class Manifesto:
    """Registro persistente e thread-safe do que já foi baixado."""

    def __init__(self, caminho: Path):
        self.caminho = caminho
        self._lock = threading.Lock()
        self.dados: dict[str, dict] = (
            json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}
        )

    def get(self, chave: str) -> dict | None:
        with self._lock:
            return self.dados.get(chave)

    def registrar(self, chave: str, info: dict) -> None:
        # Salva a cada registro: se o processo morrer, o progresso não se perde.
        with self._lock:
            self.dados[chave] = info
            tmp = self.caminho.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.dados, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.caminho)

    def remover(self, chave: str) -> None:
        with self._lock:
            if self.dados.pop(chave, None) is not None:
                tmp = self.caminho.with_suffix(".tmp")
                tmp.write_text(json.dumps(self.dados, ensure_ascii=False, indent=1), encoding="utf-8")
                tmp.replace(self.caminho)

    def itens(self) -> list[tuple[str, dict]]:
        with self._lock:
            return list(self.dados.items())


# --------------------------------------------------------------------------- HTTP
def _sessao() -> requests.Session:
    """Sessão com retry exponencial para erros transitórios (5xx, 429, conexão)."""
    s = requests.Session()
    retry = Retry(total=5, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET", "HEAD"))
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
    s.mount("http://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
    return s


SESSAO = _sessao()


def baixar_arquivo(url: str, destino: Path) -> tuple[int, str]:
    """Baixa `url` para `destino` de forma atômica (.part -> nome final).

    Devolve (bytes, sha256 do conteúdo baixado). O hash vai para o manifesto como `conteudo`
    e é o que a impressão digital do download usa: rebaixar um arquivo idêntico não muda nada
    a jusante (o processamento não é refeito à toa); só mudança real de conteúdo muda.
    """
    ensure(destino.parent)
    parcial = destino.with_name(destino.name + ".part")
    h = hashlib.sha256()
    with SESSAO.get(url, stream=True, timeout=CFG["timeout_s"]) as r:
        r.raise_for_status()
        with parcial.open("wb") as f:
            for bloco in r.iter_content(chunk_size=1 << 20):
                f.write(bloco)
                h.update(bloco)
    parcial.replace(destino)
    return destino.stat().st_size, h.hexdigest()


def csv_para_parquet(arquivo: Path) -> Path:
    """Converte um CSV do ONS (separador ';') em Parquet ao lado e apaga o CSV.

    Regra: data/raw só tem Parquet. Com formatos misturados, `read_parquet('**/*.parquet')`
    ignora os CSVs em silêncio (o intercâmbio "começava" em 2023 por isso). Um formato só
    torna essa perda impossível.
    """
    destino = arquivo.with_suffix(".parquet")
    parcial = destino.with_name(destino.name + ".part")
    con = conectar()
    con.execute(f"""COPY (SELECT * FROM read_csv('{arquivo.as_posix()}', delim=';', header=true,
                                                 sample_size=-1))
                    TO '{parcial.as_posix()}' (FORMAT parquet, COMPRESSION zstd)""")
    con.close()
    parcial.replace(destino)
    arquivo.unlink()
    return destino


def limpar_parquets_vazios(man: Manifesto) -> None:
    """Remove Parquets sem linhas/colunas gravados antes da regra acima e marca sem_dados."""
    for chave, v in man.itens():
        arq = RAIZ / v.get("caminho", "")
        if v.get("status") == "ok" and arq.suffix == ".parquet" and arq.is_file():
            meta = pq.ParquetFile(arq).metadata
            if meta.num_rows == 0 or meta.num_columns == 0:
                arq.unlink()
                man.registrar(chave, {**v, "status": "sem_dados", "linhas": 0, "caminho": ""})
                log.info("removido Parquet vazio: %s", chave)


def migrar_csvs(man: Manifesto) -> None:
    """Converte CSVs baixados antes da regra 'só Parquet' e atualiza o manifesto."""
    for chave, v in man.itens():
        caminho = v.get("caminho", "")
        if v.get("status") == "ok" and caminho.lower().endswith(".csv") and (RAIZ / caminho).exists():
            novo = csv_para_parquet(RAIZ / caminho)
            man.registrar(chave, {**v, "caminho": str(novo.relative_to(RAIZ)),
                                  "linhas": contar_linhas(novo), "convertido_de_csv": True})
            log.info("convertido para Parquet: %s", novo.name)


def contar_linhas(arquivo: Path) -> int | None:
    """Linhas de dados. Parquet: lê só o rodapé. CSV: conta quebras de linha - cabeçalho.

    Outros formatos (a BDGD zipada, GeoJSON do IBGE) não têm "linhas": devolve None em vez de
    contar quebras de linha de um binário e registrar um número sem sentido no manifesto.
    """
    if arquivo.suffix.lower() == ".parquet":
        return pq.ParquetFile(arquivo).metadata.num_rows
    if arquivo.suffix.lower() != ".csv":
        return None
    with arquivo.open("rb") as f:
        n = sum(bloco.count(b"\n") for bloco in iter(lambda: f.read(1 << 20), b""))
    return max(n - 1, 0)


# --------------------------------------------------------------------------- CKAN
def listar_parquets(pacote: str, aceitar_csv: bool = False) -> list[dict]:
    """Recursos PARQUET de um pacote do portal: [{nome, url, tamanho, modificado}], por nome.

    - O portal às vezes repete o mesmo arquivo em dois recursos (hosts S3 diferentes);
      deduplicamos pelo nome do arquivo.
    - Com `aceitar_csv`, um período que só existe em CSV (ex.: intercâmbio antes de 2023)
      entra em CSV. A preferência é sempre Parquet para o mesmo nome-base.
    - `tamanho` (bytes) e `modificado` vêm dos metadados do CKAN (`size`, `metadata_modified`;
      o `last_modified` do portal vem sempre nulo). São o que permite detectar republicação.
    """
    r = SESSAO.get(CFG["ckan_package_show"], params={"id": pacote}, timeout=60)
    r.raise_for_status()
    por_base: dict[str, dict[str, dict]] = {}
    for rec in r.json()["result"]["resources"]:
        fmt = (rec.get("format") or "").upper()
        if fmt == "PARQUET" or (aceitar_csv and fmt == "CSV"):
            nome = rec["url"].rsplit("/", 1)[-1]
            base = nome.rsplit(".", 1)[0].upper()
            por_base.setdefault(base, {})[fmt] = {
                "nome": nome, "url": rec["url"],
                "tamanho": rec.get("size"), "modificado": rec.get("metadata_modified")}
    escolhidos = {}
    for fmts in por_base.values():
        rec = fmts.get("PARQUET") or fmts["CSV"]
        escolhidos[rec["nome"]] = rec
    return [escolhidos[n] for n in sorted(escolhidos)]


def precisa_baixar(info: dict | None, recurso: dict) -> str | None:
    """Motivo para (re)baixar um arquivo do portal, ou None se o que temos está em dia.

    Compara os metadados que o portal informa AGORA com os que ele informava quando
    baixamos (guardados no manifesto como portal_tamanho/portal_modificado). Comparar
    portal com portal (e não portal com o arquivo em disco) evita rebaixar em loop caso o
    `size` do CKAN não bata exatamente com os bytes servidos.

    Registros antigos, de antes desta regra, não têm portal_*: aí o tamanho do portal é
    comparado com os bytes baixados. Igual -> em dia (o chamador só anota os metadados);
    diferente -> rebaixa uma vez, e daí em diante vale a comparação portal x portal.
    """
    if not info or info.get("status") != "ok":
        return "novo" if not info else "falhou antes"
    tam, mod = recurso.get("tamanho"), recurso.get("modificado")
    if "portal_tamanho" in info or "portal_modificado" in info:
        if tam is not None and info.get("portal_tamanho") != tam:
            return "tamanho mudou no portal"
        if mod is not None and info.get("portal_modificado") != mod:
            return "republicado no portal"
        return None
    if tam is not None and info.get("bytes") is not None and info["bytes"] != tam:
        return "tamanho difere do baixado"
    return None


_RE_ANO = re.compile(r"(?<!\d)(20\d{2})(?!\d)")


def destino_data(apelido: str, nome: str) -> Path:
    """<apelido>/ano=YYYY/<nome>. Arquivos sem ano no nome (cadastros) ficam na raiz."""
    m = _RE_ANO.search(nome)
    if not m:
        return DESTINO / apelido / nome
    return DESTINO / apelido / f"ano={m.group(1)}" / nome


def processar_conjunto(c: dict, man: Manifesto) -> None:
    apelido, particao = c["apelido"], c["particao"]
    recursos = listar_parquets(c["pacote"], c.get("aceitar_csv", False))
    log.info("%s: %d arquivos no portal", apelido, len(recursos))

    def tarefa(recurso: dict) -> None:
        nome, url = recurso["nome"], recurso["url"]
        chave = f"{apelido}/{nome}"
        info = man.get(chave)
        motivo = precisa_baixar(info, recurso)
        if motivo is None:
            if "portal_tamanho" not in info:  # registro antigo em dia: só anota os metadados
                man.registrar(chave, {**info, "portal_tamanho": recurso["tamanho"],
                                      "portal_modificado": recurso["modificado"]})
            return
        if info:  # rebaixando algo que já tínhamos: fica no log por quê
            log.info("%s %s: rebaixando (%s)", apelido, nome, motivo)
        if particao == "id_ons":
            dest = LANDING / apelido / nome
        elif particao == "data":
            dest = destino_data(apelido, nome)
        else:
            dest = DESTINO / apelido / nome
        t0 = time.time()
        try:
            nbytes, conteudo = baixar_arquivo(url, dest)
            if dest.suffix.lower() == ".csv":
                dest = csv_para_parquet(dest)
            linhas = contar_linhas(dest)
            man.registrar(chave, {
                "conjunto": apelido, "arquivo": nome, "url": url, "status": "ok",
                "bytes": nbytes, "conteudo": conteudo, "linhas": linhas,
                "caminho": str(dest.relative_to(RAIZ)),
                "consolidado": particao != "id_ons",
                "baixado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "portal_tamanho": recurso["tamanho"], "portal_modificado": recurso["modificado"],
            })
            log.info("%-22s %-55s %10d linhas %6.1fs", apelido, nome, linhas, time.time() - t0)
        except Exception as e:  # registra e segue; a próxima execução tenta de novo
            man.registrar(chave, {"conjunto": apelido, "arquivo": nome, "url": url,
                                  "status": f"erro: {e}"[:300]})
            log.error("%s %s falhou: %s", apelido, nome, e)

    with ThreadPoolExecutor(CFG["threads_download"]) as ex:
        list(ex.map(tarefa, recursos))

    if particao == "id_ons":
        consolidar_id_ons(apelido, man)


def consolidar_id_ons(apelido: str, man: Manifesto, recompactar: bool = False) -> None:
    """Reescreve landing mensal + consolidado anterior em <apelido>/id_ons=<id>/.

    Estratégia em GRUPOS ORDENADOS: os id_ons são divididos em N grupos (hash % N); cada
    grupo é lido, ordenado por (id_ons, din_instante) e escrito de uma vez. Com a entrada
    ordenada só uma partição fica aberta por vez, então:
      - a memória é limitada pelo tamanho do grupo (não pelo total de 80M linhas);
      - sai ~1 arquivo por usina. A 1ª versão (um COPY único com buffers pequenos para
        caber na RAM) gerou 316 mil arquivos minúsculos para a eólica — trocar memória
        por fragmentação não resolve; ordenar resolve as duas coisas.
    Grava num diretório temporário e só troca no fim: se falhar, o consolidado anterior
    continua intacto. `recompactar` refaz o consolidado mesmo sem arquivos novos.
    """
    pendentes = [(k, v) for k, v in man.itens()
                 if v.get("conjunto") == apelido and v.get("status") == "ok"
                 and not v.get("consolidado")]
    final = DESTINO / apelido
    if not pendentes and not (recompactar and final.exists()):
        return
    arquivos = [str((RAIZ / v["caminho"]).as_posix()) for _, v in pendentes]
    tmp = DESTINO / f"{apelido}.__tmp"
    if tmp.exists():
        shutil.rmtree(tmp)

    fonte = sql_consolidacao(final if final.exists() else None, arquivos)

    n = CFG["duckdb"]["grupos_consolidacao"]
    log.info("%s: consolidando (%d arquivos novos) por id_ons em %d grupos...", apelido, len(arquivos), n)
    t0 = time.time()
    con = conectar()  # limites de memória/disco centralizados (src/utils/banco_analitico.py)
    for g in range(n):
        con.execute(f"""COPY (SELECT * FROM ({fonte}) WHERE hash(id_ons) % {n} = {g}
                              ORDER BY id_ons, din_instante)
                        TO '{tmp.as_posix()}'
                        (FORMAT parquet, PARTITION_BY (id_ons), COMPRESSION zstd,
                         OVERWRITE_OR_IGNORE, FILENAME_PATTERN 'g{g}_{{i}}')""")
    con.close()
    if final.exists():
        shutil.rmtree(final)
    tmp.rename(final)
    for chave, v in pendentes:
        (RAIZ / v["caminho"]).unlink(missing_ok=True)
        man.registrar(chave, {**v, "consolidado": True,
                              "caminho": str(final.relative_to(RAIZ))})
    log.info("%s: consolidado em %.0fs", apelido, time.time() - t0)


def sql_consolidacao(final: Path | None, arquivos: list[str]) -> str:
    """SELECT que une o consolidado anterior com os arquivos novos do landing.

    Regra: os meses cobertos pelos arquivos novos SUBSTITUEM os mesmos meses do consolidado.
    Assim um mês republicado pelo ONS e rebaixado entra no lugar da versão antiga, em vez de
    se somar a ela: linha duplicada por rebaixar um mês não tem como acontecer.
    union_by_name: o ONS muda colunas/tipos entre meses; unimos pelo nome.
    """
    if not arquivos:  # recompactar sem arquivo novo: só o consolidado
        return (f"SELECT * FROM read_parquet('{final.as_posix()}/**/*.parquet', "
                f"hive_partitioning=true, union_by_name=true)")
    novos = f"read_parquet({arquivos!r}, union_by_name=true)"
    if final is None:
        return f"SELECT * FROM {novos}"
    return (f"SELECT * FROM read_parquet('{final.as_posix()}/**/*.parquet', "
            f"hive_partitioning=true, union_by_name=true) "
            f"WHERE date_trunc('month', din_instante) NOT IN "
            f"(SELECT DISTINCT date_trunc('month', din_instante) FROM {novos}) "
            f"UNION ALL BY NAME SELECT * FROM {novos}")


# --------------------------------------------------------------------------- API carga
# A API de carga escreve campo numérico sem valor como `"val_cargammgd": ,` (JSON inválido),
# típico dos anos em que o ONS ainda não estimava MMGD. Trocamos o valor vazio por null:
# o dado continua AUSENTE (NaN), nunca vira zero nem é inventado. Só casa ":" seguido
# direto de "," "}" ou "]", o que nunca acontece dentro de uma string entre aspas válida.
_RE_VALOR_VAZIO = re.compile(r":(\s*)(?=[,}\]])")


def json_tolerante(texto: str):
    return json.loads(_RE_VALOR_VAZIO.sub(r":\1null", texto))


def carga_para_dataframe(texto: str) -> pd.DataFrame:
    """Resposta da API -> DataFrame com todas as colunas val_* em float64.

    Uma janela inteira sem MMGD viraria coluna object/None e o Parquet dela teria tipo
    diferente das outras janelas. Fixar float64 aqui garante schema estável.
    """
    df = pd.DataFrame(json_tolerante(texto))
    for c in df.columns:
        if c.startswith("val_"):
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    return df


def janelas(inicio: date, fim: date, meses: int) -> list[tuple[date, date]]:
    """Janelas [ini, fim] de até `meses` meses cobrindo [inicio, fim]."""
    out, ini = [], inicio
    while ini <= fim:
        m = ini.month - 1 + meses
        prox = date(ini.year + m // 12, m % 12 + 1, 1)
        out.append((ini, min(prox - timedelta(days=1), fim)))
        ini = prox
    return out


def processar_api_carga(man: Manifesto) -> None:
    api = CFG["api_carga"]
    ontem = date.today() - timedelta(days=1)
    limite_fechada = date.today() - timedelta(days=api["dias_para_fechar"])
    tarefas = []
    for ep in api["endpoints"]:
        ini0 = date.fromisoformat(ep["inicio"])
        for area in ep["areas"]:
            for ini, fim in janelas(ini0, ontem, api["janela_meses"]):
                tarefas.append((ep, area, ini, fim))

    def tarefa(t) -> None:
        ep, area, ini, fim = t
        chave = f"{ep['apelido']}/{area}/{ini.isoformat()}"
        info = man.get(chave)
        if info and info.get("status") in ("ok", "sem_dados") and info.get("fechada"):
            return
        dest = DESTINO / ep["apelido"] / f"area={area}" / f"ano={ini.year}" / f"janela_{ini.isoformat()}.parquet"
        try:
            r = SESSAO.get(f"{api['base_url']}/{ep['nome']}", timeout=CFG["timeout_s"],
                           params={"dat_inicio": ini.isoformat(), "dat_fim": fim.isoformat(),
                                   "cod_areacarga": area})
            fechada = fim < limite_fechada
            if r.status_code == 404:  # a API responde 404 quando não há dado no período
                man.registrar(chave, {"conjunto": ep["apelido"], "arquivo": f"{area}/{ini}",
                                      "status": "sem_dados", "linhas": 0, "fechada": fechada})
                return
            r.raise_for_status()
            df = carga_para_dataframe(r.text)
            if df.empty:
                # A API também responde `[]` com status 200 (ex.: perdas e Roraima antes de
                # serem publicados). Nunca gravar arquivo vazio: um Parquet sem colunas
                # quebra a leitura da pasta inteira.
                dest.unlink(missing_ok=True)
                man.registrar(chave, {"conjunto": ep["apelido"], "arquivo": f"{area}/{ini}",
                                      "status": "sem_dados", "linhas": 0, "fechada": fechada})
                return
            ensure(dest.parent)
            parcial = dest.with_name(dest.name + ".part")
            df.to_parquet(parcial, index=False)
            parcial.replace(dest)
            man.registrar(chave, {
                "conjunto": ep["apelido"], "arquivo": f"{area}/{ini}_{fim}", "status": "ok",
                "linhas": len(df), "bytes": dest.stat().st_size, "fechada": fechada,
                # hash da resposta da API (e não do Parquet gravado): mesma resposta, mesmo hash.
                "conteudo": hashlib.sha256(r.content).hexdigest(),
                "caminho": str(dest.relative_to(RAIZ)), "consolidado": True,
                "baixado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })
        except Exception as e:
            man.registrar(chave, {"conjunto": ep["apelido"], "arquivo": f"{area}/{ini}",
                                  "status": f"erro: {e}"[:300]})
            log.error("API %s %s %s falhou: %s", ep["nome"], area, ini, e)

    log.info("API carga: %d janelas (área x período)", len(tarefas))
    with ThreadPoolExecutor(api["threads"]) as ex:
        for i, _ in enumerate(as_completed([ex.submit(tarefa, t) for t in tarefas]), 1):
            if i % 100 == 0:
                log.info("API carga: %d/%d janelas", i, len(tarefas))


# --------------------------------------------------------------------------- arquivos diretos
def vencido(baixado_em: str | None, dias: int | None, agora: datetime | None = None) -> bool:
    """True se um download feito em `baixado_em` (ISO) tem mais de `dias` dias.

    `dias` None = a fonte não expira (só baixa se faltar). Sem data registrada = vencido.
    """
    if dias is None:
        return False
    if not baixado_em:
        return True
    agora = agora or datetime.now(timezone.utc)
    return agora - datetime.fromisoformat(baixado_em) > timedelta(days=dias)


def chave_direta(a: dict) -> str:
    """Chave do manifesto de um arquivo direto: apelido + nome do arquivo de DESTINO.

    Antes era o fim da URL, e várias URLs terminam igual (".../items/<id>/data" da BDGD):
    trocar de ano deixaria a chave igual e o arquivo velho seria dado como em dia. O destino
    é único por arquivo e é o que está no disco.
    """
    return f"{a['apelido']}/{Path(a['destino']).name}"


def precisa_baixar_direto(a: dict, info: dict | None, agora: datetime | None = None) -> str | None:
    """Motivo para (re)baixar um arquivo direto, ou None se o que está no disco vale.

    Rebaixa se: nunca baixou/falhou, o arquivo sumiu, a URL da config mudou (nova edição da
    BDGD, por exemplo) ou o download venceu (`atualizar_apos_dias`).
    """
    if not info or info.get("status") != "ok":
        return "ausente"
    if not (RAIZ / info.get("caminho", "")).exists():
        return "arquivo sumiu do disco"
    if info.get("url") != a["url"]:
        return "URL mudou na config"
    if vencido(info.get("baixado_em"), a.get("atualizar_apos_dias"), agora):
        return f"download com mais de {a['atualizar_apos_dias']} dias"
    return None


def processar_arquivos_diretos(man: Manifesto, apelidos: list[str] | None = None) -> None:
    """Fontes de arquivo único fora do portal ONS (MMGD e BDGD da ANEEL, malhas do IBGE)."""
    for a in CFG.get("arquivos_diretos", []):
        if apelidos and a["apelido"] not in apelidos:
            continue
        chave = chave_direta(a)
        # Entradas antigas do mesmo apelido com outra chave (formato anterior ou edição anterior
        # da BDGD) saem do manifesto: senão continuariam na impressão digital e na tela Validação.
        # Se a entrada antiga aponta para o MESMO arquivo de destino, só muda de chave (não rebaixa).
        for velha, v in man.itens():
            if velha.startswith(f"{a['apelido']}/") and velha != chave:
                if Path(v.get("caminho", "")).as_posix() == a["destino"] and man.get(chave) is None:
                    man.registrar(chave, v)
                man.remover(velha)
        info = man.get(chave)
        motivo = precisa_baixar_direto(a, info)
        if motivo is None:
            continue
        log.info("%s: baixando (%s)", a["apelido"], motivo)
        dest = RAIZ / a["destino"]
        try:
            nbytes, conteudo = baixar_arquivo(a["url"], dest)
            man.registrar(chave, {
                "conjunto": a["apelido"], "arquivo": dest.name, "url": a["url"], "status": "ok",
                "bytes": nbytes, "conteudo": conteudo, "linhas": contar_linhas(dest),
                "caminho": str(dest.relative_to(RAIZ)),
                "consolidado": True,
                "baixado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })
            log.info("%s: %s baixado", a["apelido"], dest.name)
        except Exception as e:
            man.registrar(chave, {"conjunto": a["apelido"], "arquivo": dest.name,
                                  "status": f"erro: {e}"[:300]})
            log.error("%s falhou: %s", a["apelido"], e)


# --------------------------------------------------------------------------- relatórios
def gravar_relatorios(man: Manifesto) -> pd.DataFrame:
    """Log por arquivo + sanidade por conjunto (linhas obtidas vs. ordem de grandeza)."""
    ensure(DOCS_REPORTS)
    df = pd.DataFrame([{"chave": k, **v} for k, v in man.itens()])
    if df.empty:
        return df
    cols = [c for c in ("conjunto", "arquivo", "status", "linhas", "bytes", "baixado_em") if c in df]
    df.sort_values(["conjunto", "arquivo"])[cols].to_csv(DOCS_REPORTS / "download_log.csv", index=False)

    esperado = {c["apelido"]: c.get("linhas_esperadas") for c in CFG["conjuntos"]}
    ok = df[df["status"] == "ok"]
    san = ok.groupby("conjunto").agg(arquivos=("arquivo", "count"), linhas=("linhas", "sum")).reset_index()
    erros = df[df["status"].str.startswith("erro")].groupby("conjunto").size()
    san["arquivos_com_erro"] = san["conjunto"].map(erros).fillna(0).astype(int)
    san["linhas_esperadas"] = san["conjunto"].map(esperado)
    san["razao"] = san["linhas"] / san["linhas_esperadas"]
    lo, hi = CFG["sanidade_razao_min"], CFG["sanidade_razao_max"]
    san["divergencia"] = san["razao"].notna() & ~san["razao"].between(lo, hi)
    san.to_csv(DOCS_REPORTS / "download_sanidade.csv", index=False)
    return san


def executar(conjuntos: list[str] | None = None, so_ckan: bool = False, so_api: bool = False,
             recompactar: list[str] | tuple = (), diretos: list[str] | None = None) -> pd.DataFrame:
    """Baixa o que falta ou está desatualizado. Devolve a sanidade por conjunto.

    Sem argumentos = tudo (é o que o run_heavywork.py chama). Os filtros existem para a
    linha de comando de depuração.
    """
    ensure(DESTINO)
    log_util.configurar(DESTINO / "_download.log")
    with TravaDeProcesso(DESTINO / "_download.lock", "download"):
        man = Manifesto(MANIFESTO_PATH)
        t0 = time.time()
        limpar_parquets_vazios(man)
        migrar_csvs(man)
        if not so_api and diretos is None:
            for c in CFG["conjuntos"]:
                if conjuntos and c["apelido"] not in conjuntos:
                    continue
                try:
                    processar_conjunto(c, man)
                except Exception as e:  # um conjunto com problema não derruba os outros
                    log.exception("conjunto %s falhou: %s", c["apelido"], e)
        if not so_ckan and not conjuntos and diretos is None:
            processar_api_carga(man)
        if diretos is not None:  # --diretos: só os arquivos diretos (lista vazia = todos)
            processar_arquivos_diretos(man, diretos or None)
        elif not so_api and not so_ckan and not conjuntos:
            processar_arquivos_diretos(man)
        for apelido in recompactar:
            consolidar_id_ons(apelido, man, recompactar=True)
        san = gravar_relatorios(man)
    log.info("download: fim em %.1f min", (time.time() - t0) / 60)
    return san


def impressao_digital(conjuntos: set[str] | None = None) -> str:
    """Resumo do que está baixado: muda sempre que um arquivo entra, sai ou é rebaixado.

    É a "entrada" da etapa de processamento no run_heavywork.py: se nada mudou aqui (nem no
    código/config do processamento), as tabelas processadas continuam válidas. `conjuntos`
    restringe aos apelidos pedidos (a espacialização só depende da BDGD, do cadastro da ANEEL
    e das malhas do IBGE: um download novo de carga não a refaz).
    """
    man = Manifesto(MANIFESTO_PATH)
    return de_objeto(sorted((k, _versao(v)) for k, v in man.itens()
                            if v.get("status") == "ok" and (conjuntos is None or v.get("conjunto") in conjuntos)))


def _versao(info: dict):
    """O que identifica a versão de um arquivo baixado para a impressão digital.

    Usa o hash do CONTEÚDO, nunca a hora do download: a ingestão rebaixa em toda execução as
    janelas recentes da carga (o ONS ainda as consiste), e com a hora na impressão o
    processamento seria refeito sempre, mesmo com dado idêntico. Registros de antes desta
    regra não têm hash; para eles vale (bytes, linhas, baixado_em), que não muda enquanto o
    arquivo não for rebaixado (e, quando for, ganha hash).
    """
    if info.get("conteudo"):
        return info["conteudo"]
    return [info.get("bytes"), info.get("linhas"), info.get("baixado_em")]


def erros_de_download() -> list[str]:
    """Chaves do manifesto cuja última tentativa falhou (a próxima execução tenta de novo)."""
    return sorted(k for k, v in Manifesto(MANIFESTO_PATH).itens()
                  if str(v.get("status", "")).startswith("erro"))


def conjuntos_declarados() -> set[str]:
    """Todos os apelidos que a ingestão baixa, lidos de config/fontes_ons.yaml.

    Três blocos declaram fontes: `conjuntos` (CKAN do ONS), `arquivos_diretos` (ANEEL, IBGE)
    e `api_carga.endpoints` (API de carga). Fonte nova em qualquer um deles aparece aqui.
    """
    return ({c["apelido"] for c in CFG["conjuntos"]}
            | {a["apelido"] for a in CFG.get("arquivos_diretos", [])}
            | {e["apelido"] for e in CFG["api_carga"]["endpoints"]})


def validar_grupos_fontes(grupos: dict[str, list[str]]) -> None:
    """Confere `status_fontes` (config/publicacao.yaml) contra as fontes de config/fontes_ons.yaml.

    Decisão: a checagem é entre os DOIS ARQUIVOS DE CONFIG, sem olhar o manifesto. Assim ela
    roda em milissegundos no início do run_heavywork.py e nos testes. Antes, fonte nova sem
    grupo só estourava na publicação, a última etapa, depois de ~70 min de ingestão e treino
    (aconteceu em 2026-09-26 com BDGD e malhas do IBGE). Também recusa grupo citando apelido
    que não existe (erro de digitação sumiria da tela em silêncio).
    """
    declarados = conjuntos_declarados()
    agrupados = {c for cs in grupos.values() for c in cs}
    problemas = []
    if sem_grupo := sorted(declarados - agrupados):
        problemas.append(f"conjuntos sem grupo em publicacao.yaml (status_fontes): {sem_grupo}")
    if desconhecidos := sorted(agrupados - declarados):
        problemas.append(f"status_fontes cita conjuntos que não existem em fontes_ons.yaml: {desconhecidos}")
    if problemas:
        raise ValueError("; ".join(problemas))


def status_fontes(grupos: dict[str, list[str]]) -> list[dict]:
    """Saúde de cada fonte, a partir do manifesto (tela Validação do dashboard).

    `grupos`: rótulo exibido -> conjuntos do manifesto (config/publicacao.yaml).
    - online: a última tentativa de TODOS os arquivos do grupo deu certo;
    - ultima_sincronizacao: download mais recente do grupo (UTC).
    Conjunto do manifesto sem grupo é erro: fonte nova nunca some da tela em silêncio.
    """
    itens = [v for _, v in Manifesto(MANIFESTO_PATH).itens()]
    conhecidos = {c for cs in grupos.values() for c in cs}
    sem_grupo = sorted({v["conjunto"] for v in itens} - conhecidos)
    if sem_grupo:
        raise ValueError(f"conjuntos sem grupo em publicacao.yaml (status_fontes): {sem_grupo}")
    out = []
    for rotulo, conjuntos in grupos.items():
        do_grupo = [v for v in itens if v["conjunto"] in conjuntos]
        datas = [v["baixado_em"] for v in do_grupo if v.get("baixado_em")]
        if not datas:
            raise LookupError(f"fonte '{rotulo}' nunca foi baixada: rode a ingestão")
        out.append({"fonte": rotulo,
                    "online": all(v.get("status") == "ok" for v in do_grupo),
                    "ultima_sincronizacao": max(datetime.fromisoformat(d) for d in datas)})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--so-ckan", action="store_true")
    ap.add_argument("--so-api", action="store_true")
    ap.add_argument("--conjuntos", nargs="*", help="apelidos de config/fontes_ons.yaml")
    ap.add_argument("--recompactar", nargs="*", default=[],
                    help="apelidos id_ons para reconsolidar mesmo sem arquivos novos")
    ap.add_argument("--diretos", nargs="*", default=None,
                    help="só os arquivos diretos (ANEEL, IBGE); apelidos opcionais")
    args = ap.parse_args()
    san = executar(args.conjuntos, args.so_ckan, args.so_api, args.recompactar, args.diretos)
    log.info("\n%s", san.to_string(index=False))


if __name__ == "__main__":
    main()
