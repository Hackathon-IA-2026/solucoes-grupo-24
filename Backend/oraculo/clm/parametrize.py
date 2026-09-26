# -*- coding: utf-8 -*-
"""Parametrizacao sugerida do CMPLDW a partir do que esta ferramenta observa.

O CMPLDW tem mais de cem campos. Dado aberto brasileiro nao determina nem um
quinto deles. Este modulo existe para deixar essa fronteira explicita: dizer
quais campos a composicao de classe medida no Mapa Inteligente de fato
informa, quais saem do cadastro de subestacoes, e quais continuam sendo do
especialista.

O produto e um **cartao de parametros com procedencia campo a campo**, nao
um caso pronto para simular. A diferenca esta escrita no proprio cartao.

Destino: parametrizacao do CLM no ORGANON. Os campos do CMPLDW sao os mesmos
em PSS/E (CMLDxxU2), PSLF (cmpldw), PowerWorld, DSATools e ORGANON -- e a
razao de o cartao ser neutro em vez de ter a sintaxe de uma ferramenta.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import spec, theory

# ---------------------------------------------------------------------------
# Composicao por classe de consumo -- premissa versionada
# ---------------------------------------------------------------------------

#: Reparticao da carga de cada classe entre os componentes do CLM.
#:
#: Premissa, nao medicao. O raciocinio, por classe:
#:
#: * **Residencial** -- a carga motora e pequena e quase toda monofasica:
#:   compressor de refrigerador e de ar condicionado, que e o motor D. A
#:   carga eletronica e alta e crescente (fontes chaveadas, LED, TV,
#:   carregadores). O resto e resistivo -- chuveiro, no Brasil, e parcela
#:   relevante e puramente estatica.
#: * **Comercial** -- climatizacao central distribui entre compressores de
#:   conjugado constante (motor A) e ventilacao forcada (motor B); carga
#:   eletronica alta por iluminacao e equipamento de escritorio.
#: * **Industrial** -- predominio de bombas e cargas de alta inercia (motor
#:   C), fator de carga alto, pouca carga monofasica.
#: * **Rural** -- irrigacao e bombeamento, praticamente tudo motor C.
#:
#: A soma dos quatro motores de cada linha reproduz exatamente a fracao
#: motora ja publicada pelo Mapa Inteligente (`substations/mapper.py`), e ha
#: teste que exige essa coerencia. As duas telas nao podem divergir.
#:
#: A fonte indicada para substituir esta premissa por dado e o *Reliability
#: Guideline - Developing Load Model Composition Data* da NERC, com a
#: Pesquisa de Posse e Habitos de Consumo para adaptar ao uso final
#: brasileiro. Nenhuma das duas foi consultada nesta versao.
CLASS_COMPONENTS = {
    "residencial": {"Fma": 0.05, "Fmb": 0.03, "Fmc": 0.02, "Fmd": 0.12,
                    "Fel": 0.20},
    "comercial": {"Fma": 0.12, "Fmb": 0.10, "Fmc": 0.06, "Fmd": 0.10,
                  "Fel": 0.22},
    "industrial": {"Fma": 0.20, "Fmb": 0.12, "Fmc": 0.28, "Fmd": 0.02,
                   "Fel": 0.10},
    "rural": {"Fma": 0.06, "Fmb": 0.04, "Fmc": 0.43, "Fmd": 0.02,
              "Fel": 0.08},
}

COMPONENTES = ("Fma", "Fmb", "Fmc", "Fmd", "Fel")

#: Fracao motora por classe, como ja publicada pelo Mapa Inteligente. Fica
#: aqui apenas para o teste de coerencia; a fonte segue sendo o mapper.
MOTOR_FRACTION_ESPERADA = {"residencial": 0.22, "comercial": 0.38,
                           "industrial": 0.62, "rural": 0.55}

#: Raio mediano das 522 subestacoes de fronteira, em km. Ancora a escala de
#: impedancia do alimentador: a subestacao mediana recebe exatamente o valor
#: do conjunto de referencia, e as demais escalam com o comprimento.
RAIO_MEDIANO_KM = 3.34

#: Limites da escala, para nao extrapolar a premissa linear para fora de uma
#: faixa defensavel.
ESCALA_ALIMENTADOR_MIN = 0.35
ESCALA_ALIMENTADOR_MAX = 2.20


def normalize_mix(mix: dict) -> dict:
    """Normaliza a composicao de classe para somar 1, ignorando o que nao e classe."""
    m = {k: max(float(v), 0.0) for k, v in (mix or {}).items()
         if k in CLASS_COMPONENTS}
    total = sum(m.values())
    if total <= 0:
        return {"residencial": 0.5, "comercial": 0.3, "industrial": 0.1,
                "rural": 0.1}
    return {k: v / total for k, v in m.items()}


def fractions_from_mix(mix: dict, ac_factor: float = 1.0) -> dict:
    """Fracoes do CLM a partir da composicao de classe.

    Combinacao linear das linhas de `CLASS_COMPONENTS` pelos pesos de classe.
    O resto vai para a carga estatica, pela regra da especificacao.

    `ac_factor` escala a fracao do compressor monofasico (motor D). Existe
    porque **este e o parametro mais consequente e o menos conhecido no
    contexto brasileiro**: a penetracao de ar condicionado residencial no
    Brasil nao e a do sudoeste dos Estados Unidos, de onde vem o modelo, e o
    motor D e justamente o componente que governa a recuperacao lenta de
    tensao. Deixar a sensibilidade exposta e mais honesto do que fixar um
    numero que nao temos. O delta e devolvido a carga estatica, para que a
    soma continue fechando.
    """
    mix = normalize_mix(mix)
    fr = {c: 0.0 for c in COMPONENTES}
    contrib = {c: {} for c in COMPONENTES}
    for classe, peso in mix.items():
        for c in COMPONENTES:
            parcela = CLASS_COMPONENTS[classe][c] * peso
            fr[c] += parcela
            if peso > 0:
                contrib[c][classe] = round(parcela, 6)

    ac_factor = max(float(ac_factor), 0.0)
    fmd_base = fr["Fmd"]
    fr["Fmd"] = fmd_base * ac_factor

    (fma, fmb, fmc, fmd, fel), estatica = theory.static_remainder(
        fr["Fma"], fr["Fmb"], fr["Fmc"], fr["Fmd"], fr["Fel"])

    # A estatica e publicada como complemento exato dos cinco valores JA
    # arredondados, e nao como arredondamento do seu proprio valor. Sem isso,
    # a soma exibida fecha em 1,000001 e parece erro de modelo onde ha apenas
    # arredondamento -- num cartao de parametros, essa diferenca importa.
    arred = [round(x, 6) for x in (fma, fmb, fmc, fmd, fel)]
    estatica_pub = round(1.0 - sum(arred), 6) if estatica > 0 else 0.0

    return {
        "mix": {k: round(v, 6) for k, v in mix.items()},
        "Fma": arred[0], "Fmb": arred[1], "Fmc": arred[2],
        "Fmd": arred[3], "Fel": arred[4],
        "estatica": estatica_pub,
        "fracao_motora": round(sum(arred[:4]), 6),
        "contribuicao": contrib,
        "ac_factor": round(ac_factor, 4),
        "Fmd_sem_ajuste": round(fmd_base, 6),
    }


def feeder_scale(raio_km: float | None) -> float:
    """Escala de impedancia do alimentador pelo comprimento equivalente.

    A impedancia serie e proporcional ao comprimento. O raio de influencia
    calculado pelo Mapa Inteligente e o unico proxy de comprimento disponivel
    em dado aberto, e a escala ancora a subestacao mediana no valor de
    referencia. Premissa de primeira ordem, limitada a faixa
    [0,35 ; 2,20] para nao extrapolar.

    A especificacao observa que as ferramentas reajustam Rfdr e Xfdr na
    inicializacao para manter o barramento de carga acima de 0,95 pu -- ou
    seja, este valor e ponto de partida, nao palavra final.
    """
    if not raio_km or raio_km <= 0:
        return 1.0
    esc = float(raio_km) / RAIO_MEDIANO_KM
    return float(min(max(esc, ESCALA_ALIMENTADOR_MIN), ESCALA_ALIMENTADOR_MAX))


@dataclass(frozen=True)
class Contexto:
    """O que a ferramenta sabe da subestacao, e que alimenta o cartao."""
    nome: str = "-"
    uf: str = "-"
    subsistema: str = "-"
    mva_fronteira: float | None = None
    kv_secundario: float | None = None
    raio_km: float | None = None
    mix: dict | None = None
    mmgd_kwp: float | None = None
    confianca: str = "-"
    amostra: str = "-"


def build_card(ctx: Contexto, ac_factor: float = 1.0) -> dict:
    """Cartao completo de parametros, com procedencia campo a campo."""
    fr = fractions_from_mix(ctx.mix or {}, ac_factor)
    esc = feeder_scale(ctx.raio_km)
    blocos = spec.by_block()

    # Valores que substituimos no conjunto de referencia, com a procedencia.
    subs: dict[tuple[str, str], tuple[float, str, str]] = {}

    if ctx.mva_fronteira and ctx.mva_fronteira > 0:
        subs[("transformador", "MVA")] = (
            round(float(ctx.mva_fronteira), 2), spec.DERIVADO,
            "Capacidade de transformacao de fronteira somada para esta "
            "subestacao, do conjunto `capacidade-transformacao` do ONS.")

    for nome in ("Rfdr", "Xfdr"):
        base = spec.reference_value("alimentador", nome) or 0.0
        subs[("alimentador", nome)] = (
            round(base * esc, 6), spec.PREMISSA,
            f"Valor de referencia escalado por {esc:.3f}, razao entre o raio "
            f"de influencia desta subestacao e o raio mediano das de "
            f"fronteira ({RAIO_MEDIANO_KM:g} km).")

    for nome in COMPONENTES:
        subs[("fracoes", nome)] = (
            fr[nome], spec.DERIVADO,
            "Composicao de classe medida no Mapa Inteligente, combinada com "
            "a reparticao por classe declarada em `CLASS_COMPONENTS` "
            "(premissa).")

    linhas = []
    for bloco, params in blocos.items():
        for p in params:
            key = (bloco, p.nome)
            if key in subs:
                valor, origem, nota = subs[key]
                linhas.append(p.as_dict(valor, origem, nota))
            else:
                linhas.append(p.as_dict())

    cobertura = {}
    for ln in linhas:
        cobertura[ln["origem"]] = cobertura.get(ln["origem"], 0) + 1

    return {
        "subestacao": {"nome": ctx.nome, "uf": ctx.uf,
                       "subsistema": ctx.subsistema,
                       "mva_fronteira": ctx.mva_fronteira,
                       "kv_secundario": ctx.kv_secundario,
                       "raio_km": ctx.raio_km,
                       "confianca": ctx.confianca,
                       "adequacao_amostra": ctx.amostra},
        "fracoes": fr,
        "escala_alimentador": round(esc, 4),
        "parametros": linhas,
        "blocos": spec.BLOCOS,
        "motores_3f": spec.MOTORES_3F,
        "cobertura": cobertura,
        "origens": spec.ORIGENS,
        "fontes": spec.FONTES,
        "geracao_distribuida": _dg_block(ctx),
        "aviso": ("Cartao de parametros com procedencia, nao caso pronto "
                  "para simulacao. Os campos marcados A_CALIBRAR aparecem "
                  "com o valor do conjunto de referencia publicado e nao "
                  "sao afirmacao desta ferramenta. A escolha final e do "
                  "especialista."),
    }


def _dg_block(ctx: Contexto) -> dict:
    """Onde a MMGD entra, e onde nao entra.

    A figura de inicializacao da especificacao mostra `Pdg + jQdg` injetado
    no barramento de carga: o CLM **acomoda** geracao distribuida como
    injecao, e o balanco de reativos da inicializacao ja conta com ela. O que
    o CMPLDW nao tem e **dinamica** de inversor -- nem sub/sobretensao, nem
    resposta de frequencia, nem anti-ilhamento. Isso e outro modelo (a
    familia DER_A), e dize-lo e mais util do que sugerir que o CLM resolve.
    """
    kwp = float(ctx.mmgd_kwp or 0.0)
    return {
        "mmgd_kwp": round(kwp, 1),
        "mmgd_mw": round(kwp / 1000.0, 4),
        "entra_como": "Injecao Pdg + jQdg no barramento de carga, como na "
                      "figura de inicializacao da especificacao.",
        "nao_contemplado": "O CMPLDW nao representa dinamica de inversor. "
                           "Resposta a subtensao e a frequencia e "
                           "anti-ilhamento exigem modelo proprio de recurso "
                           "distribuido (familia DER_A), em paralelo ao CLM.",
        "relevante": kwp > 0,
    }


def wecc_worked_example() -> dict:
    """O exemplo numerico publicado, recalculado por esta implementacao.

    A especificacao demonstra a reparticao dos reativos extras com um caso de
    100 MW (Motor A 40+j9, B 20+j6, C 5+j4, D 15+j1, eletronica 10-j2,
    estatica 10-j2) e publica a tabela de resultado. Reproduzir aquela tabela
    e a unica forma que temos de provar que a implementacao esta correta, e
    nao apenas plausivel -- por isso ela e um teste de regressao, nao uma
    figura.
    """
    comps = [
        theory.Component("Motor A", 40.0, 9.0),
        theory.Component("Motor B", 20.0, 6.0),
        theory.Component("Motor C", 5.0, 4.0),
        theory.Component("Motor D", 15.0, 1.0),
        theory.Component("Eletronica", 10.0, -2.0),
        theory.Component("Estatica", 10.0, -2.0),
    ]
    # Os -36 Mvar sao os do exemplo publicado (figura 11), resultado do
    # balanco de rede da inicializacao -- nao a soma dos reativos dos
    # componentes, que da +16.
    extra = -36.0
    alloc = theory.extra_vars_allocation(comps, extra, mva_base=100.0, v_pu=1.0)
    sobrev = theory.surviving_admittance(
        comps, {"Motor A": 0.20, "Motor B": 0.70, "Motor C": 0.40,
                "Motor D": 1.00, "Eletronica": 0.80, "Estatica": 1.00},
        extra, mva_base=100.0, v_pu=1.0)

    #: Tabela publicada na especificacao, para comparacao lado a lado.
    publicado = {"Motor A": 0.144, "Motor B": 0.072, "Motor C": 0.018,
                 "Motor D": 0.054, "Eletronica": 0.036, "Estatica": 0.036}
    publicado_total = 0.360
    publicado_remanescente = {"Motor A": 0.0288, "Motor B": 0.0504,
                              "Motor C": 0.0072, "Motor D": 0.0540,
                              "Eletronica": 0.0288, "Estatica": 0.0360}
    publicado_remanescente_total = 0.2052

    linhas = []
    for row, srow in zip(alloc["componentes"], sobrev["componentes"]):
        nome = row["componente"]
        calc = row["admitancia_pu"]
        pub = publicado[nome]
        rem_calc = srow["admitancia_remanescente_pu"]
        rem_pub = publicado_remanescente[nome]
        linhas.append({
            "componente": nome, "mw": row["mw"], "mvar": row["mvar"],
            "mva": row["mva"], "peso": row["peso"],
            "extra_vars_mvar": row["extra_vars_mvar"],
            "admitancia_calculada": calc, "admitancia_publicada": pub,
            "desvio": round(abs(calc - pub), 8),
            "fracao_em_servico": srow["fracao_em_servico"],
            "remanescente_calculada": rem_calc,
            "remanescente_publicada": rem_pub,
            "desvio_remanescente": round(abs(rem_calc - rem_pub), 8),
        })

    desvio_max = max([ln["desvio"] for ln in linhas]
                     + [ln["desvio_remanescente"] for ln in linhas])
    return {
        "linhas": linhas,
        "total_calculado": alloc["admitancia_total_pu"],
        "total_publicado": publicado_total,
        "remanescente_calculado": sobrev["admitancia_remanescente_total_pu"],
        "remanescente_publicado": publicado_remanescente_total,
        "extra_vars_mvar": alloc["extra_vars_mvar"],
        "desvio_maximo": round(desvio_max, 8),
        "confere": desvio_max <= 5e-4,
        "fonte": "WECC CLM Specification, secao 'Handling of extra vars due "
                 "to end-use load tripping', paginas 19 e 20.",
    }


def coherence_check() -> dict:
    """A fracao motora deste modulo bate com a que o Mapa Inteligente publica?

    Duas telas que discordam sobre a mesma grandeza destroem a credibilidade
    das duas. Esta verificacao roda como teste e e exposta na API.
    """
    linhas = []
    for classe, comp in CLASS_COMPONENTS.items():
        motora = sum(comp[c] for c in ("Fma", "Fmb", "Fmc", "Fmd"))
        esperada = MOTOR_FRACTION_ESPERADA[classe]
        linhas.append({"classe": classe,
                       "motora_clm": round(motora, 6),
                       "motora_mapa": esperada,
                       "desvio": round(abs(motora - esperada), 8),
                       "soma_total": round(motora + comp["Fel"], 6)})
    return {"linhas": linhas,
            "desvio_maximo": round(max(l["desvio"] for l in linhas), 8),
            "confere": all(l["desvio"] <= 1e-9 for l in linhas)}
