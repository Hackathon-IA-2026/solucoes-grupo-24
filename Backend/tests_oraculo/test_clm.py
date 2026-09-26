# -*- coding: utf-8 -*-
"""Testes da parametrizacao do Modelo de Carga Composta.

O teste que importa mais neste arquivo e
`test_exemplo_publicado_da_especificacao`: a especificacao do WECC traz um
exemplo numerico resolvido, e reproduzir aquela tabela e a unica forma de
mostrar que a implementacao esta correta, e nao apenas plausivel. Os demais
verificam propriedades que as equacoes tem de ter.
"""
from __future__ import annotations

import math

import pytest

from oraculo.api.service import SERVICE
from oraculo.clm import parametrize as P
from oraculo.clm import spec as S
from oraculo.clm import theory as T


# ---------------------------------------------------------------------------
# Confronto com a fonte
# ---------------------------------------------------------------------------

def test_exemplo_publicado_da_especificacao():
    """Reproduz a tabela das paginas 19 e 20 da especificacao do WECC.

    Doze comparacoes: a admitancia extra alocada a cada um dos seis
    componentes na inicializacao e a remanescente apos desligamento parcial.
    Tolerancia igual ao arredondamento da tabela publicada.
    """
    r = P.wecc_worked_example()
    assert r["confere"], r
    assert r["desvio_maximo"] <= 5e-4
    assert r["total_calculado"] == pytest.approx(0.360, abs=5e-4)
    assert r["remanescente_calculado"] == pytest.approx(0.2052, abs=5e-4)
    assert len(r["linhas"]) == 6


def test_reativos_extras_nao_sao_a_soma_dos_componentes():
    """O montante vem do balanco de rede, nao da soma dos reativos.

    No exemplo publicado a soma dos reativos dos componentes e +16 Mvar
    enquanto os reativos extras sao -36. Derivar um do outro seria erro, e
    este teste existe para que ninguem o reintroduza por simplificacao.
    """
    r = P.wecc_worked_example()
    assert r["extra_vars_mvar"] == pytest.approx(-36.0)
    comps = [T.Component("a", 40, 9), T.Component("b", 20, 6),
             T.Component("c", 5, 4), T.Component("d", 15, 1),
             T.Component("e", 10, -2), T.Component("f", 10, -2)]
    assert sum(c.mvar for c in comps) == pytest.approx(16.0)


def test_peso_da_alocacao_e_por_mw():
    """A especificacao pondera por MW, nao por MVA."""
    comps = [T.Component("x", 40.0, 30.0), T.Component("y", 60.0, 0.0)]
    r = T.extra_vars_allocation(comps, -10.0, mva_base=100.0)
    pesos = {c["componente"]: c["peso"] for c in r["componentes"]}
    assert pesos["x"] == pytest.approx(0.40)
    assert pesos["y"] == pytest.approx(0.60)


# ---------------------------------------------------------------------------
# Carga estatica
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("p1c,p2c", [(1.0, 0.0), (0.0, 1.0), (0.3, 0.3),
                                     (0.0, 0.0)])
def test_estatica_devolve_um_em_tensao_nominal(p1c, p2c):
    """Qualquer reparticao ZIP tem de dar fator 1 em 1 pu.

    Se nao desse, o CLM deslocaria o ponto de operacao na inicializacao --
    o modelo passaria a mentir sobre a propria carga inicial.
    """
    fp, fq = T.static_pq(1.0, 0.0, p1c=p1c, p2c=p2c, q1c=p1c, q2c=p2c)
    assert float(fp) == pytest.approx(1.0, abs=1e-12)
    assert float(fq) == pytest.approx(1.0, abs=1e-12)


def test_estatica_impedancia_constante_cai_com_o_quadrado():
    fp, _ = T.static_pq(0.5, 0.0, p1c=1.0, p1e=2.0, p2c=0.0)
    assert float(fp) == pytest.approx(0.25)


def test_estatica_sensibilidade_de_frequencia():
    fp, fq = T.static_pq(1.0, -0.01, pfrq=1.0, qfrq=-1.0)
    assert float(fp) == pytest.approx(0.99)
    assert float(fq) == pytest.approx(1.01)


# ---------------------------------------------------------------------------
# Carga eletronica
# ---------------------------------------------------------------------------

def test_eletronica_limites():
    f, _ = T.electronic_fraction(1.0, 1.0)
    assert f == 1.0
    f, _ = T.electronic_fraction(0.60, 1.0)
    assert f == 0.0


def test_eletronica_tem_memoria():
    """Sem religamento, a carga nao volta depois do afundamento.

    E a propriedade que explica por que carga eletronica desligada continua
    desligada: `vmin` guarda a menor tensao ja vista.
    """
    vmin = 1.0
    _, vmin = T.electronic_fraction(0.75, vmin, frcel=0.0)
    f_volta, _ = T.electronic_fraction(1.0, vmin, frcel=0.0)
    assert f_volta < 1.0
    assert f_volta == pytest.approx(0.5, abs=1e-9)


def test_eletronica_religa_na_fracao_frcel():
    vmin = 1.0
    _, vmin = T.electronic_fraction(0.75, vmin, frcel=1.0)
    f, _ = T.electronic_fraction(1.0, vmin, frcel=1.0)
    assert f == pytest.approx(1.0, abs=1e-9)


def test_eletronica_curva_descida_difere_da_subida():
    """A malha entra crescente; a varredura comeca no topo.

    Com Frcel = 0 e um afundamento abaixo de Vd2, a recuperacao e
    identicamente nula: a carga desligada nao volta.
    """
    vs = [0.60, 0.72, 0.75, 0.80, 0.90, 1.00]
    down, up = T.electronic_curve(vs, vd1=0.80, vd2=0.70, frcel=0.0)
    assert down[-1] == 1.0          # em 1 pu, tudo em servico
    assert down[0] == 0.0           # abaixo de Vd2, nada
    assert 0.0 < down[2] < 1.0      # rampa entre Vd2 e Vd1
    assert all(u == 0.0 for u in up)
    assert up != down


def test_eletronica_curva_recupera_com_frcel_unitario():
    vs = [0.60, 0.72, 0.80, 1.00]
    _, up = T.electronic_curve(vs, vd1=0.80, vd2=0.70, frcel=1.0)
    assert up[-1] == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Compressor monofasico
# ---------------------------------------------------------------------------

def test_admitancia_de_rotor_bloqueado():
    g, b = T.stall_admittance(0.124, 0.114)
    den = 0.124 ** 2 + 0.114 ** 2
    assert g == pytest.approx(0.124 / den)
    assert b == pytest.approx(0.114 / den)


def test_admitancia_degenerada_nao_divide_por_zero():
    assert T.stall_admittance(0.0, 0.0) == (0.0, 0.0)


def test_vstallbrk_dois_metodos_concordam():
    """O laco publicado tem passo de 0,01 pu; a bisseccao e independente."""
    g, _ = T.stall_admittance(0.124, 0.114)
    laco = T.vstallbrk(1.0, g)
    bis = T.vstallbrk_refined(1.0, g)
    assert abs(laco - bis) <= 0.01 + 1e-9


def test_vstallbrk_e_o_cruzamento_das_curvas():
    """No ponto encontrado, as duas caracteristicas tem o mesmo P."""
    g, _ = T.stall_admittance(0.124, 0.114)
    v = T.vstallbrk_refined(1.0, g)
    p_travado = g * v * v
    p_regime = 1.0 + T.AC_P_GAIN * (T.V_BREAK_AC - v) ** T.AC_P_EXP
    assert p_travado == pytest.approx(p_regime, abs=1e-4)


def test_motor_d_continuo_na_tensao_de_quebra():
    """As equacoes acima e abaixo de 0,86 pu tem de se encontrar ali.

    Uma descontinuidade em 0,86 pu apareceria como degrau de potencia no
    meio da faixa normal de operacao.
    """
    kw = dict(po=1.0, comppf=0.97, rstall=0.124, xstall=0.114)
    p_ac, q_ac = T.motor_d_pq(T.V_BREAK_AC + 1e-9, **kw)
    p_ab, q_ab = T.motor_d_pq(T.V_BREAK_AC - 1e-9, **kw)
    assert p_ac == pytest.approx(p_ab, abs=1e-6)
    assert q_ac == pytest.approx(q_ab, abs=1e-6)


def test_motor_d_fator_de_potencia_inicial():
    """Em 1 pu o modelo tem de partir do CompPF pedido."""
    po, pf = 1.0, 0.97
    p, q = T.motor_d_pq(1.0, po=po, comppf=pf)
    assert p == pytest.approx(po)
    esperado = po * math.tan(math.acos(pf))
    assert q == pytest.approx(esperado, abs=1e-9)


def test_motor_d_travado_absorve_muito_mais_potencia():
    """Travado, o compressor e um rotor bloqueado.

    E este salto que retem a tensao deprimida depois de uma falta -- o
    fenomeno que motivou o modelo.
    """
    kw = dict(po=1.0, comppf=0.97)
    p_regime, _ = T.motor_d_pq(0.90, **kw)
    p_travado, q_travado = T.motor_d_pq(0.90, stalled=True, **kw)
    assert p_travado > 2.0 * p_regime
    assert q_travado < 0.0


def test_motor_d_frequencia():
    p_n, _ = T.motor_d_pq(1.0, po=1.0, dfreq=0.0)
    p_d, q_d = T.motor_d_pq(1.0, po=1.0, dfreq=-0.02)
    assert p_d == pytest.approx(p_n * 0.98)
    assert q_d > 0


# ---------------------------------------------------------------------------
# Protecoes
# ---------------------------------------------------------------------------

def test_termica_rampa():
    assert float(T.thermal_fraction(0.0)) == 1.0
    assert float(T.thermal_fraction(1.3)) == pytest.approx(1.0)
    assert float(T.thermal_fraction(4.3)) == pytest.approx(0.0)
    assert float(T.thermal_fraction(2.8)) == pytest.approx(0.5, abs=1e-9)
    assert float(T.thermal_fraction(9.0)) == 0.0


def test_termica_limites_degenerados():
    assert float(T.thermal_fraction(2.0, th1t=1.0, th2t=1.0)) == 0.0


def test_contator_extremos_e_histerese():
    assert T.contactor_fraction(1.0) == 1.0
    assert T.contactor_fraction(0.20) == 0.0
    # Na faixa intermediaria o resultado depende de como se chegou ali.
    subindo = T.contactor_fraction(0.44, previous=0.0)
    descendo = T.contactor_fraction(0.44, previous=1.0)
    assert subindo != descendo


def test_conjugado_mecanico():
    assert float(T.mech_torque(1.0, 0.5, 0.0)) == pytest.approx(1.0)
    assert float(T.mech_torque(1.0, 0.5, 2.0)) == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Fracoes
# ---------------------------------------------------------------------------

def test_resto_vai_para_a_estatica():
    fr, est = T.static_remainder(0.1, 0.1, 0.1, 0.1, 0.1)
    assert sum(fr) == pytest.approx(0.5)
    assert est == pytest.approx(0.5)


def test_fracoes_excedentes_normalizam_e_zeram_a_estatica():
    """Regra explicita da especificacao para soma maior que 1."""
    fr, est = T.static_remainder(0.5, 0.4, 0.3, 0.2, 0.1)
    assert sum(fr) == pytest.approx(1.0)
    assert est == 0.0


def test_composicao_bate_com_o_mapa_inteligente():
    """A fracao motora do CLM tem de ser a mesma que o Mapa publica.

    Duas telas que discordassem sobre a mesma grandeza destruiriam a
    credibilidade das duas.
    """
    co = P.coherence_check()
    assert co["confere"], co
    assert co["desvio_maximo"] == 0.0


def test_composicao_por_classe_nunca_excede_um():
    for classe, comp in P.CLASS_COMPONENTS.items():
        assert sum(comp.values()) <= 1.0, classe
        assert all(v >= 0.0 for v in comp.values()), classe


def test_fracoes_de_mix_puro_reproduzem_a_linha_da_classe():
    for classe, comp in P.CLASS_COMPONENTS.items():
        fr = P.fractions_from_mix({classe: 1.0})
        for c in P.COMPONENTES:
            assert fr[c] == pytest.approx(comp[c], abs=1e-9), (classe, c)
        assert fr["estatica"] == pytest.approx(
            1.0 - sum(comp.values()), abs=1e-9)


def test_mix_vazio_nao_quebra():
    fr = P.fractions_from_mix({})
    assert fr["fracao_motora"] > 0
    assert sum(fr["mix"].values()) == pytest.approx(1.0)


def test_mix_normaliza_pesos_nao_unitarios():
    fr = P.fractions_from_mix({"residencial": 2.0, "comercial": 2.0})
    assert fr["mix"]["residencial"] == pytest.approx(0.5)


def test_ac_factor_move_o_motor_d_e_devolve_o_resto_a_estatica():
    base = P.fractions_from_mix({"residencial": 1.0}, ac_factor=1.0)
    meio = P.fractions_from_mix({"residencial": 1.0}, ac_factor=0.5)
    assert meio["Fmd"] == pytest.approx(base["Fmd"] * 0.5)
    assert meio["estatica"] > base["estatica"]
    soma = sum(meio[c] for c in P.COMPONENTES) + meio["estatica"]
    assert soma == pytest.approx(1.0, abs=1e-9)


def test_soma_publicada_fecha_exatamente_em_um():
    """As frações exibidas têm de somar 1 sem sobra de arredondamento.

    Com a estatica arredondada em separado, a soma fechava em 1,000001 --
    num cartao de parametros isso se le como erro de modelo.
    """
    casos = [
        {"residencial": 0.4958, "comercial": 0.3686,
         "industrial": 0.0488, "rural": 0.0869},
        {"residencial": 1.0},
        {"industrial": 0.7, "rural": 0.3},
        {"residencial": 0.33, "comercial": 0.33, "industrial": 0.34},
    ]
    for mix in casos:
        for ac in (0.0, 0.5, 1.0, 1.7):
            fr = P.fractions_from_mix(mix, ac_factor=ac)
            soma = sum(fr[c] for c in P.COMPONENTES) + fr["estatica"]
            assert soma == pytest.approx(1.0, abs=1e-12), (mix, ac, soma)


def test_ac_factor_zero_elimina_o_motor_d():
    fr = P.fractions_from_mix({"residencial": 1.0}, ac_factor=0.0)
    assert fr["Fmd"] == 0.0


# ---------------------------------------------------------------------------
# Escala do alimentador e aplicabilidade
# ---------------------------------------------------------------------------

def test_escala_do_alimentador_ancora_na_mediana():
    assert P.feeder_scale(P.RAIO_MEDIANO_KM) == pytest.approx(1.0)
    assert P.feeder_scale(None) == 1.0
    assert P.feeder_scale(0.0) == 1.0


def test_escala_do_alimentador_e_limitada():
    assert P.feeder_scale(0.01) == P.ESCALA_ALIMENTADOR_MIN
    assert P.feeder_scale(500.0) == P.ESCALA_ALIMENTADOR_MAX


def test_aplicabilidade_reprova_e_diz_qual_criterio():
    r = T.applicability(2.0, 0.99, q_mvar=0.5)
    assert not r["aplicavel"]
    reprovados = [t["criterio"] for t in r["testes"] if not t["ok"]]
    assert reprovados == ["carga minima"]


def test_aplicabilidade_aprova_caso_folgado():
    r = T.applicability(50.0, 1.0, q_mvar=20.0)
    assert r["aplicavel"]


def test_base_mva_tres_casos():
    assert T.mva_base_from_spec(150.0, 100.0) == 150.0
    assert T.mva_base_from_spec(-0.8, 80.0) == pytest.approx(100.0)
    assert T.mva_base_from_spec(0.0, 80.0) == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Registro de parametros
# ---------------------------------------------------------------------------

def test_registro_completo_e_sem_duplicata():
    vistos = set()
    for p in S.REGISTRO:
        chave = (p.bloco, p.nome)
        assert chave not in vistos, chave
        vistos.add(chave)
    assert len(S.REGISTRO) > 100


def test_todo_parametro_tem_procedencia_conhecida():
    """A regra que organiza o modulo: nenhum numero sem procedencia."""
    for p in S.REGISTRO:
        assert p.origem in S.ORIGENS, (p.nome, p.origem)
        assert p.descricao.strip()


def test_parametros_a_calibrar_tem_justificativa():
    """Se nao e afirmado, o cartao tem de dizer por que."""
    for p in S.REGISTRO:
        if p.origem == S.A_CALIBRAR:
            assert p.nota.strip(), p.nome


def test_reatancia_de_dispersao_segue_a_regra_da_especificacao():
    for bloco in ("motor_a", "motor_b", "motor_c"):
        ll = S.get(bloco, "Ll")
        lpp = S.get(bloco, "Lpp")
        assert ll is not None and lpp is not None
        assert ll.ref == pytest.approx(T.LL_OVER_LPP * lpp.ref, abs=1e-6)
        assert ll.origem == S.WECC


def test_motores_trifasicos_diferem_em_h_e_etrq():
    """E a unica diferenca entre eles no modelo. Se coincidissem, os tres
    slots seriam redundantes."""
    pares = set()
    for bloco in ("motor_a", "motor_b", "motor_c"):
        h = S.get(bloco, "H").ref
        etrq = S.get(bloco, "Etrq").ref
        pares.add((h, etrq))
    assert len(pares) == 3


def test_motor_d_e_monofasico_e_os_outros_trifasicos():
    assert S.get("fracoes", "Mtypd").ref == 1.0
    for nome in ("Mtypa", "Mtypb", "Mtypc"):
        assert S.get("fracoes", nome).ref == 3.0


def test_cobertura_declarada():
    c = S.counts()
    assert sum(c.values()) == len(S.REGISTRO)
    # Ha campos que nao afirmamos, e isso e declarado, nao escondido.
    assert c.get(S.A_CALIBRAR, 0) > 0


# ---------------------------------------------------------------------------
# Cartao
# ---------------------------------------------------------------------------

def test_cartao_marca_como_derivado_o_que_vem_de_dado_nosso():
    ctx = P.Contexto(nome="T", mva_fronteira=120.0, raio_km=4.0,
                     mix={"comercial": 1.0})
    card = P.build_card(ctx)
    por_nome = {(p["bloco"], p["nome"]): p for p in card["parametros"]}
    assert por_nome[("transformador", "MVA")]["origem"] == S.DERIVADO
    assert por_nome[("transformador", "MVA")]["valor"] == pytest.approx(120.0)
    for nome in P.COMPONENTES:
        assert por_nome[("fracoes", nome)]["origem"] == S.DERIVADO
    assert por_nome[("alimentador", "Rfdr")]["origem"] == S.PREMISSA


def test_cartao_sem_mva_mantem_a_referencia():
    """Sem dado, nao se inventa: o campo fica com o valor de referencia."""
    card = P.build_card(P.Contexto(mix={"residencial": 1.0}))
    por_nome = {(p["bloco"], p["nome"]): p for p in card["parametros"]}
    mva = por_nome[("transformador", "MVA")]
    assert mva["origem"] == S.WECC
    assert mva["valor"] == mva["referencia"]


def test_cartao_traz_o_aviso_de_que_nao_e_caso_pronto():
    card = P.build_card(P.Contexto(mix={"residencial": 1.0}))
    assert "nao" in card["aviso"].lower() or "não" in card["aviso"].lower()
    assert card["cobertura"].get(S.A_CALIBRAR, 0) > 0


def test_bloco_de_geracao_distribuida_declara_o_que_falta():
    card = P.build_card(P.Contexto(mix={"residencial": 1.0}, mmgd_kwp=1500.0))
    dg = card["geracao_distribuida"]
    assert dg["relevante"]
    assert dg["mmgd_mw"] == pytest.approx(1.5)
    assert "DER_A" in dg["nao_contemplado"]


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def test_payload_de_spec():
    d = SERVICE.clm_spec_payload()
    assert d["total_parametros"] == len(S.REGISTRO)
    assert d["coerencia_mapa"]["confere"]
    assert len(d["topologia"]["componentes"]) == 6
    assert len(d["topologia"]["barramentos"]) == 3


def test_payload_de_curvas_tem_series_alinhadas():
    d = SERVICE.clm_curves_payload()
    n = len(d["tensao"])
    for chave in ("p", "q"):
        assert len(d["estatica"][chave]) == n
    for chave in ("regime_p", "regime_q", "travado_p", "travado_q"):
        assert len(d["motor_d"][chave]) == n
    assert len(d["eletronica"]["descida"]) == n
    assert len(d["contator"]["fracao"]) == n
    assert len(d["termica"]["fracao"]) == len(d["termica"]["temperatura"])
    assert len(d["conjugado"]["etrq_0"]) == len(d["conjugado"]["velocidade"])


def test_payload_de_curvas_responde_aos_parametros():
    a = SERVICE.clm_curves_payload(vd1=0.80, vd2=0.70)
    b = SERVICE.clm_curves_payload(vd1=0.95, vd2=0.90)
    assert a["eletronica"]["descida"] != b["eletronica"]["descida"]


def test_payload_de_cartao_livre():
    d = SERVICE.clm_card_payload()
    assert d["exemplo_wecc"]["confere"]
    assert d["cartao_texto"].startswith("!")
    assert d["cobertura"].get(S.DERIVADO, 0) >= 5


def test_payload_de_validacao_expoe_limites():
    d = SERVICE.clm_validation_payload()
    assert all(c["ok"] for c in d["conferencias"]), d["conferencias"]
    assert d["exemplo_wecc"]["confere"]
    assert len(d["limites"]) >= 4


def test_cartao_texto_tem_procedencia_em_cada_linha_de_parametro():
    d = SERVICE.clm_card_payload()
    linhas = [l for l in d["cartao_texto"].splitlines()
              if l.startswith("  ")]
    assert linhas
    for l in linhas:
        assert "!" in l, l
