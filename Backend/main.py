"""O.R.A.C.U.L.O. — serviço web: API FastAPI só de leitura (lê o banco que o run_heavywork.py publica).

Como rodar (de dentro de Backend/, com o .venv ativo):

    python main.py                 # http://127.0.0.1:8000/api/...  (host/porta em config/api.yaml)
    uvicorn main:app --reload      # alternativa, com recarga automática no desenvolvimento

Documentação interativa das rotas: http://127.0.0.1:8000/docs

Este arquivo não importa nada da parte pesada (ingestão, processamento, modelos): o serviço
web só lê o banco. Se o banco ainda não foi publicado, as rotas respondem 503 dizendo para
rodar `python run_heavywork.py`. Arquitetura em docs/Oraculo_planejamento.md §13.1.
"""
from src.api.app import criar_app
from src.utils.config import carregar

app = criar_app()

if __name__ == "__main__":
    import uvicorn

    cfg = carregar("api")
    uvicorn.run(app, host=cfg["host"], port=cfg["porta"])
