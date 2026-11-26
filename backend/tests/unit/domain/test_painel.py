from datetime import date

import pytest

from painel.domain.entidades import ResumoMensal, TipoConta
from painel.domain.erros import ErroDeValidacao
from painel.domain.regras.painel import (
    cobertura_percentual,
    data_do_recebimento,
    dias_para_vencer,
    ganhos_do_mes,
    inicio_pela_parcela,
    itens_por_categoria,
    mes_fim_ao_parar,
    numero_parcela_paga,
)
from painel.domain.valores import Dinheiro, Mes
from unit.domain.factories import conta, dinheiro, ganho, pagamento


def _resumo(tenho="0", entra="0", corridas="0", falta="0"):
    zero = Dinheiro.zero()
    return ResumoMensal(
        mes=Mes("2026-11"),
        tenho=dinheiro(tenho),
        vai_entrar=dinheiro(entra),
        recebido=zero,
        corridas=dinheiro(corridas),
        abertas=(),
        falta_pagar=dinheiro(falta),
        pagas=(),
        ja_pago=zero,
        sobra=zero,
    )


@pytest.mark.parametrize(
    ("tenho", "entra", "corridas", "falta", "pct"),
    [
        ("0", "0", "0", "0", 100),
        ("50", "0", "0", "200", 25),
        ("100", "50", "50", "100", 100),
        ("-100", "0", "0", "50", 0),
        ("1", "0", "0", "3", 33),
    ],
)
def test_cobertura(tenho, entra, corridas, falta, pct):
    assert cobertura_percentual(_resumo(tenho, entra, corridas, falta)) == pct


def test_dias_para_vencer():
    c = conta(dia_vencimento=25)
    hoje = date(2026, 11, 20)
    assert dias_para_vencer(c, Mes("2026-11"), hoje, atrasada=False) == 5
    assert dias_para_vencer(conta(dia_vencimento=10), Mes("2026-11"), hoje, False) == -10
    assert dias_para_vencer(c, Mes("2026-12"), hoje, False) is None
    assert dias_para_vencer(c, Mes("2026-11"), hoje, atrasada=True) is None
    assert dias_para_vencer(conta(), Mes("2026-11"), hoje, False) is None


def test_numero_parcela_paga():
    c = conta(tipo=TipoConta.PARCELADA, parcela_inicial=3, total_parcelas=5, mes_inicio="2026-10")
    assert numero_parcela_paga(c, pagamento(mes_conta="2026-11")) == 4
    assert numero_parcela_paga(conta(), pagamento()) is None


def test_itens_por_categoria():
    aluguel = conta(id="a", nome="Aluguel", valor="900", tipo=TipoConta.FIXA, mes_inicio="2026-01")
    antiga = conta(
        id="b", nome="Luz", valor="50", tipo=TipoConta.FIXA, mes_inicio="2026-01", mes_fim="2026-05"
    )
    celular = conta(
        id="c",
        nome="Celular",
        valor="100",
        tipo=TipoConta.PARCELADA,
        mes_inicio="2026-11",
        parcela_inicial=2,
        total_parcelas=4,
        categoria="outros",
    )
    quitada = conta(id="d", nome="Bico", valor="30", mes_inicio="2026-11", categoria="outros")
    unica = conta(id="e", nome="Multa", valor="80", mes_inicio="2026-11", categoria="outros")
    pago = pagamento(conta_id="d", mes_conta="2026-11", valor="30")
    itens = itens_por_categoria(
        Mes("2026-11"), Mes("2026-01"), [aluguel, antiga, celular, quitada, unica], [pago]
    )
    assert [(i.conta.nome, i.valor.valor) for i in itens["casa"]] == [
        ("Aluguel", dinheiro("900").valor)
    ]
    outros = {i.conta.nome: i for i in itens["outros"]}
    assert set(outros) == {"Celular", "Multa"}
    assert outros["Celular"].valor == dinheiro("300") and outros["Celular"].parcelas_restantes == 3
    assert outros["Multa"].parcelas_restantes is None


def test_ganhos_do_mes():
    nov = ganho(id="n", data=date(2026, 11, 10), recebido=True)
    out_pendente = ganho(id="o", data=date(2026, 10, 5), recebido=False)
    out_recebido = ganho(id="r", data=date(2026, 10, 6), recebido=True)
    dez = ganho(id="d", data=date(2026, 12, 1))
    lista = ganhos_do_mes([nov, out_pendente, out_recebido, dez], Mes("2026-11"))
    assert [(x.ganho.id, x.atrasado) for x in lista] == [("n", False), ("o", True)]


def test_data_do_recebimento():
    hoje = date(2026, 11, 20)
    assert data_do_recebimento(date(2026, 11, 5), Mes("2026-11"), hoje) == date(2026, 11, 5)
    assert data_do_recebimento(date(2026, 11, 28), Mes("2026-11"), hoje) == hoje
    assert data_do_recebimento(date(2026, 10, 5), Mes("2026-11"), hoje) == hoje


def test_inicio_pela_parcela():
    ref = Mes("2026-11")
    assert inicio_pela_parcela(None, ref, 3, 8) == (ref, 3)
    parcelada = conta(
        tipo=TipoConta.PARCELADA, mes_inicio="2026-09", parcela_inicial=1, total_parcelas=8
    )
    assert inicio_pela_parcela(parcelada, ref, 4, 8) == (Mes("2026-09"), 2)
    assert inicio_pela_parcela(parcelada, ref, 1, 8) == (ref, 1)  # daria parcela 0 no início
    assert inicio_pela_parcela(conta(mes_inicio="2026-09"), ref, 2, 3) == (ref, 2)
    futura = conta(
        tipo=TipoConta.PARCELADA, mes_inicio="2027-01", parcela_inicial=1, total_parcelas=2
    )
    assert inicio_pela_parcela(futura, ref, 1, 2) == (ref, 1)
    with pytest.raises(ErroDeValidacao):
        inicio_pela_parcela(None, ref, 5, 4)


def test_mes_fim_ao_parar():
    fixa = conta(tipo=TipoConta.FIXA, mes_inicio="2026-09")
    assert mes_fim_ao_parar(fixa, Mes("2026-11")) == Mes("2026-10")
    with pytest.raises(ErroDeValidacao):
        mes_fim_ao_parar(fixa, Mes("2026-09"))
    with pytest.raises(ErroDeValidacao):
        mes_fim_ao_parar(conta(), Mes("2026-11"))


def test_referencia_para_editar():
    from painel.domain.regras.painel import referencia_para_editar

    ref = Mes("2026-11")
    p = conta(tipo=TipoConta.PARCELADA, mes_inicio="2026-09", parcela_inicial=1, total_parcelas=8)
    assert referencia_para_editar(p, ref) == (ref, 3)
    acabou = conta(
        tipo=TipoConta.PARCELADA, mes_inicio="2026-01", parcela_inicial=1, total_parcelas=2
    )
    assert referencia_para_editar(acabou, ref) == (Mes("2026-01"), 1)
    futura = conta(
        tipo=TipoConta.PARCELADA, mes_inicio="2027-02", parcela_inicial=4, total_parcelas=9
    )
    assert referencia_para_editar(futura, ref) == (Mes("2027-02"), 4)
    assert referencia_para_editar(conta(mes_inicio="2026-08"), ref) == (Mes("2026-08"), None)
    fixa = conta(tipo=TipoConta.FIXA, mes_inicio="2026-01")
    assert referencia_para_editar(fixa, ref) == (ref, None)


def test_situacao_vencimento():
    from painel.domain.regras.painel import situacao_vencimento

    assert [situacao_vencimento(d) for d in (None, -1, 0, 1, 5, 6)] == [
        None,
        "venceu",
        "hoje",
        "em_breve",
        "em_breve",
        "no_prazo",
    ]
