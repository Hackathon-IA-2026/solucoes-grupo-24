# -*- coding: utf-8 -*-
"""Fachada da parametrizacao do CLM.

Mixin proprio, como o do Mapa Inteligente: nao toca em nada que ja funciona.
Reaproveita o registro de subestacoes e a composicao de classe que o Mapa
Inteligente ja produz -- a parametrizacao do CLM e o destino natural daquele
resultado, nao um calculo paralelo.
"""
from __future__ import annotations

import numpy as np

from ..clm import parametrize as P
from ..clm import spec as S
from ..clm import theory as T
from ..substations import mapper

#: Malha de tensao das curvas. Comeca em 0,30 pu porque abaixo disso nenhuma
#: das caracteristicas do modelo tem significado pratico, e termina em 1,10 pu
#: para mostrar o comportamento em sobretensao.
V_GRID = np.round(np.arange(0.30, 1.1001, 0.005), 4)


class ClmMixin:
    """Rotas da parametrizacao do CLM. Estado proprio."""

    def clm_spec_payload(self) -> dict:
        """Estrutura do modelo, registro de parametros e cobertura."""
        blocos = S.by_block()
        return {
            "blocos": S.BLOCOS,
            "motores_3f": S.MOTORES_3F,
            "parametros": {b: [p.as_dict() for p in ps]
                           for b, ps in blocos.items()},
            "total_parametros": len(S.REGISTRO),
            "cobertura": S.counts(),
            "origens": S.ORIGENS,
            "fontes": S.FONTES,
            "topologia": self._clm_topology(),
            "aplicabilidade": {
                "carga_minima_mw": T.APPLY_MIN_MW,
                "tensao_minima_pu": T.APPLY_MIN_V_PU,
                "relacao_pq_minima": T.APPLY_MIN_PQ,
                "piso_barramento_carga_pu": T.V_LOAD_BUS_FLOOR,
                "fator_carregamento_padrao": T.DEFAULT_LOADING_FACTOR,
                "nota": "Criterios citados na especificacao para o caso "
                        "WECC. O CLM nao deve ser aplicado a qualquer barra: "
                        "carga pequena, tensao baixa ou relacao P/Q "
                        "desfavoravel produzem erro de inicializacao.",
            },
            "composicao_por_classe": P.CLASS_COMPONENTS,
            "coerencia_mapa": P.coherence_check(),
        }

    @staticmethod
    def _clm_topology() -> dict:
        """A cadeia entre o barramento do sistema e o uso final.

        E o ponto do modelo que costuma passar em branco: o CLM nao e so uma
        mistura de motores. Metade do efeito dinamico vem da **rede entre** o
        barramento de transmissao e a carga -- a impedancia do transformador e
        do alimentador e o que faz a tensao no uso final cair mais do que a
        tensao medida na subestacao, e e o que leva o compressor a travar.
        """
        return {
            "barramentos": [
                {"id": "sistema", "nome": "Barramento do sistema",
                 "nota": "Onde a carga existe no fluxo de potencia. 230, 115 "
                         "ou 69 kV nos exemplos da especificacao."},
                {"id": "baixa", "nome": "Barramento de baixa",
                 "nota": "Criado na inicializacao; nao existe no fluxo de "
                         "potencia. Recebe o shunt Bss."},
                {"id": "carga", "nome": "Barramento de carga",
                 "nota": "Extremidade do alimentador. Onde ficam os seis "
                         "componentes e onde a geracao distribuida injeta."},
            ],
            "ramos": [
                {"de": "sistema", "para": "baixa", "rotulo": "jXxf, tape 1:T",
                 "nota": "Transformador com comutacao em carga. Zerar Xxf "
                         "omite o transformador, quando ele ja esta no caso."},
                {"de": "baixa", "para": "carga", "rotulo": "Rfdr + jXfdr",
                 "nota": "Equivalente do alimentador. Compensacao reativa "
                         "Bfdr reparte-se entre as duas pontas pela fracao Fb."},
            ],
            "componentes": [
                {"id": "motor_a", "nome": "Motor A", "tipo": "trifasico",
                 "detalhe": "H = 0,3 s, Etrq = 0 -- conjugado constante, "
                            "baixa inercia. Sem desligamento por subtensao no "
                            "conjunto de referencia."},
                {"id": "motor_b", "nome": "Motor B", "tipo": "trifasico",
                 "detalhe": "H = 0,5 s, Etrq = 2 -- conjugado proporcional ao "
                            "quadrado da velocidade."},
                {"id": "motor_c", "nome": "Motor C", "tipo": "trifasico",
                 "detalhe": "H = 1,0 s, Etrq = 2 -- alta inercia."},
                {"id": "motor_d", "nome": "Motor D", "tipo": "monofasico",
                 "detalhe": "Compressor de ar condicionado, modelo por "
                            "desempenho obtido em ensaio. E o componente que "
                            "trava e retem a tensao deprimida."},
                {"id": "eletronica", "nome": "Carga eletronica",
                 "tipo": "estatica com memoria",
                 "detalhe": "Cai em rampa entre Vd1 e Vd2 e so religa na "
                            "fracao Frcel."},
                {"id": "estatica", "nome": "Carga estatica", "tipo": "ZIP",
                 "detalhe": "O que resta depois das cinco fracoes."},
            ],
            "protecoes": ["UVLS", "UFLS", "reles de subtensao por motor",
                          "contatores", "protecao termica"],
        }

    # -- curvas -------------------------------------------------------------

    def clm_curves_payload(self, *, vstall: float = 0.60,
                           rstall: float = 0.124, xstall: float = 0.114,
                           vd1: float = 0.80, vd2: float = 0.70,
                           frcel: float = 0.0, comppf: float = 0.97,
                           p1c: float = 1.0, p1e: float = 2.0,
                           p2c: float = 0.0, p2e: float = 1.0) -> dict:
        """Caracteristicas estaticas do modelo, com os parametros que importam.

        A tela deixa `Vstall`, `Vd1/Vd2`, `Frcel` e a reparticao ZIP
        ajustaveis porque sao os parametros cuja consequencia e visivel e
        cuja escolha e do especialista. Os demais ficariam so enfeitando.
        """
        vs = V_GRID.tolist()

        fp, fq = T.static_pq(V_GRID, 0.0, p1c=p1c, p1e=p1e, p2c=p2c, p2e=p2e)
        down, up = T.electronic_curve(vs, vd1=vd1, vd2=vd2, frcel=frcel)
        md = T.motor_d_curves(vs, po=1.0, comppf=comppf, rstall=rstall,
                              xstall=xstall)

        gstall, _ = T.stall_admittance(rstall, xstall)
        vbrk_loop = T.vstallbrk(1.0, gstall, v_lo=0.40, v_hi=max(vstall, 0.41))
        vbrk_ref = T.vstallbrk_refined(1.0, gstall)

        thetas = np.round(np.arange(0.0, 6.001, 0.02), 3)
        fth = T.thermal_fraction(thetas)

        prev, fcn = 1.0, []
        for v in vs:
            f = T.contactor_fraction(v, previous=prev)
            fcn.append(f)
            prev = f

        omega = np.round(np.arange(0.0, 1.201, 0.005), 4)

        return {
            "tensao": vs,
            "estatica": {"p": [round(float(x), 6) for x in np.atleast_1d(fp)],
                         "q": [round(float(x), 6) for x in np.atleast_1d(fq)],
                         "p1c": p1c, "p1e": p1e, "p2c": p2c, "p2e": p2e,
                         "nota": "Em V = 1 pu e df = 0 o fator e exatamente "
                                 "1, qualquer que seja a reparticao ZIP."},
            "eletronica": {"descida": [round(x, 6) for x in down],
                           "subida": [round(x, 6) for x in up],
                           "vd1": vd1, "vd2": vd2, "frcel": frcel,
                           "nota": "Descida e subida nao coincidem: o modelo "
                                   "guarda a menor tensao ja vista. Com "
                                   "Frcel = 0 nada religa."},
            "motor_d": {
                "regime_p": [round(x, 6) for x in md["regime_p"]],
                "regime_q": [round(x, 6) for x in md["regime_q"]],
                "travado_p": [round(x, 6) for x in md["travado_p"]],
                "travado_q": [round(x, 6) for x in md["travado_q"]],
                "vstallbrk": round(md["vstallbrk"], 6),
                "vstallbrk_laco_publicado": round(vbrk_loop, 6),
                "vstallbrk_bisseccao": round(vbrk_ref, 6),
                "vstall": vstall,
                "gstall": round(md["gstall"], 6),
                "bstall": round(md["bstall"], 6),
                "qo": round(md["qo"], 6),
                "v_quebra": T.V_BREAK_AC,
                "nota": "O cruzamento das duas curvas e o Vstallbrk. Se "
                        "Vstall for menor que ele, o compressor trava antes "
                        "de a curva de regime encontrar a de rotor "
                        "bloqueado -- e por isso a posicao relativa dos dois "
                        "muda o resultado, nao apenas o valor de Vstall."},
            "termica": {"temperatura": [float(x) for x in thetas],
                        "fracao": [round(float(x), 6) for x in fth],
                        "th1t": 1.3, "th2t": 4.3},
            "contator": {"fracao": [round(x, 6) for x in fcn],
                         "vc1off": 0.45, "vc2off": 0.35,
                         "vc1on": 0.50, "vc2on": 0.40},
            "conjugado": {
                "velocidade": [float(x) for x in omega],
                "etrq_0": [round(float(x), 6)
                           for x in np.atleast_1d(T.mech_torque(1.0, omega, 0.0))],
                "etrq_2": [round(float(x), 6)
                           for x in np.atleast_1d(T.mech_torque(1.0, omega, 2.0))],
                "nota": "Etrq = 0 e conjugado constante; Etrq = 2 cresce com "
                        "o quadrado da velocidade. Com H, e o unico campo que "
                        "distingue os motores A, B e C."},
        }

    # -- cartao -------------------------------------------------------------

    def clm_card_payload(self, sub_id: str = "", *, ac_factor: float = 1.0,
                         mix: dict | None = None, fonte: str = "") -> dict:
        """Cartao de parametros: por subestacao real, ou por composicao livre.

        `fonte="bdgd"` troca a composicao do Mapa Inteligente (morfologia de
        ortoimagem) pela da correlacao fronteira T-D (energia faturada real,
        BDGD + SAMP) e a MMGD pelo cadastro da ANEEL.
        """
        if sub_id and fonte == "bdgd":
            fr = self.fronteira_clm_context(sub_id)
            reg = self.registry_ensure().by_id(sub_id)
            ctx = P.Contexto(
                nome=fr["name"], uf=fr["uf"], subsistema=fr["subsystem"],
                mva_fronteira=fr["frontier_mva"],
                kv_secundario=fr["secondary_kv"],
                raio_km=reg.radius_km if reg is not None else None,
                mix=fr["weights"], mmgd_kwp=fr["gd_kw"],
                confianca="parcela medida %.0f%%" % (
                    100 * (fr["measured_share"] or 0.0)),
                amostra="%d SEDs associadas" % fr["n_sed"],
            )
            card = P.build_card(ctx, ac_factor)
            card["fonte_composicao"] = ("Fronteira T-D: BDGD + SAMP + cadastro "
                                        "de MMGD (ANEEL)")
            card["insumo_mapa"] = fr["clm"]
            p_mw = float(fr["frontier_mva"] or 0.0) * 0.9
            card["aplicabilidade"] = T.applicability(
                p_mw, 1.0, q_mvar=max(p_mw / 3.0, 1e-6))
        elif sub_id:
            detail = self.substation_detail_payload(sub_id)
            sub = detail["substation"]
            lc = detail["load_class"]
            ctx = P.Contexto(
                nome=sub.get("name", "-"), uf=sub.get("uf", "-"),
                subsistema=sub.get("subsystem", "-"),
                mva_fronteira=sub.get("frontier_mva"),
                kv_secundario=sub.get("secondary_kv_min"),
                raio_km=sub.get("radius_km"),
                mix=lc.get("weights") or {},
                mmgd_kwp=(detail.get("mmgd") or {}).get("kwp_total"),
                confianca=lc.get("confidence", "-"),
                amostra=(detail.get("mmgd") or {}).get("sample_adequacy", "-"),
            )
            card = P.build_card(ctx, ac_factor)
            card["fonte_composicao"] = "Mapa Inteligente, subestacao real"
            card["insumo_mapa"] = detail.get("clm")
            p_mw = float(sub.get("frontier_mva") or 0.0) * 0.9
            card["aplicabilidade"] = T.applicability(
                p_mw, 1.0, q_mvar=max(p_mw / 3.0, 1e-6))
        else:
            m = mix or {"residencial": 0.55, "comercial": 0.25,
                        "industrial": 0.12, "rural": 0.08}
            ctx = P.Contexto(nome="Composicao livre", mix=m)
            card = P.build_card(ctx, ac_factor)
            card["fonte_composicao"] = "Composicao informada na tela"
            card["aplicabilidade"] = T.applicability(50.0, 1.0, q_mvar=20.0)
        card["exemplo_wecc"] = P.wecc_worked_example()
        card["cartao_texto"] = _card_text(card)
        return card

    def clm_validation_payload(self) -> dict:
        """O que prova que a implementacao esta correta, e nao apenas plausivel."""
        gstall, bstall = T.stall_admittance(0.124, 0.114)
        vbrk_loop = T.vstallbrk(1.0, gstall)
        vbrk_ref = T.vstallbrk_refined(1.0, gstall)
        fp1, fq1 = T.static_pq(1.0)
        fr, est = T.static_remainder(0.6, 0.3, 0.2, 0.1, 0.1)

        return {
            "exemplo_wecc": P.wecc_worked_example(),
            "coerencia_mapa": P.coherence_check(),
            "conferencias": [
                {"nome": "Carga estatica em 1 pu",
                 "esperado": "fator 1,000000 em P e em Q",
                 "obtido": f"P = {float(fp1):.6f} · Q = {float(fq1):.6f}",
                 "ok": abs(float(fp1) - 1.0) < 1e-12
                       and abs(float(fq1) - 1.0) < 1e-12,
                 "porque": "Se a carga estatica nao devolvesse exatamente 1 "
                           "em 1 pu, o CLM deslocaria o ponto de operacao na "
                           "inicializacao."},
                {"nome": "Vstallbrk por dois metodos",
                 "esperado": "concordancia dentro de um passo de 0,01 pu",
                 "obtido": f"laco publicado {vbrk_loop:.4f} · bisseccao "
                           f"{vbrk_ref:.6f}",
                 "ok": abs(vbrk_loop - vbrk_ref) <= 0.01 + 1e-9,
                 "porque": "O laco de passo fixo e o da especificacao; a "
                           "bisseccao e conferencia independente."},
                {"nome": "Normalizacao das fracoes",
                 "esperado": "soma 1,000000 e estatica nula quando as "
                             "fracoes excedem 1",
                 "obtido": f"soma {sum(fr):.6f} · estatica {est:.6f}",
                 "ok": abs(sum(fr) - 1.0) < 1e-12 and est == 0.0,
                 "porque": "Regra explicita da especificacao para fracoes "
                           "que somam mais de 1."},
                {"nome": "Admitancia de rotor bloqueado",
                 "esperado": "inversao de Rstall + jXstall",
                 "obtido": f"Gstall = {gstall:.4f} · Bstall = {bstall:.4f}",
                 "ok": abs(gstall - 0.124 / (0.124 ** 2 + 0.114 ** 2)) < 1e-9,
                 "porque": "A especificacao usa Gstall e Bstall sem "
                           "escreve-los em funcao de Rstall e Xstall."},
            ],
            "limites": [
                "Nada aqui simula o CLM no tempo. Sao as relacoes algebricas "
                "e a logica de protecao, que e o que a parametrizacao expoe.",
                "A composicao por classe e premissa versionada, nao medicao "
                "de uso final. A calibracao pede o guia de composicao de "
                "carga da NERC e a Pesquisa de Posse e Habitos de Consumo.",
                "Os parametros eletricos de maquina e os de ensaio do "
                "compressor aparecem com o valor do conjunto de referencia "
                "publicado e rotulo A_CALIBRAR. Nao sao afirmacao desta "
                "ferramenta.",
                "A penetracao de ar condicionado no Brasil nao e a do "
                "sudoeste norte-americano de onde vem o modelo do motor D. A "
                "tela expoe a sensibilidade em vez de fixar um numero.",
            ],
        }


def _card_text(card: dict) -> str:
    """Cartao em texto, agrupado por bloco, com a procedencia em cada linha.

    Formato neutro de proposito: os campos do CMPLDW sao os mesmos em PSS/E,
    PSLF, PowerWorld, DSATools e ORGANON, e emitir a sintaxe de uma
    ferramenta especifica daria a impressao de um caso pronto para rodar --
    que nao e o que isto e.
    """
    sub = card.get("subestacao", {})
    linhas = [
        "! Modelo de Carga Composta (CMPLDW) - parametrizacao sugerida",
        "! O.R.A.C.U.L.O. / equipe LINKFY",
        "! Subestacao: %s (%s, %s)" % (sub.get("nome", "-"),
                                       sub.get("uf", "-"),
                                       sub.get("subsistema", "-")),
        "! Composicao: %s" % card.get("fonte_composicao", "-"),
        "!",
        "! ATENCAO: cartao de parametros com procedencia, nao caso pronto",
        "! para simulacao. Campos A_CALIBRAR trazem o valor do conjunto de",
        "! referencia publicado (arXiv:1708.00939) e nao sao afirmacao",
        "! desta ferramenta.",
        "!",
    ]
    blocos = card.get("blocos", {})
    atual = None
    for p in card.get("parametros", []):
        if p["bloco"] != atual:
            atual = p["bloco"]
            linhas.append("! --- %s" % blocos.get(atual, atual))
        valor = p["valor"]
        txt = ("%.6g" % valor) if isinstance(valor, (int, float)) else str(valor)
        linhas.append("  %-8s %12s   ! %s" % (p["nome"], txt, p["origem"]))
    return "\n".join(linhas)
