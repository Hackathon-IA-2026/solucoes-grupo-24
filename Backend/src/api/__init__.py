"""API FastAPI só de leitura. Lê o banco e nada mais (docs/Oraculo_planejamento.md §13.1).

Não pode importar nada da parte pesada (ingestão, processamento, publicação, pandas, DuckDB,
modelos): tests/test_db_api.py sobe o main.py num processo limpo e falha se algum desses
módulos for carregado.
"""
