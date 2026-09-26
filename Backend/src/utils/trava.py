"""Trava de processo por arquivo: impede duas execuções simultâneas do mesmo trabalho.

Usada pelo download (manifesto do que foi baixado) e pelo run_heavywork.py (pipeline inteiro).
Uma implementação só (DRY): antes ela vivia dentro de src/ingestion/download.py.

Por que existe: dois processos com o mesmo manifesto em memória sobrescreveriam os
registros um do outro (o último a salvar vence). Com a trava criada via O_EXCL, esse
cenário não consegue nem começar. Se o processo anterior morreu sem limpar, a mensagem
diz o que apagar.
"""
import os
from datetime import datetime
from pathlib import Path


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
            raise SystemExit(
                f"outro {self.descricao} em andamento (trava {self.caminho}: "
                f"{self.caminho.read_text(encoding='utf-8')}). Se não houver, apague a trava.")
        os.write(fd, f"pid={os.getpid()} desde={datetime.now().isoformat(timespec='seconds')}".encode())
        os.close(fd)
        return self

    def __exit__(self, *exc):
        self.caminho.unlink(missing_ok=True)
