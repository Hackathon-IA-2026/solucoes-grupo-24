"""As etapas concretas do run_heavywork.py, na ordem (docs/Oraculo_planejamento.md §13.1).

Cada etapa só CHAMA funções que já existem nos módulos do src/ (DRY: a lógica mora num lugar
só; a linha de comando de depuração de cada módulo chama as mesmas funções).

Etapas ainda sem implementação ficam declaradas com executar=None: aparecem no resumo como
"nao_implementada" em vez de fingir que rodaram.
"""
from __future__ import annotations

from src.analise import episodios as analise_episodios
from src.analise import historico as analise_historico
from src.db.sessao import ARQUIVO_SQLITE, url_banco
from src.heavywork.orquestrador import Etapa
from src.ingestion import download
from src.models import carga as modelos_carga
from src.models import curtailment as modelos_curtailment
from src.models import relatorio_carga, relatorio_curtailment
# O TFT (src.models.tft) NÃO é importado aqui: ele carrega o torch, pesado. As funções abaixo o
# importam só quando a etapa roda; as impressões digitais usam só caminhos de mc (carga.py).
from src.processing import mapeamento, tabelas
from src.processing import saidas as processamento_saidas
from src.publicacao import montar as publicacao
from src.spatial import bdgd as espacial_bdgd
from src.spatial import construir as espacial
from src.spatial import saidas as espacial_saidas
from src.utils.config import carregar
from src.utils.impressao import codigo_de, de_arquivos, de_objeto
from src.utils.joins import ARQUIVO_MAPEAMENTO
from src.utils.paths import CONFIG, DASHBOARD_MOCK, RAIZ


# --------------------------------------------------------------------------- 1. ingestão
def _ingerir() -> str:
    san = download.executar()
    erros = download.erros_de_download()
    divergentes = san[san["divergencia"]]["conjunto"].tolist() if len(san) else []
    partes = [f"{len(san)} conjuntos"]
    if erros:
        # Não interrompe: o arquivo anterior continua intacto (escrita atômica) e a próxima
        # execução tenta de novo. Fica visível no resumo e em docs/reports/download_log.csv.
        partes.append(f"{len(erros)} arquivos com erro (ver docs/reports/download_log.csv)")
    if divergentes:
        partes.append(f"volume fora do esperado: {divergentes}")
    return "; ".join(partes)


def _estimativa_ingestao() -> str:
    ja_baixados = sum(1 for _, v in download.Manifesto(download.MANIFESTO_PATH).itens()
                      if v.get("status") == "ok")
    if ja_baixados == 0:
        return carregar("heavywork")["estimativas"]["ingestao_completa"]
    return f"incremental: {ja_baixados} arquivos já baixados; só entra o que for novo ou republicado"


# --------------------------------------------------------------------------- 2. processamento
# O que, se mudar, invalida as tabelas processadas: o que foi baixado, o código que processa
# (os módulos e tudo que importam do projeto: codigo_de segue os imports, então uma feature
# nova de modelo não reprocessa nada, e um utilitário usado pelo processamento sim) e os
# parâmetros.
_CONFIG_PROCESSAMENTO = [CONFIG / "processamento.yaml", CONFIG / "mapeamento_areas.yaml",
                         CONFIG / "projeto.yaml"]


def _entradas_processamento() -> str:
    codigo = {*codigo_de("src.processing.tabelas", RAIZ), *codigo_de("src.processing.mapeamento", RAIZ)}
    return de_objeto([download.impressao_digital(),
                      de_arquivos([*sorted(codigo), *_CONFIG_PROCESSAMENTO], RAIZ)])


def _processar() -> str:
    mapeamento.construir()
    cob = tabelas.construir()
    total = cob.groupby("tabela")["linhas"].sum()
    return "; ".join(f"{tab}: {n:,} linhas" for tab, n in total.items())


# --------------------------------------------------------------------------- 2b. espacialização
# Fase 6: BDGD -> áreas de influência -> MMGD por área de influência -> pesos de carga (src/spatial/construir.py).
# Entradas: só os downloads de que ela depende (BDGD, cadastro da ANEEL, malha do IBGE), o
# código (construir e tudo que ele importa), a config espacial, a do projeto (caminho do fator de
# correção do satélite) e o próprio arquivo do fator, se houver.
def _conjuntos_espaciais() -> set[str]:
    return ({d.apelido_bdgd for d in espacial_bdgd.distribuidoras()}
            | {espacial.APELIDO_MALHA_UF, processamento_saidas.APELIDO_ANEEL_MMGD})


def _entradas_espacializacao() -> str:
    arquivos = [*codigo_de("src.spatial.construir", RAIZ), CONFIG / "espacial.yaml", CONFIG / "projeto.yaml"]
    fator = carregar("projeto")["caminho_fator_correcao"]
    if fator:
        arquivos.append(RAIZ / fator)
    return de_objeto([download.impressao_digital(_conjuntos_espaciais()), de_arquivos(arquivos, RAIZ)])


# --------------------------------------------------------------------------- 3. treino
# Uma etapa por modelo (carga, curtailment), cada uma com a própria impressão digital: mexer
# no classificador de curtailment não retreina a carga, e vice-versa.
# Entradas do treino: as tabelas processadas que ele lê + o código (o módulo e tudo que ele
# importa do projeto, via codigo_de: nunca uma lista escrita à mão) + as configs. Mudou o split,
# um hiperparâmetro ou uma feature? A etapa refaz sozinha. Mexeu só em outro modelo? Não refaz.
def _entradas_treino_carga() -> str:
    arquivos = [processamento_saidas.SAIDA_CARGA, processamento_saidas.SAIDA_CALENDARIO,
                *codigo_de("src.models.carga", RAIZ),
                CONFIG / "modelos_carga.yaml", CONFIG / "processamento.yaml"]
    return de_arquivos(arquivos, RAIZ)


def _entradas_treino_tft() -> str:
    # As mesmas tabelas do LightGBM + o código do TFT (e tudo que ele importa, inclusive
    # src/models/carga.py: split e calibração são os mesmos) + as duas configs.
    arquivos = [processamento_saidas.SAIDA_CARGA, processamento_saidas.SAIDA_CALENDARIO,
                *codigo_de("src.models.tft", RAIZ),
                CONFIG / "modelos_tft.yaml", CONFIG / "modelos_carga.yaml", CONFIG / "processamento.yaml"]
    return de_arquivos(arquivos, RAIZ)


def _treinar_tft() -> str:
    from src.models import tft  # import tardio (torch)
    return tft.treinar()


def _entradas_treino_curtailment() -> str:
    # config da carga entra: os horizontes do curtailment são os da carga
    arquivos = [processamento_saidas.SAIDA_ROTULOS, processamento_saidas.SAIDA_CARGA,
                processamento_saidas.SAIDA_CALENDARIO,
                *codigo_de("src.models.curtailment", RAIZ), CONFIG / "modelos_curtailment.yaml",
                CONFIG / "modelos_carga.yaml", CONFIG / "processamento.yaml"]
    return de_arquivos(arquivos, RAIZ)


# --------------------------------------------------------------------------- 4. previsão
# Entradas do treino + os modelos salvos (treino refeito -> previsões refeitas) + o código do
# relatório do backtest.
def _entradas_previsao_tft() -> str:
    return de_objeto([_entradas_treino_tft(), de_arquivos([_arq_ckpt_tft()], RAIZ)])


def _arq_ckpt_tft():
    # Mesmo caminho de src/models/tft.py (ARQ_CKPT), sem importar o torch para calcular a impressão.
    return modelos_carga.ARQ_PREVISOES_TFT.with_name("tft.ckpt")


def _prever_tft() -> str:
    from src.models import tft  # import tardio (torch)
    return tft.prever()


# O relatório do backtest de carga compara TODOS os modelos, inclusive o TFT: as previsões do
# TFT entram nas entradas desta etapa (TFT refeito -> relatório refeito).
def _entradas_previsao_carga() -> str:
    return de_objeto([_entradas_treino_carga(),
                      de_arquivos([modelos_carga.ARQ_MODELOS, modelos_carga.ARQ_PREVISOES_TFT,
                                   *codigo_de("src.models.relatorio_carga", RAIZ)], RAIZ)])


def _entradas_previsao_curtailment() -> str:
    return de_objeto([_entradas_treino_curtailment(),
                      de_arquivos([modelos_curtailment.ARQ_MODELOS,
                                   *codigo_de("src.models.relatorio_curtailment", RAIZ)], RAIZ)])


def _prever_carga() -> str:
    return f"{modelos_carga.prever()}; {relatorio_carga.escrever()}"


def _prever_curtailment() -> str:
    return f"{modelos_curtailment.prever()}; {relatorio_curtailment.escrever()}"


# --------------------------------------------------------------------------- 4b. análises do pitch
# Peça B (histórico mensal / Figura 1) e Peça C (episódios, lead time, caso real): src/analise/.
# Entradas: as tabelas que elas leem, as previsões do classificador (lead time e caso real), o
# código e a config. Não tocam o banco: só docs/reports (e a tabela de episódios).
def _entradas_analises() -> str:
    arquivos = [processamento_saidas.SAIDA_CURTAILMENT_MENSAL, processamento_saidas.SAIDA_CAPACIDADE_MMGD,
                processamento_saidas.SAIDA_CARGA, processamento_saidas.SAIDA_ROTULOS,
                modelos_curtailment.ARQ_PREVISOES, CONFIG / "analises.yaml",
                CONFIG / "modelos_curtailment.yaml", CONFIG / "modelos_carga.yaml",
                *codigo_de("src.analise.historico", RAIZ), *codigo_de("src.analise.episodios", RAIZ)]
    return de_arquivos(arquivos, RAIZ)


def _analisar() -> str:
    return f"{analise_historico.escrever()}; {analise_episodios.escrever()}"


# --------------------------------------------------------------------------- 5. publicação
# Entradas: as tabelas processadas que a publicação lê, os mocks do dashboard (recursos ainda
# sem saída real), o código de contrato/banco/publicação, as migrations, a config e o PRÓPRIO
# endereço do banco (trocar DATABASE_URL publica de novo no banco novo).
def _entradas_publicacao() -> str:
    arquivos = [processamento_saidas.SAIDA_CARGA, processamento_saidas.SAIDA_CAPACIDADE_MMGD,
                processamento_saidas.SAIDA_CALENDARIO, processamento_saidas.SAIDA_CARGA_AREA,
                processamento_saidas.SAIDA_USINAS_CADASTRO, processamento_saidas.SAIDA_CLIMA_UF,
                espacial_saidas.SAIDA_MMGD_AREA_INFLUENCIA, espacial_saidas.SAIDA_MMGD_DIARIA,
                espacial_saidas.SAIDA_CARGA_AREA_INFLUENCIA, espacial_saidas.SAIDA_AREAS_INFLUENCIA_GEOJSON,
                CONFIG / "espacial.yaml",
                modelos_carga.ARQ_PREVISOES, modelos_carga.ARQ_PREVISOES_TFT,
                modelos_curtailment.ARQ_PREVISOES,
                modelos_curtailment.ARQ_MODELOS, modelos_curtailment.ARQ_USINAS,
                *sorted(DASHBOARD_MOCK.glob("*.json")), CONFIG / "publicacao.yaml",
                CONFIG / "modelos_carga.yaml", CONFIG / "modelos_curtailment.yaml",
                *codigo_de("src.publicacao.montar", RAIZ), RAIZ / "migrations"]
    # O manifesto de download entra inteiro (inclusive horários): o status das fontes da tela
    # Validação mostra a última sincronização, então um download novo publica de novo.
    manifesto = download.Manifesto(download.MANIFESTO_PATH).dados
    return de_objeto([url_banco(), manifesto, de_arquivos(arquivos, RAIZ.parent)])


def _saidas_publicacao() -> tuple:
    export = RAIZ / carregar("publicacao")["arquivo_export"]
    # Com o SQLite padrão, apagar o arquivo do banco também faz a etapa rodar de novo.
    return (export, ARQUIVO_SQLITE) if url_banco().startswith("sqlite") else (export,)


# --------------------------------------------------------------------------- lista
def montar() -> list[Etapa]:
    est = carregar("heavywork")["estimativas"]
    return [
        Etapa("ingestao",
              "baixa das fontes (ONS, ANEEL) só o que falta ou está desatualizado",
              executar=_ingerir, entradas=None, estimativa=_estimativa_ingestao),
        Etapa("processamento",
              "mapeamento subsistema x área + calendário, carga supervisionada e rótulos de curtailment",
              executar=_processar, entradas=_entradas_processamento,
              saidas=(ARQUIVO_MAPEAMENTO, *processamento_saidas.SAIDAS),
              estimativa=lambda: est["processamento"]),
        Etapa("espacializacao",
              "BDGD (LIGHT + Enel RJ) -> áreas de influência por subestação, MMGD por área de influência (desempate com a ANEEL) e pesos de carga",
              executar=espacial.construir, entradas=_entradas_espacializacao, saidas=espacial_saidas.SAIDAS,
              estimativa=lambda: est["espacializacao"]),
        # 3. Treino (um por modelo) e 4. previsão (modo replay). O TFT (Fatia 3) é mais um par
        # treino/previsão; a previsão dele vem ANTES da previsao_carga, que escreve o relatório
        # comparando todos os modelos.
        Etapa("treino_carga",
              "baselines + LightGBM quantílico da carga supervisionada, split cronológico",
              executar=modelos_carga.treinar, entradas=_entradas_treino_carga,
              saidas=(modelos_carga.ARQ_MODELOS,), estimativa=lambda: est["treino_carga"]),
        Etapa("treino_tft",
              "TFT com perda assimétrica por patamar (P10/P50/P90), mesmo split da carga",
              executar=_treinar_tft, entradas=_entradas_treino_tft,
              saidas=(_arq_ckpt_tft(),), estimativa=lambda: est["treino_tft"]),
        Etapa("treino_curtailment",
              "classificador de curtailment por razão (ENE, CNF) + montante, split cronológico",
              executar=modelos_curtailment.treinar, entradas=_entradas_treino_curtailment,
              saidas=(modelos_curtailment.ARQ_MODELOS,), estimativa=lambda: est["treino_curtailment"]),
        Etapa("previsao_tft",
              "previsões do TFT fora da amostra de cada semi-hora (modo replay)",
              executar=_prever_tft, entradas=_entradas_previsao_tft,
              saidas=(modelos_carga.ARQ_PREVISOES_TFT,), estimativa=lambda: est["previsao_tft"]),
        Etapa("previsao_carga",
              "previsões de carga fora da amostra de cada semi-hora (modo replay) + relatório do backtest",
              executar=_prever_carga, entradas=_entradas_previsao_carga,
              saidas=(modelos_carga.ARQ_PREVISOES, relatorio_carga.ARQ_MD),
              estimativa=lambda: est["previsao_carga"]),
        Etapa("previsao_curtailment",
              "risco de curtailment fora da amostra de cada usina e semi-hora + relatório do backtest",
              executar=_prever_curtailment, entradas=_entradas_previsao_curtailment,
              saidas=(modelos_curtailment.ARQ_PREVISOES, modelos_curtailment.ARQ_USINAS,
                      relatorio_curtailment.ARQ_MD),
              estimativa=lambda: est["previsao_curtailment"]),
        Etapa("analises",
              "Peça B (histórico mensal do corte por razão, Figura 1) e Peça C (episódios, lead time, caso real)",
              executar=_analisar, entradas=_entradas_analises,
              saidas=(analise_historico.ARQ_MD, analise_episodios.ARQ_MD),
              estimativa=lambda: est["analises"]),
        Etapa("publicacao",
              "monta os 6 recursos do contrato e grava no banco",
              executar=publicacao.publicar, entradas=_entradas_publicacao,
              saidas=_saidas_publicacao()),
    ]
