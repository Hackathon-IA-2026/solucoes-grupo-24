"""Download idempotente das bases do ONS (portal CKAN + API REST de carga).

Uso:
    python -m src.ingestion.download                 # tudo
    python -m src.ingestion.download --so-ckan       # só conjuntos do portal
    python -m src.ingestion.download --so-api        # só API de carga
    python -m src.ingestion.download --conjuntos coff_eolica_tm coff_solar_tm

Decisões:
- Idempotência por MANIFESTO (data/raw/ons/_manifesto.json): cada arquivo baixado com
  sucesso é registrado com bytes e linhas. Rodar de novo pula o que já está lá, então um
  download interrompido retoma de onde parou sem rebaixar nada.
- Escrita atômica: baixa para `.part` e só renomeia no fim. Arquivo pela metade nunca
  fica com nome final, logo nunca é confundido com arquivo completo (classe de bug eliminada).
- A lista de arquivos vem da API CKAN (config/fontes_ons.yaml só diz QUAIS conjuntos),
  então meses novos publicados pelo ONS entram sozinhos numa nova execução.
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
import json
import os
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

from src.utils.banco_analitico import conectar
from src.utils.config import carregar
from src.utils.paths import DOCS_REPORTS, RAIZ, ensure

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


def baixar_arquivo(url: str, destino: Path) -> int:
    """Baixa `url` para `destino` de forma atômica (.part -> nome final). Devolve bytes."""
    ensure(destino.parent)
    parcial = destino.with_name(destino.name + ".part")
    with SESSAO.get(url, stream=True, timeout=CFG["timeout_s"]) as r:
        r.raise_for_status()
        with parcial.open("wb") as f:
            for bloco in r.iter_content(chunk_size=1 << 20):
                f.write(bloco)
    parcial.replace(destino)
    return destino.stat().st_size


def contar_linhas(arquivo: Path) -> int:
    """Linhas de dados. Parquet: lê só o rodapé. CSV: conta quebras de linha - cabeçalho."""
    if arquivo.suffix.lower() == ".parquet":
        return pq.ParquetFile(arquivo).metadata.num_rows
    with arquivo.open("rb") as f:
        n = sum(bloco.count(b"\n") for bloco in iter(lambda: f.read(1 << 20), b""))
    return max(n - 1, 0)


# --------------------------------------------------------------------------- CKAN
def listar_parquets(pacote: str, aceitar_csv: bool = False) -> list[tuple[str, str]]:
    """(nome_arquivo, url) dos recursos PARQUET de um pacote do portal.

    - O portal às vezes repete o mesmo arquivo em dois recursos (hosts S3 diferentes);
      deduplicamos pelo nome do arquivo.
    - Com `aceitar_csv`, um período que só existe em CSV (ex.: intercâmbio antes de 2023)
      entra em CSV. A preferência é sempre Parquet para o mesmo nome-base.
    """
    r = SESSAO.get(CFG["ckan_package_show"], params={"id": pacote}, timeout=60)
    r.raise_for_status()
    por_base: dict[str, dict[str, str]] = {}
    for rec in r.json()["result"]["resources"]:
        fmt = (rec.get("format") or "").upper()
        if fmt == "PARQUET" or (aceitar_csv and fmt == "CSV"):
            nome = rec["url"].rsplit("/", 1)[-1]
            base = nome.rsplit(".", 1)[0].upper()
            por_base.setdefault(base, {})[fmt] = rec["url"]
    escolhidos = {}
    for fmts in por_base.values():
        url = fmts.get("PARQUET") or fmts["CSV"]
        escolhidos[url.rsplit("/", 1)[-1]] = url
    return sorted(escolhidos.items())


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

    def tarefa(nome_url: tuple[str, str]) -> None:
        nome, url = nome_url
        chave = f"{apelido}/{nome}"
        info = man.get(chave)
        if info and info.get("status") == "ok":
            return  # já baixado (e, se id_ons, possivelmente já consolidado)
        if particao == "id_ons":
            dest = LANDING / apelido / nome
        elif particao == "data":
            dest = destino_data(apelido, nome)
        else:
            dest = DESTINO / apelido / nome
        t0 = time.time()
        try:
            nbytes = baixar_arquivo(url, dest)
            linhas = contar_linhas(dest)
            man.registrar(chave, {
                "conjunto": apelido, "arquivo": nome, "url": url, "status": "ok",
                "bytes": nbytes, "linhas": linhas, "caminho": str(dest.relative_to(RAIZ)),
                "consolidado": particao != "id_ons",
                "baixado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
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


def consolidar_id_ons(apelido: str, man: Manifesto) -> None:
    """Reescreve landing mensal + consolidado anterior em <apelido>/id_ons=<id>/.

    Grava primeiro num diretório temporário e só troca no fim: se a consolidação falhar,
    o consolidado anterior continua intacto.
    """
    pendentes = [(k, v) for k, v in man.itens()
                 if v.get("conjunto") == apelido and v.get("status") == "ok"
                 and not v.get("consolidado")]
    if not pendentes:
        return
    arquivos = [str((RAIZ / v["caminho"]).as_posix()) for _, v in pendentes]
    final = DESTINO / apelido
    tmp = DESTINO / f"{apelido}.__tmp"
    if tmp.exists():
        shutil.rmtree(tmp)

    # Conexão com limites de memória/disco (src/utils/banco_analitico.py): com PARTITION_BY
    # o DuckDB mantém um buffer por partição e por thread, o que estourou a RAM na 1ª execução.
    con = conectar()
    # union_by_name: o ONS muda colunas/tipos entre meses; unimos pelo nome.
    fonte = f"SELECT * FROM read_parquet({arquivos!r}, union_by_name=true)"
    if final.exists():
        fonte = (f"SELECT * FROM read_parquet('{final.as_posix()}/**/*.parquet', "
                 f"hive_partitioning=true, union_by_name=true) UNION ALL BY NAME {fonte}")
    log.info("%s: consolidando %d arquivos novos por id_ons...", apelido, len(arquivos))
    t0 = time.time()
    con.execute(f"COPY ({fonte}) TO '{tmp.as_posix()}' "
                f"(FORMAT parquet, PARTITION_BY (id_ons), COMPRESSION zstd)")
    con.close()
    if final.exists():
        shutil.rmtree(final)
    tmp.rename(final)
    for chave, v in pendentes:
        (RAIZ / v["caminho"]).unlink(missing_ok=True)
        man.registrar(chave, {**v, "consolidado": True,
                              "caminho": str(final.relative_to(RAIZ))})
    log.info("%s: consolidado em %.0fs", apelido, time.time() - t0)


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
            ensure(dest.parent)
            parcial = dest.with_name(dest.name + ".part")
            df.to_parquet(parcial, index=False)
            parcial.replace(dest)
            man.registrar(chave, {
                "conjunto": ep["apelido"], "arquivo": f"{area}/{ini}_{fim}", "status": "ok",
                "linhas": len(df), "bytes": dest.stat().st_size, "fechada": fechada,
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
def processar_arquivos_diretos(man: Manifesto) -> None:
    """Fontes de arquivo único fora do portal ONS (ex.: MMGD da ANEEL)."""
    for a in CFG.get("arquivos_diretos", []):
        chave = f"{a['apelido']}/{a['url'].rsplit('/', 1)[-1]}"
        info = man.get(chave)
        if info and info.get("status") == "ok" and (RAIZ / info["caminho"]).exists():
            continue
        dest = RAIZ / a["destino"]
        try:
            nbytes = baixar_arquivo(a["url"], dest)
            man.registrar(chave, {
                "conjunto": a["apelido"], "arquivo": dest.name, "url": a["url"], "status": "ok",
                "bytes": nbytes, "linhas": contar_linhas(dest), "caminho": str(dest.relative_to(RAIZ)),
                "consolidado": True,
                "baixado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })
            log.info("%s: %s baixado", a["apelido"], dest.name)
        except Exception as e:
            man.registrar(chave, {"conjunto": a["apelido"], "arquivo": dest.name,
                                  "status": f"erro: {e}"[:300]})
            log.error("%s falhou: %s", a["apelido"], e)


# --------------------------------------------------------------------------- trava
class TravaDeProcesso:
    """Impede dois downloads simultâneos sobre o mesmo manifesto.

    Dois processos com o manifesto em memória sobrescreveriam os registros um do outro
    (o último a salvar vence). Com a trava criada via O_EXCL, esse cenário não consegue
    nem começar. Se o processo anterior morreu sem limpar, a mensagem diz o que apagar.
    """

    def __init__(self, caminho: Path):
        self.caminho = caminho

    def __enter__(self):
        try:
            fd = os.open(self.caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise SystemExit(
                f"outro download em andamento (trava {self.caminho}: "
                f"{self.caminho.read_text(encoding='utf-8')}). Se não houver, apague a trava.")
        os.write(fd, f"pid={os.getpid()} desde={datetime.now().isoformat(timespec='seconds')}".encode())
        os.close(fd)
        return self

    def __exit__(self, *exc):
        self.caminho.unlink(missing_ok=True)


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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--so-ckan", action="store_true")
    ap.add_argument("--so-api", action="store_true")
    ap.add_argument("--conjuntos", nargs="*", help="apelidos de config/fontes_ons.yaml")
    args = ap.parse_args()

    ensure(DESTINO)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(),
                                  logging.FileHandler(DESTINO / "_download.log", encoding="utf-8")])
    with TravaDeProcesso(DESTINO / "_download.lock"):
        man = Manifesto(MANIFESTO_PATH)
        t0 = time.time()
        if not args.so_api:
            for c in CFG["conjuntos"]:
                if args.conjuntos and c["apelido"] not in args.conjuntos:
                    continue
                try:
                    processar_conjunto(c, man)
                except Exception as e:  # um conjunto com problema não derruba os outros
                    log.exception("conjunto %s falhou: %s", c["apelido"], e)
        if not args.so_ckan and not args.conjuntos:
            processar_api_carga(man)
        if not args.so_api and not args.so_ckan and not args.conjuntos:
            processar_arquivos_diretos(man)
        san = gravar_relatorios(man)
    log.info("fim em %.1f min\n%s", (time.time() - t0) / 60, san.to_string(index=False))


if __name__ == "__main__":
    main()
