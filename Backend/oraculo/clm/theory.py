# -*- coding: utf-8 -*-
"""Equacoes do CMPLDW, escritas como no documento normativo.

Fonte unica: *WECC Composite Load Model Specification*, Modeling and
Validation Subcommittee, abril de 2021 (primeira versao aprovada em
27/01/2015). As secoes citadas abaixo sao as do proprio documento.

Por que reimplementar as equacoes em vez de so tabelar parametros: a pagina
de parametrizacao precisa **mostrar a consequencia** de cada parametro. Uma
tabela de numeros nao revela que mover `Vstall` de 0,60 para 0,55 pu desloca
o ponto de travamento do compressor; a curva revela. E, sobretudo, permite
que o teste compare a implementacao com o exemplo numerico publicado na
propria especificacao (secao "Handling of extra vars", pagina 19), o que
transforma "implementei o CLM" em afirmacao verificavel.

Nada aqui simula o CLM no tempo. Sao as relacoes algebricas estaticas e a
logica de protecao, que e o que a parametrizacao precisa expor.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# ---------------------------------------------------------------------------
# Constantes que a especificacao fixa no texto (nao sao escolha nossa).
# ---------------------------------------------------------------------------

#: Tensao de quebra das equacoes do compressor monofasico (secao
#: "Single-phase Air Conditioner Performance-based Model").
V_BREAK_AC = 0.86

#: Expoentes das equacoes de P e Q do compressor abaixo de V_BREAK_AC.
AC_P_GAIN, AC_P_EXP = 12.0, 3.2
AC_Q_GAIN, AC_Q_EXP = 11.0, 2.5

#: Termo quadratico de Q acima de V_BREAK_AC e sensibilidades de frequencia.
AC_Q_CURV = 6.0
AC_P_DFREQ = 1.0
AC_Q_DFREQ = -3.3

#: Piso de tensao no barramento de carga que as ferramentas garantem
#: ajustando Rfdr/Xfdr na inicializacao (secao "Distribution Feeder
#: Equivalent").
V_LOAD_BUS_FLOOR = 0.95

#: Criterios de aplicabilidade citados para o caso WECC (secao
#: "Introduction"): carga > 5 MW, tensao > 0,98 pu, relacao P/Q > 1,61.
APPLY_MIN_MW = 5.0
APPLY_MIN_V_PU = 0.98
APPLY_MIN_PQ = 1.61

#: Fator de carregamento adotado quando a base MVA e informada como zero.
DEFAULT_LOADING_FACTOR = 0.8

#: Em CMLDXXU2 a reatancia de dispersao e fixada em 0,80 x Lpp (nota da
#: secao "Three-phase Motor Model").
LL_OVER_LPP = 0.80


# ---------------------------------------------------------------------------
# Carga estatica
# ---------------------------------------------------------------------------

def static_pq(v, dfreq=0.0, p1c=1.0, p1e=2.0, p2c=0.0, p2e=1.0, pfrq=1.0,
              q1c=1.0, q1e=2.0, q2c=0.0, q2e=1.0, qfrq=-1.0):
    """Multiplicadores de P e Q da carga estatica.

        P = Po (P1c V^P1e + P2c V^P2e + P3) (1 + Pfrq df),  P3 = 1 - P1c - P2c
        Q = Qo (Q1c V^Q1e + Q2c V^Q2e + Q3) (1 + Qfrq df),  Q3 = 1 - Q1c - Q2c

    Retorna os fatores relativos a Po e Qo, de modo que v=1 e df=0 devolve
    exatamente (1, 1) qualquer que seja a reparticao ZIP -- propriedade que o
    teste verifica, porque e ela que garante que a carga estatica nao desloca
    o ponto de operacao inicial.
    """
    v = np.asarray(v, dtype=float)
    p3 = 1.0 - p1c - p2c
    q3 = 1.0 - q1c - q2c
    fp = (p1c * v ** p1e + p2c * v ** p2e + p3) * (1.0 + pfrq * dfreq)
    fq = (q1c * v ** q1e + q2c * v ** q2e + q3) * (1.0 + qfrq * dfreq)
    return fp, fq


# ---------------------------------------------------------------------------
# Carga eletronica
# ---------------------------------------------------------------------------

def electronic_fraction(v, vmin, vd1=0.80, vd2=0.70, frcel=0.0):
    """Fracao `Fv1` da carga eletronica em servico, e o novo `vmin`.

    Transcricao do pseudocodigo da secao "Electronic Load Model". `vmin`
    rastreia a menor tensao ja vista, limitada inferiormente a `vd2`; e ele
    que da memoria ao modelo -- abaixo de Vd1 a carga se desliga em rampa e
    so retorna na fracao `frcel`, de modo que o estado depende do historico e
    nao apenas da tensao instantanea.

    O `Vmin` desta funcao nao e o `Vmin` do transformador: a especificacao
    alerta para essa colisao de nomes, e a mantemos porque o nome e o do
    documento.
    """
    if v < vmin:
        vmin = v
    if vmin < vd2:
        vmin = vd2

    if v < vd2:
        fv1 = 0.0
    elif v < vd1:
        if v <= vmin:
            fv1 = (v - vd2) / (vd1 - vd2)
        else:
            fv1 = ((vmin - vd2) + frcel * (v - vmin)) / (vd1 - vd2)
    else:
        if vmin >= vd1:
            fv1 = 1.0
        else:
            fv1 = ((vmin - vd2) + frcel * (vd1 - vmin)) / (vd1 - vd2)
    return float(min(max(fv1, 0.0), 1.0)), float(vmin)


def electronic_curve(vs, vd1=0.80, vd2=0.70, frcel=0.0):
    """`Fv1` ao longo de uma rampa descendente e da recuperacao seguinte.

    `vs` e a malha de tensao em ordem **crescente**, e as duas series saem
    alinhadas a ela. A varredura, porem, comeca no topo: o modelo tem
    memoria, e percorre-lo na ordem errada produziria uma curva sem sentido
    fisico -- foi o que aconteceu na primeira versao deste codigo.

    Duas series, porque a curva de descida nao e a de subida. Com
    `Frcel = 0` a recuperacao e identicamente nula depois de um afundamento
    abaixo de `Vd2`: a carga eletronica desligada **nao volta sozinha**. E
    esse laco, e nao o valor de `Vd1`, o que costuma surpreender em estudo.
    """
    vs = [float(x) for x in vs]
    n = len(vs)
    if not n:
        return [], []

    down = [0.0] * n
    vmin = max(vs[-1], 1.0)          # parte do topo, sem memoria de afundamento
    for i in range(n - 1, -1, -1):   # descendo
        down[i], vmin = electronic_fraction(vs[i], vmin, vd1, vd2, frcel)

    up = [0.0] * n
    for i in range(n):               # subindo de volta, com a memoria acumulada
        up[i], vmin = electronic_fraction(vs[i], vmin, vd1, vd2, frcel)
    return down, up


# ---------------------------------------------------------------------------
# Compressor monofasico (motor D) -- modelo por desempenho
# ---------------------------------------------------------------------------

def stall_admittance(rstall, xstall):
    """Condutancia e susceptancia do compressor travado.

        Y = 1/(Rstall + j Xstall)  ->  G = R/(R^2+X^2),  B = X/(R^2+X^2)

    A especificacao usa Gstall e Bstall nas equacoes de estado travado sem
    escreve-las em funcao de Rstall/Xstall; esta e a inversao direta.
    """
    den = rstall * rstall + xstall * xstall
    if den <= 0.0:
        return 0.0, 0.0
    return rstall / den, xstall / den


def qo_init(po, comppf):
    """Q inicial do compressor.

        Q'o = Po tan(acos(CompPF)) - 6 (1 - 0.86)^2

    O segundo termo cancela a curvatura que a equacao de Q acima de 0,86 pu
    introduz em V = 1, para que o modelo parta do fator de potencia pedido.
    """
    comppf = min(max(float(comppf), -1.0), 1.0)
    return po * math.tan(math.acos(comppf)) - AC_Q_CURV * (1.0 - V_BREAK_AC) ** 2


def vstallbrk(po, gstall, v_lo=0.40, v_hi=0.60, step=0.01):
    """Ponto onde a curva de estado travado cruza a de regime II.

    Transcricao literal do laco publicado na secao do compressor
    monofasico::

        for (V = 0.4; V < Vstall; V += 0.01)
            pst    = Gstall * V^2
            p_comp = Po + 12 * (0.86 - V)^3.2
            if (p_comp <= pst) { V'stall = V; break }

    A especificacao declara a precisao de 0,01 pu e observa que fornecedores
    usam outros metodos (o PowerWorld Simulator resolve a 0,0001 pu).
    Mantemos o laco publicado para poder compara-lo com `vstallbrk_refined`.
    """
    v = v_lo
    while v < v_hi:
        pst = gstall * v * v
        p_comp = po + AC_P_GAIN * (V_BREAK_AC - v) ** AC_P_EXP
        if p_comp <= pst:
            return float(v)
        v += step
    return float(v_hi)


def vstallbrk_refined(po, gstall, v_lo=0.30, v_hi=0.86, tol=1e-6):
    """O mesmo cruzamento, por bisseccao.

    `f(V) = Gstall V^2 - [Po + 12 (0.86 - V)^3.2]` e crescente no intervalo
    de interesse, porque o primeiro termo cresce e o segundo decresce com V.
    Vale como conferencia independente do laco de passo fixo: os dois devem
    concordar dentro de um passo de 0,01 pu.
    """
    def f(v):
        return gstall * v * v - (po + AC_P_GAIN * (V_BREAK_AC - v) ** AC_P_EXP)

    lo, hi = float(v_lo), float(v_hi)
    if f(lo) > 0.0:
        return lo
    if f(hi) < 0.0:
        return hi
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if f(mid) < 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def motor_d_pq(v, po=1.0, qo=None, comppf=0.97, rstall=0.124, xstall=0.114,
               dfreq=0.0, vstall_prime=None, stalled=False):
    """P e Q do compressor monofasico, nos tres regimes da especificacao.

        V > 0.86            P = Po (1 + df)
                            Q = [Q'o + 6 (V - 0.86)^2] (1 - 3.3 df)

        V'stall < V < 0.86  P = [Po + 12 (0.86 - V)^3.2] (1 + df)
                            Q = [Q'o + 11 (0.86 - V)^2.5] (1 - 3.3 df)

        V < V'stall         P =  Gstall V^2
                            Q = -Bstall V^2

    `df` e `f - 1`, negativo em subfrequencia, como o documento observa.

    O sinal de Q no estado travado e o da especificacao: um compressor
    travado e um rotor bloqueado, quase uma reatancia pura -- absorve muito
    reativo. O sinal negativo aparece porque a equacao devolve Q na convencao
    de injecao.
    """
    gstall, bstall = stall_admittance(rstall, xstall)
    if qo is None:
        qo = qo_init(po, comppf)
    if vstall_prime is None:
        vstall_prime = vstallbrk_refined(po, gstall)

    v = float(v)
    if stalled or v < vstall_prime:
        return gstall * v * v, -bstall * v * v
    if v > V_BREAK_AC:
        p = po * (1.0 + AC_P_DFREQ * dfreq)
        q = (qo + AC_Q_CURV * (v - V_BREAK_AC) ** 2) * (1.0 + AC_Q_DFREQ * dfreq)
        return p, q
    p = (po + AC_P_GAIN * (V_BREAK_AC - v) ** AC_P_EXP) * (1.0 + AC_P_DFREQ * dfreq)
    q = (qo + AC_Q_GAIN * (V_BREAK_AC - v) ** AC_Q_EXP) * (1.0 + AC_Q_DFREQ * dfreq)
    return p, q


def motor_d_curves(vs, po=1.0, comppf=0.97, rstall=0.124, xstall=0.114):
    """As tres caracteristicas do motor D e o ponto `Vstallbrk`.

    Devolve regime (I e II juntos, que e a curva de operacao) e estado
    travado como series separadas ao longo de todo o eixo, porque e a
    sobreposicao das duas que mostra onde uma cruza a outra -- a figura 6 da
    especificacao.
    """
    gstall, bstall = stall_admittance(rstall, xstall)
    qo = qo_init(po, comppf)
    vbrk = vstallbrk_refined(po, gstall)

    run_p, run_q, stall_p, stall_q = [], [], [], []
    for v in vs:
        v = float(v)
        if v > V_BREAK_AC:
            run_p.append(po)
            run_q.append(qo + AC_Q_CURV * (v - V_BREAK_AC) ** 2)
        else:
            run_p.append(po + AC_P_GAIN * (V_BREAK_AC - v) ** AC_P_EXP)
            run_q.append(qo + AC_Q_GAIN * (V_BREAK_AC - v) ** AC_Q_EXP)
        stall_p.append(gstall * v * v)
        stall_q.append(-bstall * v * v)
    return {"regime_p": run_p, "regime_q": run_q,
            "travado_p": stall_p, "travado_q": stall_q,
            "vstallbrk": vbrk, "gstall": gstall, "bstall": bstall, "qo": qo}


# ---------------------------------------------------------------------------
# Protecoes agregadas
# ---------------------------------------------------------------------------

def thermal_fraction(theta, th1t=1.3, th2t=4.3):
    """Fracao nao desligada pela protecao termica (figura 10).

    Rampa unitaria ate `Th1t` (temperatura pu), decrescente linearmente ate
    zero em `Th2t`. A temperatura vem de `I^2 Rstall` filtrado por `1/(Tth s
    + 1)` -- a dinamica fica fora daqui; o que a parametrizacao precisa e a
    caracteristica estatica.
    """
    theta = np.asarray(theta, dtype=float)
    if th2t <= th1t:
        return np.where(theta >= th1t, 0.0, 1.0)
    return np.clip((th2t - theta) / (th2t - th1t), 0.0, 1.0)


def contactor_fraction(v, vc1off=0.45, vc2off=0.35, vc1on=0.50, vc2on=0.40,
                       previous=1.0):
    """Fracao nao desligada pelos contatores (figura 9), com histerese.

    Desliga na descida entre `Vc1off` e `Vc2off`; religa na subida entre
    `Vc2on` e `Vc1on`. Os dois trechos sao distintos, e por isso o estado
    anterior entra como argumento: entre 0,40 e 0,50 pu a fracao depende de
    como se chegou ali. A laco de histerese e o que impede religamento
    instantaneo e oscilacao numerica na fronteira.
    """
    v = float(v)
    if v >= vc1on:
        return 1.0
    if v <= vc2off:
        return 0.0
    off = 0.0 if v <= vc2off else min((v - vc2off) / max(vc1off - vc2off, 1e-9), 1.0)
    on = 0.0 if v <= vc2on else min((v - vc2on) / max(vc1on - vc2on, 1e-9), 1.0)
    # Na descida segue o ramo inferior; na subida, o superior.
    return float(min(max(on if previous >= off else off, 0.0), 1.0))


def mech_torque(tmo, omega, etrq):
    """Conjugado mecanico do motor trifasico: `Tm = Tmo w^Etrq`.

    `Etrq = 0` e conjugado constante (compressor); `Etrq = 2` e conjugado
    proporcional ao quadrado da velocidade (ventilador, bomba). E este
    expoente, com a inercia H, que diferencia os tres motores trifasicos do
    modelo -- nao ha outro campo que os distinga.
    """
    return float(tmo) * np.power(np.asarray(omega, dtype=float), float(etrq))


# ---------------------------------------------------------------------------
# Fracoes e inicializacao de reativo
# ---------------------------------------------------------------------------

def static_remainder(fma, fmb, fmc, fmd, fel):
    """Fracao estatica e fracoes normalizadas, pela regra da especificacao.

    "If these fractions sum to less than 1, the remainder is represented by
    the static load model. If these fractions sum to more than 1, the static
    load fraction is set to zero and the other fractions are normalized to
    sum to 1."
    """
    fr = [float(fma), float(fmb), float(fmc), float(fmd), float(fel)]
    total = sum(fr)
    if total > 1.0:
        fr = [x / total for x in fr]
        return tuple(fr), 0.0
    return tuple(fr), 1.0 - total


@dataclass(frozen=True)
class Component:
    """Um dos seis componentes do barramento de carga, na inicializacao."""
    nome: str
    mw: float
    mvar: float

    @property
    def mva(self) -> float:
        return math.hypot(self.mw, self.mvar)


def extra_vars_allocation(components, extra_mvar, mva_base=100.0, v_pu=1.0):
    """Reparticao dos reativos extras entre os componentes.

    Na inicializacao, o CLM acrescenta reativo shunt ao alimentador para que
    o Q do modelo case com o Q do fluxo de potencia no barramento do sistema.
    Esse reativo nao fica constante: quando um componente e desligado pela
    protecao, a parcela dele sai junto, proporcionalmente ao MW. A
    especificacao (secao "Handling of extra vars due to end-use load
    tripping") demonstra a conta com um exemplo de 100 MW, e e contra a
    tabela publicada ali que o teste compara.

    `extra_mvar` e argumento, e nao calculado aqui, por um motivo de fundo:
    o montante vem do balanco de rede da inicializacao -- transformador,
    alimentador, shunts e a propria geracao distribuida no barramento de
    carga. No exemplo publicado sao -36 Mvar, enquanto a soma dos reativos
    dos componentes e apenas +16: os dois numeros nao sao o mesmo, e derivar
    um do outro seria erro. O que este modulo faz e a **reparticao**, que e a
    parte que a especificacao define.

    O peso e `MW do componente / MW total`, nao a participacao em MVA -- e o
    que o exemplo publicado usa. O MVA total da tabela publicada tambem e a
    soma aritmetica dos MVA, nao a composicao vetorial.
    """
    comps = list(components)
    total_mw = sum(c.mw for c in comps)
    total_mvar = sum(c.mvar for c in comps)
    total_mva = sum(c.mva for c in comps)
    extra = float(extra_mvar)

    rows, soma_b = [], 0.0
    for c in comps:
        peso = (c.mw / total_mw) if total_mw else 0.0
        aloc = extra * peso
        b_pu = abs(aloc) / mva_base / (v_pu * v_pu)
        soma_b += b_pu
        rows.append({"componente": c.nome, "mw": round(c.mw, 4),
                     "mvar": round(c.mvar, 4), "mva": round(c.mva, 4),
                     "peso": round(peso, 6),
                     "extra_vars_mvar": round(aloc, 4),
                     "admitancia_pu": round(b_pu, 6)})
    return {"componentes": rows,
            "total_mw": round(total_mw, 4),
            "total_mvar": round(total_mvar, 4),
            "total_mva": round(total_mva, 4),
            "extra_vars_mvar": round(extra, 4),
            "admitancia_total_pu": round(soma_b, 6),
            "mva_base": mva_base}


def surviving_admittance(components, survival, extra_mvar, mva_base=100.0,
                         v_pu=1.0):
    """Admitancia extra remanescente apos desligamentos parciais.

    `survival` traz, por componente, a fracao ainda em servico (0,70 = 30%
    desligado). A carga estatica nunca desliga por protecao de uso final, e
    por isso entra sempre com 1,00 -- como o exemplo da especificacao
    explicita.
    """
    base = extra_vars_allocation(components, extra_mvar, mva_base, v_pu)
    rows, soma = [], 0.0
    for row in base["componentes"]:
        frac = float(survival.get(row["componente"], 1.0))
        nova = row["admitancia_pu"] * frac
        soma += nova
        rows.append({**row, "fracao_em_servico": round(frac, 4),
                     "admitancia_remanescente_pu": round(nova, 6)})
    return {"componentes": rows, "admitancia_remanescente_total_pu": round(soma, 6),
            "admitancia_inicial_total_pu": base["admitancia_total_pu"]}


# ---------------------------------------------------------------------------
# Aplicabilidade
# ---------------------------------------------------------------------------

def applicability(p_mw, v_pu, q_mvar=None, pq_ratio=None):
    """Verifica os criterios de aplicabilidade citados na especificacao.

    O CLM nao deve ser aplicado a qualquer barra: carga pequena, tensao baixa
    ou relacao P/Q desfavoravel produzem erro de inicializacao. A propria
    especificacao propoe, para o caso WECC, carga > 5 MW, tensao > 0,98 pu e
    P/Q > 1,61. Reportamos cada criterio em separado, porque o que interessa
    ao usuario e *qual* deles reprovou.
    """
    if pq_ratio is None:
        pq_ratio = (p_mw / q_mvar) if q_mvar else float("inf")
    testes = [
        {"criterio": "carga minima", "limite": f"> {APPLY_MIN_MW:g} MW",
         "valor": round(float(p_mw), 3), "ok": float(p_mw) > APPLY_MIN_MW},
        {"criterio": "tensao minima", "limite": f"> {APPLY_MIN_V_PU:g} pu",
         "valor": round(float(v_pu), 4), "ok": float(v_pu) > APPLY_MIN_V_PU},
        {"criterio": "relacao P/Q", "limite": f"> {APPLY_MIN_PQ:g}",
         "valor": (round(float(pq_ratio), 3) if math.isfinite(pq_ratio) else None),
         "ok": float(pq_ratio) > APPLY_MIN_PQ},
    ]
    return {"aplicavel": all(t["ok"] for t in testes), "testes": testes,
            "fonte": "WECC CLM Specification, secao Introduction"}


def mva_base_from_spec(xxx, load_mw):
    """Base MVA a partir do campo `MVA` da especificacao.

    Tres casos, como no documento: positivo e a propria base; negativo e
    fator de carregamento (base = ``MW / |xxx|``); zero usa o fator padrao
    0,8.
    """
    xxx = float(xxx)
    if xxx > 0:
        return xxx
    lf = abs(xxx) if xxx < 0 else DEFAULT_LOADING_FACTOR
    return float(load_mw) / lf if lf else float(load_mw)
