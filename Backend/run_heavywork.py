"""O.R.A.C.U.L.O. — trabalho pesado: dados brutos -> processamento -> modelos -> banco.

Como rodar (de dentro de Backend/, com o .venv ativo):

    python run_heavywork.py

Sem argumentos: o comportamento vem de config/heavywork.yaml. Pode ser rodado a qualquer
momento; cada etapa pula o que já está em dia:

    1. ingestao       baixa só o que falta ou foi republicado nas fontes (ONS, ANEEL)
    2. processamento  refaz as tabelas de data/processed se os dados, o código ou a config mudaram
    3. treino_carga, treino_curtailment      modelos com split cronológico
    4. previsao_carga, previsao_curtailment  previsões fora da amostra (modo replay) + backtest
    5. publicacao     monta o contrato (6 recursos) e grava no banco

O serviço web (API FastAPI + dashboard) NÃO roda nada disso: ele só lê o banco que a etapa 5
preenche. Arquitetura e decisões em docs/Oraculo_planejamento.md §13.1.

Uma execução por vez (trava em data/_heavywork.lock). O estado da última execução bem-sucedida
de cada etapa fica em data/_estado_heavywork.json (local, fora do git). Sai com código 1 se
alguma etapa falhar.
"""
import logging
import sys

from src.heavywork import etapas as etapas_oraculo
from src.heavywork.orquestrador import Estado, resumo, rodar, validar_config
from src.utils import log as log_util
from src.utils.config import carregar
from src.utils.paths import ESTADO_HEAVYWORK, TRAVA_HEAVYWORK
from src.utils.trava import TravaDeProcesso


def main() -> int:
    log_util.configurar()
    etapas = etapas_oraculo.montar()
    ligadas, forcar = validar_config(carregar("heavywork"), etapas)
    with TravaDeProcesso(TRAVA_HEAVYWORK, "run_heavywork"):
        resultados = rodar(etapas, Estado.ler(ESTADO_HEAVYWORK), ligadas, forcar)
    logging.getLogger("heavywork").info("resumo:\n%s", resumo(resultados))
    return 1 if any(r.status == "falhou" for r in resultados) else 0


if __name__ == "__main__":
    sys.exit(main())
