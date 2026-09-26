# -*- coding: utf-8 -*-
"""Registro de parametros do CMPLDW, com a procedencia de cada valor.

Duas fontes, e apenas duas:

* **WECC** -- *WECC Composite Load Model Specification*, Modeling and
  Validation Subcommittee, abril de 2021. Define a estrutura, os nomes dos
  campos e as equacoes. Poucos numeros: o fator de carregamento padrao 0,8,
  a tensao de quebra 0,86 pu, o piso 0,95 pu no barramento de carga, os
  criterios de aplicabilidade e `Ll = 0,80 Lpp`.

* **REF** -- conjunto de parametros completo publicado em formato PSLF DYD
  no apendice de Q. Huang, S. Jin, R. Diao, B. Palmer et al., *A Reference
  Implementation of WECC Composite Load Model in Matlab and GridPACK*
  (arXiv:1708.00939), barra 90 do caso IEEE de 300 barras. E dali que vem
  cada valor numerico de referencia deste registro.

O que **nao** e dessas fontes recebe rotulo proprio:

* **DERIVADO** -- calculado com dado nosso (capacidade de fronteira, tensao
  secundaria, composicao de classe medida no Mapa Inteligente).
* **PREMISSA** -- hipotese versionada aqui, com o motivo escrito.
* **A_CALIBRAR** -- nao afirmado. Exige ensaio, medicao de campo ou base
  cadastral. Fica com o valor de referencia e o rotulo, jamais apresentado
  como resultado nosso.

A regra que organiza o modulo: **nenhum numero sem procedencia**. E a mesma
do resto do projeto, aplicada a um objeto em que a tentacao de inventar e
maior, porque o CMPLDW tem mais de cem campos e quase nenhum e observavel a
partir de dado aberto.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Rotulos de procedencia.
WECC = "WECC"
REF = "REF"
DERIVADO = "DERIVADO"
PREMISSA = "PREMISSA"
A_CALIBRAR = "A_CALIBRAR"

ORIGENS = {
    WECC: "Definido na especificacao WECC do CLM (abril de 2021).",
    REF: "Conjunto de referencia publicado em arXiv:1708.00939, apendice "
         "(formato PSLF DYD, barra 90 do IEEE 300 barras).",
    DERIVADO: "Calculado a partir de dado observado por esta ferramenta.",
    PREMISSA: "Hipotese versionada neste repositorio, com justificativa.",
    A_CALIBRAR: "Nao afirmado. Requer ensaio, medicao de campo ou base "
                "cadastral; exibido com o valor de referencia apenas.",
}

FONTES = {
    "WECC": {
        "titulo": "WECC Composite Load Model Specification",
        "autor": "WECC Modeling and Validation Subcommittee",
        "data": "abril de 2021 (aprovado em 27/01/2015)",
        "url": "https://www.wecc.org/sites/default/files/documents/meeting/"
               "2024/WECC%20Comp%20Load%20Model%20Specification_final.pdf",
    },
    "REF": {
        "titulo": "A Reference Implementation of WECC Composite Load Model "
                  "in Matlab and GridPACK",
        "autor": "Q. Huang, S. Jin, R. Diao, B. Palmer et al.",
        "data": "arXiv:1708.00939, apendice",
        "url": "https://arxiv.org/pdf/1708.00939",
    },
    "NERC": {
        "titulo": "Reliability Guideline - Developing Load Model Composition "
                  "Data",
        "autor": "NERC Load Modeling Task Force",
        "data": "marco de 2017",
        "url": "https://www.nerc.com/comm/RSTC_Reliability_Guidelines/"
               "Reliability_Guideline_-_Load_Model_Composition_-_2017-02-28.pdf",
        "nota": "Fonte indicada para calibrar a composicao por classe. Nao "
                "consultada nesta versao: o servidor nega acesso automatizado "
                "(HTTP 403). Consta como proximo passo, nao como base dos "
                "numeros abaixo.",
    },
}


@dataclass(frozen=True)
class Param:
    """Um campo do cartao CMPLDW."""
    nome: str
    bloco: str
    descricao: str
    unidade: str = "pu"
    ref: float | None = None
    origem: str = REF
    nota: str = ""

    def as_dict(self, valor=None, origem=None, nota=None) -> dict:
        return {
            "nome": self.nome, "bloco": self.bloco,
            "descricao": self.descricao, "unidade": self.unidade,
            "referencia": self.ref,
            "valor": self.ref if valor is None else valor,
            "origem": self.origem if origem is None else origem,
            "nota": self.nota if nota is None else nota,
        }


# ---------------------------------------------------------------------------
# Blocos
# ---------------------------------------------------------------------------

BLOCOS = {
    "transformador": "Transformador da subestacao, com comutacao em carga",
    "alimentador": "Equivalente do alimentador de distribuicao",
    "fracoes": "Reparticao da carga entre os seis componentes",
    "estatica": "Carga estatica (ZIP com dependencia de frequencia)",
    "eletronica": "Carga eletronica",
    "motor_a": "Motor A -- trifasico, baixa inercia, conjugado constante",
    "motor_b": "Motor B -- trifasico, inercia media, conjugado ~ w^2",
    "motor_c": "Motor C -- trifasico, alta inercia, conjugado ~ w^2",
    "motor_d": "Motor D -- compressor monofasico, modelo por desempenho",
}

#: O que distingue os tres motores trifasicos. Nao ha campo "tipo de
#: equipamento" no CMPLDW: a diferenca esta inteiramente em H e Etrq, que o
#: conjunto de referencia fixa. A leitura de equipamento e a convencional da
#: literatura de modelagem de carga, e esta rotulada como tal.
MOTORES_3F = {
    "motor_a": {"h": 0.3, "etrq": 0.0,
                "leitura": "compressores e cargas de conjugado constante",
                "trip_uv": False},
    "motor_b": {"h": 0.5, "etrq": 2.0,
                "leitura": "ventiladores e ventilacao forcada",
                "trip_uv": True},
    "motor_c": {"h": 1.0, "etrq": 2.0,
                "leitura": "bombas e cargas de alta inercia",
                "trip_uv": True},
}

# ---------------------------------------------------------------------------
# Transformador -- valores do conjunto de referencia (DYD)
# ---------------------------------------------------------------------------

TRAFO = [
    Param("MVA", "transformador",
          "Base MVA. Positivo e a base; negativo e fator de carregamento "
          "(base = MW/|x|); zero usa o padrao 0,8.",
          "MVA", -0.8, WECC,
          "O fator padrao 0,8 e da especificacao; o -0,8 do conjunto de "
          "referencia coincide com ele."),
    Param("Xxf", "transformador",
          "Reatancia do transformador. Zero omite o transformador -- e o "
          "que se faz quando ele ja esta no caso de fluxo de potencia.",
          "pu", 0.0600, REF),
    Param("Tfixhs", "transformador", "Tape fixo do lado de alta.", "pu", 1.0000, REF),
    Param("Tfixls", "transformador", "Tape fixo do lado de baixa.", "pu", 1.0000, REF),
    Param("LTC", "transformador",
          "Habilita a comutacao em carga na simulacao dinamica. No conjunto "
          "de referencia esta em zero: atua na inicializacao e fica inerte "
          "no transitorio.",
          "-", 0.0, REF),
    Param("Tmin", "transformador", "Tape minimo.", "pu", 0.9000, REF),
    Param("Tmax", "transformador", "Tape maximo.", "pu", 1.1000, REF),
    Param("step", "transformador", "Passo do comutador.", "pu", 0.006250, REF),
    Param("Vmin", "transformador", "Tensao minima regulada no lado de baixa.",
          "pu", 1.00, REF),
    Param("Vmax", "transformador", "Tensao maxima regulada no lado de baixa.",
          "pu", 1.0400, REF),
    Param("Tdel", "transformador", "Atraso para iniciar a comutacao.", "s", 30.0000, REF),
    Param("Ttap", "transformador", "Atraso entre passos sucessivos.", "s", 5.0000, REF),
    Param("Rcmp", "transformador",
          "Resistencia de compensacao de queda na linha.", "pu", 0.0000, REF),
    Param("Xcmp", "transformador",
          "Reatancia de compensacao. Com Rcmp/Xcmp nao nulos, o comutador "
          "regula Vls - (Rcmp + jXcmp) Ils.", "pu", 0.0000, REF),
]

# ---------------------------------------------------------------------------
# Alimentador
# ---------------------------------------------------------------------------

ALIMENTADOR = [
    Param("Bss", "alimentador",
          "Susceptancia do banco shunt no barramento de baixa.", "pu", 0.04, REF),
    Param("Rfdr", "alimentador", "Resistencia serie do alimentador.", "pu", 0.0400, REF),
    Param("Xfdr", "alimentador", "Reatancia serie do alimentador.", "pu", 0.0400, REF),
    Param("Fb", "alimentador",
          "Fracao da compensacao reativa do alimentador alocada na "
          "subestacao. Em PSS/E e sempre zero.", "-", 0.0000, REF),
]

# ---------------------------------------------------------------------------
# Fracoes -- os campos que esta ferramenta de fato calcula
# ---------------------------------------------------------------------------

FRACOES = [
    Param("Fma", "fracoes", "Fracao do motor A.", "-", 0.5, REF),
    Param("Fmb", "fracoes", "Fracao do motor B.", "-", 0.00, REF),
    Param("Fmc", "fracoes", "Fracao do motor C.", "-", 0.00, REF),
    Param("Fmd", "fracoes", "Fracao do motor D.", "-", 0.30, REF),
    Param("Fel", "fracoes", "Fracao da carga eletronica.", "-", 0.0000, REF),
    Param("Mtypa", "fracoes", "Tipo do motor A (3 = trifasico, 1 = monofasico).",
          "-", 3.0, REF),
    Param("Mtypb", "fracoes", "Tipo do motor B.", "-", 3.0, REF),
    Param("Mtypc", "fracoes", "Tipo do motor C.", "-", 3.0, REF),
    Param("Mtypd", "fracoes", "Tipo do motor D.", "-", 1.0, REF),
]

# ---------------------------------------------------------------------------
# Carga estatica e eletronica
# ---------------------------------------------------------------------------

ESTATICA = [
    Param("PFs", "estatica", "Fator de potencia da carga estatica.", "-", 0.90000, REF),
    Param("P1e", "estatica", "Expoente do primeiro termo de P.", "-", 2.0000, REF),
    Param("P1c", "estatica", "Coeficiente do primeiro termo de P.", "-", 1.0, REF),
    Param("P2e", "estatica", "Expoente do segundo termo de P.", "-", 1.0000, REF),
    Param("P2c", "estatica", "Coeficiente do segundo termo de P.", "-", 0.00000, REF),
    Param("Pfrq", "estatica", "Sensibilidade de P a frequencia.", "-", 1.0000, REF),
    Param("Q1e", "estatica", "Expoente do primeiro termo de Q.", "-", 2.0000, REF),
    Param("Q1c", "estatica", "Coeficiente do primeiro termo de Q.", "-", 1.00000, REF),
    Param("Q2e", "estatica", "Expoente do segundo termo de Q.", "-", 1.0, REF),
    Param("Q2c", "estatica", "Coeficiente do segundo termo de Q.", "-", 0.0000, REF),
    Param("Qfrq", "estatica", "Sensibilidade de Q a frequencia.", "-", -1.0000, REF),
]

ELETRONICA = [
    Param("PFel", "eletronica", "Fator de potencia da carga eletronica.",
          "-", 0.9000, REF),
    Param("Vd1", "eletronica",
          "Tensao abaixo da qual a carga eletronica comeca a cair.", "pu", 0.8000, REF),
    Param("Vd2", "eletronica",
          "Tensao abaixo da qual a carga eletronica e nula.", "pu", 0.7000, REF),
    Param("Frcel", "eletronica",
          "Fracao que se recupera apos desligamento por subtensao. Zero no "
          "conjunto de referencia: nada religa.", "-", 0.0000, REF),
]

# ---------------------------------------------------------------------------
# Motores trifasicos
# ---------------------------------------------------------------------------

def _motor_3f(bloco: str, lfm: float, rs: float, ls: float, lp: float,
              lpp: float, tpo: float, tppo: float, h: float, etrq: float,
              vtr1: float, ttr1: float, ftr1: float, vrc1: float, trc1: float,
              vtr2: float, ttr2: float, ftr2: float, vrc2: float,
              trc2: float) -> list[Param]:
    """Parametros de um motor trifasico.

    Os eletricos vao como `A_CALIBRAR`: sao propriedades de maquina, obtidas
    em ensaio ou estimadas por ajuste a oscilografia. Esta ferramenta nao os
    observa, e imprimi-los como se fossem resultado nosso seria inventar.
    """
    el = A_CALIBRAR
    nota_el = ("Parametro eletrico de maquina. Exibido com o valor do "
               "conjunto de referencia; exige ensaio ou ajuste a "
               "oscilografia para ser afirmado.")
    return [
        Param("LFm", bloco, "Fator de carregamento, define a base MVA do motor.",
              "-", lfm, REF),
        Param("Rs", bloco, "Resistencia de estator.", "pu", rs, el, nota_el),
        Param("Ls", bloco, "Reatancia sincrona.", "pu", ls, el, nota_el),
        Param("Lp", bloco, "Reatancia transitoria.", "pu", lp, el, nota_el),
        Param("Lpp", bloco, "Reatancia subtransitoria.", "pu", lpp, el, nota_el),
        Param("Ll", bloco,
              "Reatancia de dispersao. Em CMLDXXU2 e fixada em 0,80 Lpp.",
              "pu", round(0.80 * lpp, 6), WECC,
              "A relacao Ll = 0,80 Lpp e da especificacao, nota da secao do "
              "motor trifasico."),
        Param("Tpo", bloco, "Constante de tempo transitoria a vazio.", "s", tpo,
              el, nota_el),
        Param("Tppo", bloco, "Constante de tempo subtransitoria a vazio.", "s",
              tppo, el, nota_el),
        Param("H", bloco,
              "Constante de inercia. E um dos dois campos que distinguem os "
              "motores A, B e C.", "s", h, REF),
        Param("Etrq", bloco,
              "Expoente de velocidade do conjugado mecanico: 0 e conjugado "
              "constante, 2 e proporcional ao quadrado da velocidade. O "
              "outro campo que distingue os tres motores.", "-", etrq, REF),
        Param("Vtr1", bloco, "Tensao do primeiro estagio de subtensao.", "pu",
              vtr1, REF),
        Param("Ttr1", bloco, "Temporizacao do primeiro estagio.", "s", ttr1, REF),
        Param("Ftr1", bloco, "Fracao desligada no primeiro estagio.", "-", ftr1, REF),
        Param("Vrc1", bloco, "Tensao de religamento do primeiro estagio.", "pu",
              vrc1, REF),
        Param("Trc1", bloco, "Atraso de religamento do primeiro estagio.", "s",
              trc1, REF),
        Param("Vtr2", bloco, "Tensao do segundo estagio de subtensao.", "pu",
              vtr2, REF),
        Param("Ttr2", bloco, "Temporizacao do segundo estagio.", "s", ttr2, REF),
        Param("Ftr2", bloco,
              "Fracao desligada no segundo estagio. As fracoes dos dois "
              "estagios sao cumulativas.", "-", ftr2, REF),
        Param("Vrc2", bloco, "Tensao de religamento do segundo estagio.", "pu",
              vrc2, REF),
        Param("Trc2", bloco, "Atraso de religamento do segundo estagio.", "s",
              trc2, REF),
    ]


MOTOR_A = _motor_3f("motor_a", 0.800, 0.0100, 3.1000, 0.1779, 0.153900,
                    1.634, 0.0045, 0.3, 0.0000,
                    0.0, 999.0, 0.0000, 999.0, 999.0,
                    0.0, 999.0, 0.0, 999.0, 999.0)

MOTOR_B = _motor_3f("motor_b", 0.8000, 0.0200, 3.6000, 0.1800, 0.1800,
                    1.600, 0.0200, 0.5000, 2.0000,
                    0.80, 2.0, 1.0000, 1.0000, 999.0000,
                    0.60, 0.16, 1.0000, 999.0000, 999.0000)

MOTOR_C = _motor_3f("motor_c", 0.800, 0.0100, 3.6000, 0.1800, 0.1800,
                    1.600, 0.0200, 1.0000, 2.0000,
                    0.80, 2.0, 1.0000, 1.0000, 999.0000,
                    0.60, 0.16, 1.0000, 999.0000, 999.0000)

# ---------------------------------------------------------------------------
# Compressor monofasico
# ---------------------------------------------------------------------------

_NOTA_ENSAIO = ("Obtido em ensaio de laboratorio pelo WECC Load Modeling Task "
                "Force sobre unidades reais de ar condicionado. Nao "
                "observavel por dado aberto.")

MOTOR_D = [
    Param("LFm", "motor_d", "Fator de carregamento.", "-", 0.8000, REF),
    Param("CompPF", "motor_d", "Fator de potencia do compressor.", "-", 0.9700, REF),
    Param("Vstall", "motor_d",
          "Tensao de travamento. Abaixo dela, por Tstall, o compressor "
          "trava.", "pu", 0.6000, A_CALIBRAR, _NOTA_ENSAIO),
    Param("Rstall", "motor_d", "Resistencia de rotor bloqueado.", "pu", 0.1240,
          A_CALIBRAR, _NOTA_ENSAIO),
    Param("Xstall", "motor_d", "Reatancia de rotor bloqueado.", "pu", 0.1140,
          A_CALIBRAR, _NOTA_ENSAIO),
    Param("Tstall", "motor_d",
          "Temporizacao do travamento. Valor negativo aciona a "
          "caracteristica tempo-tensao inversa da figura 5 da "
          "especificacao.", "s", 0.0330, A_CALIBRAR, _NOTA_ENSAIO),
    Param("Frst", "motor_d",
          "Fracao que consegue reiniciar apos travar. Zero no conjunto de "
          "referencia: nenhum compressor reinicia.", "-", 0.000, REF),
    Param("Vrst", "motor_d", "Tensao acima da qual o reinicio pode ocorrer.",
          "pu", 0.9000, REF),
    Param("Trst", "motor_d", "Atraso de reinicio.", "s", 999.0, REF),
    Param("Fuvr", "motor_d",
          "Fracao protegida por rele de subtensao. Uma vez desligada, nao "
          "religa no restante da simulacao.", "-", 0.0000, REF),
    Param("Vtr1", "motor_d", "Tensao do primeiro estagio do rele.", "pu", 0.0000, REF),
    Param("Ttr1", "motor_d", "Temporizacao do primeiro estagio.", "s", 0.2, REF),
    Param("Vtr2", "motor_d", "Tensao do segundo estagio do rele.", "pu", 0.0000, REF),
    Param("Ttr2", "motor_d", "Temporizacao do segundo estagio.", "s", 5.0, REF),
    Param("Vc1off", "motor_d", "Tensao em que o contator inicia a abertura.",
          "pu", 0.45000, A_CALIBRAR, _NOTA_ENSAIO),
    Param("Vc2off", "motor_d", "Tensao em que a abertura se completa.",
          "pu", 0.3500, A_CALIBRAR, _NOTA_ENSAIO),
    Param("Vc1on", "motor_d", "Tensao em que o religamento se completa.",
          "pu", 0.5000, A_CALIBRAR, _NOTA_ENSAIO),
    Param("Vc2on", "motor_d", "Tensao em que o religamento inicia.",
          "pu", 0.4000, A_CALIBRAR, _NOTA_ENSAIO),
    Param("Tth", "motor_d", "Constante de tempo termica.", "s", 10.0000,
          A_CALIBRAR, _NOTA_ENSAIO),
    Param("Th1t", "motor_d",
          "Temperatura em que a protecao termica comeca a atuar.", "pu", 1.3,
          A_CALIBRAR, _NOTA_ENSAIO),
    Param("Th2t", "motor_d",
          "Temperatura em que a atuacao se completa.", "pu", 4.3,
          A_CALIBRAR, _NOTA_ENSAIO),
    Param("Tv", "motor_d", "Atraso de medicao de tensao.", "s", 0.0500, REF),
]

REGISTRO: list[Param] = (TRAFO + ALIMENTADOR + FRACOES + ESTATICA + ELETRONICA
                         + MOTOR_A + MOTOR_B + MOTOR_C + MOTOR_D)


def by_block() -> dict[str, list[Param]]:
    out: dict[str, list[Param]] = {k: [] for k in BLOCOS}
    for p in REGISTRO:
        out.setdefault(p.bloco, []).append(p)
    return out


def get(bloco: str, nome: str) -> Param | None:
    for p in REGISTRO:
        if p.bloco == bloco and p.nome == nome:
            return p
    return None


def reference_value(bloco: str, nome: str, default=None):
    p = get(bloco, nome)
    return default if p is None else p.ref


def counts() -> dict[str, int]:
    """Quantos campos de cada procedencia. E a medida honesta de cobertura."""
    out: dict[str, int] = {}
    for p in REGISTRO:
        out[p.origem] = out.get(p.origem, 0) + 1
    return out
