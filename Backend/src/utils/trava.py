"""Trava de processo por arquivo: impede duas execuções simultâneas do mesmo trabalho.

Usada pelo download (manifesto do que foi baixado) e pelo run_heavywork.py (pipeline inteiro).
Uma implementação só (DRY): antes ela vivia dentro de src/ingestion/download.py.

Por que existe: dois processos com o mesmo manifesto em memória sobrescreveriam os
registros um do outro (o último a salvar vence). Com a trava criada via O_EXCL, esse
cenário não consegue nem começar.

Trava órfã (2026-09-26): uma trava copiada junto com a pasta (ou deixada por um processo que
morreu) bloqueava o pipeline, e o PID gravado nela já pertencia a OUTRO programa (o Windows
reaproveitou o número para um `node`). Agora a trava só vale se o PID gravado estiver vivo E
for um processo Python; senão ela é assumida, com aviso no log. Na dúvida (não dá para
inspecionar o processo), a trava é respeitada — o lado seguro.
"""
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

log = logging.getLogger("trava")


def _nome_do_executavel(pid: int) -> str | None:
    """Nome do executável do processo `pid`; "" se não existe; None se não dá para saber."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        consulta_limitada = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
        h = kernel32.OpenProcess(consulta_limitada, False, pid)
        if not h:
            # 87 = parâmetro inválido: não existe processo com esse PID
            return "" if ctypes.get_last_error() == 87 else None
        try:
            codigo = wintypes.DWORD()
            if kernel32.GetExitCodeProcess(h, ctypes.byref(codigo)) and codigo.value != 259:  # 259 = STILL_ACTIVE
                return ""
            buf = ctypes.create_unicode_buffer(1024)
            tam = wintypes.DWORD(len(buf))
            if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(tam)):
                return Path(buf.value).name
            return None
        finally:
            kernel32.CloseHandle(h)
    # POSIX: /proc quando existe (Linux); senão só sabemos se está vivo
    cmd = Path(f"/proc/{pid}/cmdline")
    if cmd.exists():
        return Path(cmd.read_bytes().split(b"\0")[0].decode(errors="ignore")).name
    try:
        os.kill(pid, 0)  # sinal 0 = só testa existência (NUNCA usar no Windows: lá mata o processo)
    except ProcessLookupError:
        return ""
    except PermissionError:
        return None
    return None


def trava_orfa(conteudo: str) -> bool:
    """True se a trava pertence a um processo que não existe mais ou que não é Python."""
    m = re.search(r"pid=(\d+)", conteudo)
    if not m:
        return False  # formato desconhecido: respeita
    nome = _nome_do_executavel(int(m.group(1)))
    if nome is None:
        return False
    return nome == "" or "python" not in nome.lower()


class TravaDeProcesso:
    def __init__(self, caminho: Path, descricao: str = "processo"):
        self.caminho = caminho
        self.descricao = descricao

    def __enter__(self):
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        try:
            # O_EXCL: criação atômica; falha se o arquivo já existe (outro processo segura a trava).
            fd = os.open(self.caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            conteudo = self.caminho.read_text(encoding="utf-8")
            if not trava_orfa(conteudo):
                raise SystemExit(
                    f"outro {self.descricao} em andamento (trava {self.caminho}: {conteudo}). "
                    "Se não houver, apague a trava.")
            log.warning("trava órfã (%s) em %s: o processo não existe mais ou não é Python; assumindo",
                        conteudo, self.caminho)
            self.caminho.unlink(missing_ok=True)
            fd = os.open(self.caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"pid={os.getpid()} desde={datetime.now().isoformat(timespec='seconds')}".encode())
        os.close(fd)
        return self

    def __exit__(self, *exc):
        self.caminho.unlink(missing_ok=True)
