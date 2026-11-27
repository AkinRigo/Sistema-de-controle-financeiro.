from datetime import date

from painel.domain.entidades import ContaAberta, ResumoMensal
from painel.domain.regras.saldo_diario import saldo_dia_a_dia
from painel.domain.valores import Dinheiro, Mes
from unit.domain.factories import conta, dinheiro, ganho, pagamento

HOJE = date(2026, 11, 26)


def _resumo(mes="2026-11", tenho="0", entra="0", falta="0", abertas=()):
    zero = Dinheiro.zero()
    return ResumoMensal(
        mes=Mes(mes),
        tenho=dinheiro(tenho),
        vai_entrar=dinheiro(entra),
        recebido=zero,
        corridas=zero,
        abertas=tuple(abertas),
        falta_pagar=dinheiro(falta),
        pagas=(),
        ja_pago=zero,
        sobra=zero,
    )


def _saldo(r, dia):
    return r.dias[dia - 1].saldo.valor


def test_mes_atual_passado_desfeito_e_futuro_previsto():
    luz = conta(id="luz", nome="Luz", valor="200")
    aluguel = conta(id="aluguel", nome="Aluguel", valor="1300", dia_vencimento=28)
    cartao = conta(id="cartao", nome="Cartão", valor="2100", dia_vencimento=10)
    abertas = [
        ContaAberta(aluguel, Mes("2026-11"), False),
        ContaAberta(cartao, Mes("2026-10"), True),
    ]
    ganhos = [
        ganho(id="bico", valor="1500", data=date(2026, 11, 6), recebido=True),
        ganho(id="salario", valor="1800", data=date(2026, 11, 29)),
    ]
    pagos = [pagamento(conta_id="luz", valor="200", data_pagamento=date(2026, 11, 12))]
    resumo = _resumo(tenho="2380", entra="1800", falta="3400", abertas=abertas)

    r = saldo_dia_a_dia(resumo, HOJE, [luz, aluguel, cartao], pagos, ganhos)

    assert len(r.dias) == 30 and r.hoje == 26
    assert _saldo(r, 1) == 2380 - 1500 + 200  # antes do bico e da luz
    assert _saldo(r, 6) == 2380 + 200  # bico já entrou, luz ainda não saiu
    assert _saldo(r, 12) == 2380 and _saldo(r, 26) == 2380
    assert not r.dias[25].previsao and r.dias[26].previsao
    assert [m.nome for m in r.dias[11].movimentos] == ["Luz"]
    # atrasada entra amanhã; aluguel no dia 28; salário no 29
    assert _saldo(r, 27) == 2380 - 2100
    assert _saldo(r, 28) == 2380 - 2100 - 1300
    assert _saldo(r, 30) == 2380 + 1800 - 3400  # tenho + vai entrar − falta pagar
    assert r.menor.dia == 28 and r.menor.saldo.valor == -1020
    assert r.dias[28].movimentos[0].previsto


def test_conta_sem_dia_e_ganho_de_mes_anterior_entram_amanha():
    luz = conta(id="luz", nome="Luz", valor="50")
    resumo = _resumo(tenho="100", abertas=[ContaAberta(luz, Mes("2026-11"), False)])
    atrasado = ganho(valor="30", data=date(2026, 10, 5))
    r = saldo_dia_a_dia(resumo, HOJE, [luz], [], [atrasado])
    assert _saldo(r, 26) == 100 and _saldo(r, 27) == 80


def test_mes_que_ja_passou_so_mostra_o_que_aconteceu():
    c = conta(id="c", valor="40")
    resumo = _resumo(mes="2026-10", tenho="500", abertas=[ContaAberta(c, Mes("2026-10"), False)])
    pagos = [pagamento(conta_id="outra", valor="40", data_pagamento=date(2026, 11, 3))]
    r = saldo_dia_a_dia(resumo, HOJE, [c], pagos, [])
    assert len(r.dias) == 31 and r.hoje is None and r.menor is None
    assert all(not d.previsao for d in r.dias)
    assert _saldo(r, 31) == 540  # o pagamento de novembro é desfeito
    assert r.dias[0].movimentos == ()


def test_mes_futuro_e_todo_previsao():
    aluguel = conta(id="a", nome="Aluguel", valor="1000", dia_vencimento=31)
    resumo = _resumo(
        mes="2026-12", tenho="300", abertas=[ContaAberta(aluguel, Mes("2026-12"), False)]
    )
    r = saldo_dia_a_dia(resumo, HOJE, [aluguel], [], [ganho(valor="900", data=date(2026, 12, 5))])
    assert r.hoje is None and all(d.previsao for d in r.dias)
    assert _saldo(r, 4) == 300 and _saldo(r, 5) == 1200 and _saldo(r, 31) == 200
    assert r.menor.dia == 31


def test_hoje_e_o_ultimo_dia_do_mes():
    c = conta(id="c", nome="Gás", valor="70", dia_vencimento=10)
    resumo = _resumo(tenho="100", abertas=[ContaAberta(c, Mes("2026-11"), False)])
    r = saldo_dia_a_dia(resumo, date(2026, 11, 30), [c], [], [])
    assert _saldo(r, 30) == 30 and r.dias[29].previsao
    assert r.menor.dia == 30
