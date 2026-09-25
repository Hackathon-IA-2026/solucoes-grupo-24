# O.R.A.C.U.L.O.

> Previsão de carga e de risco de curtailment para o SIN, usando dados do ONS e a MMGD vista pela rede de distribuição.

## Demo

- **Link da demo:** TODO (Luiz)

## Tecnologias utilizadas

- Linguagem: Python 3.11+
- Framework(s): pandas, LightGBM, pytorch-forecasting, geopandas
- Banco de dados: DuckDB + Parquet particionado
- APIs / Serviços externos: dados.ons.org.br, MCP do ONS, ERA5 (Copernicus CDS), BDGD (ANEEL), Open Buildings, IBGE, OSM
- Dashboard: TODO (Luiz)

## Como rodar o projeto

```bash
# Clone o repositório
git clone https://github.com/Hackathon-IA-2026/solucoes-grupo-24.git
cd solucoes-grupo-24

# Instale as dependências
pip install -e .

# Rode o projeto
# pipeline em construção
```

## Pré-requisitos

- Python 3.11 ou 3.12
- Credencial do Copernicus CDS (arquivo `~/.cdsapirc`) para baixar o ERA5
- Documentação detalhada (schema do contrato de dados, inventário do portal ONS, status): [`docs/`](./docs)

## Licença

Este projeto está sob a licença MIT — veja o arquivo [LICENSE](./LICENSE) para mais detalhes.
