"""Testes para ocorrências mensais, atrasos e prioridade de contas."""

from datetime import date

import pytest

from painel.domain.entidades import TipoConta
from painel.domain.regras.ocorrencias import (
    aparece_em,
    numero_parcela,
    obter_abertas,
    obter_atrasadas,
)
from painel.domain.valores import Mes
from unit.domain.factories import conta, pagamento


def test_conta_fixa_aparece_todos_os_meses_ate_mes_final_inclusivo() -> None:
    fixa = conta(
        tipo=TipoConta.FIXA,
        mes_inicio="2026-11",
        mes_fim="2027-01",
    )

    meses = ("2026-10", "2026-11", "2026-12", "2027-01", "2027-02")
    assert [aparece_em(fixa, Mes(mes)) for mes in meses] == [
        False,
        True,
        True,
        True,
        False,
    ]


def test_conta_fixa_sem_mes_final_segue_aparecendo() -> None:
    fixa = conta(tipo=TipoConta.FIXA, mes_inicio="2026-11")

    assert aparece_em(fixa, Mes("2030-04"))


def test_conta_unica_aparece_apenas_no_mes_de_inicio() -> None:
    unica = conta(tipo=TipoConta.UNICA, mes_inicio="2026-12")

    assert not aparece_em(unica, Mes("2026-11"))
    assert aparece_em(unica, Mes("2026-12"))
    assert not aparece_em(unica, Mes("2027-01"))


def test_parcelas_usam_numero_inicial_e_param_no_fim() -> None:
    parcelada = conta(
        tipo=TipoConta.PARCELADA,
        mes_inicio="2026-12",
        parcela_inicial=3,
        total_parcelas=8,
    )

    assert [
        numero_parcela(parcelada, Mes(mes))
        for mes in (
            "2026-11",
            "2026-12",
            "2027-01",
            "2027-05",
            "2027-06",
        )
    ] == [None, 3, 4, 8, None]
    assert aparece_em(parcelada, Mes("2027-05"))
    assert not aparece_em(parcelada, Mes("2027-06"))
    assert numero_parcela(conta(), Mes("2026-11")) is None


def test_conta_de_novembro_nao_paga_fica_atrasada_em_dezembro() -> None:
    fixa = conta(id="luz", tipo=TipoConta.FIXA, mes_inicio="2026-11")

    abertas = obter_atrasadas([fixa], [], Mes("2026-12"), Mes("2026-11"))

    assert len(abertas) == 1
    assert abertas[0].mes_origem == Mes("2026-11")
    assert abertas[0].atrasada


def test_conta_paga_nao_fica_atrasada() -> None:
    fixa = conta(id="luz", tipo=TipoConta.FIXA, mes_inicio="2026-11")
    pago = pagamento(conta_id="luz", mes_conta="2026-11")

    assert obter_atrasadas([fixa], [pago], Mes("2026-12"), Mes("2026-11")) == ()


def test_ocorrencias_anteriores_ao_desde_nao_viram_atrasadas() -> None:
    fixa = conta(id="luz", tipo=TipoConta.FIXA, mes_inicio="2026-09")

    atrasadas = obter_atrasadas([fixa], [], Mes("2026-12"), Mes("2026-11"))

    assert [item.mes_origem for item in atrasadas] == [Mes("2026-11")]


def test_ocorrencias_atrasadas_incluem_origem_de_cada_mes() -> None:
    fixa = conta(id="luz", tipo=TipoConta.FIXA, mes_inicio="2026-10")

    atrasadas = obter_atrasadas([fixa], [], Mes("2027-01"), Mes("2026-11"))

    assert [item.mes_origem for item in atrasadas] == [
        Mes("2026-11"),
        Mes("2026-12"),
    ]


def test_atrasadas_ignoram_conta_que_nao_apareceu() -> None:
    unica = conta(tipo=TipoConta.UNICA, mes_inicio="2026-10")

    assert obter_atrasadas([unica], [], Mes("2026-12"), Mes("2026-11")) == ()


def test_abertas_incluem_meses_atrasados_e_mes_atual_sem_repetir_pago() -> None:
    fixa = conta(id="luz", tipo=TipoConta.FIXA, mes_inicio="2026-11")
    pago = pagamento(conta_id="luz", mes_conta="2026-11", data_pagamento=date(2026, 11, 4))

    abertas = obter_abertas([fixa], [pago], Mes("2026-12"), Mes("2026-11"))

    assert [(item.mes_origem, item.atrasada) for item in abertas] == [(Mes("2026-12"), False)]


def test_abertas_ordenam_atraso_juros_e_vencimento() -> None:
    contas = [
        conta(id="sem-dia", nome="Sem dia", dia_vencimento=0),
        conta(id="dia-10", nome="Dia 10", dia_vencimento=10),
        conta(id="juros", nome="Juros", dia_vencimento=20, juros_altos=True),
        conta(
            id="atrasada",
            nome="Atrasada",
            tipo=TipoConta.UNICA,
            mes_inicio="2026-10",
            juros_altos=False,
        ),
    ]

    abertas = obter_abertas(contas, [], Mes("2026-11"), Mes("2026-10"))

    assert [(item.conta.id, item.atrasada) for item in abertas] == [
        ("atrasada", True),
        ("juros", False),
        ("dia-10", False),
        ("sem-dia", False),
    ]


@pytest.mark.parametrize("mes", ["2026-11", "2026-12"])
def test_parcela_do_mes_esta_pendente_quando_nao_foi_paga(mes: str) -> None:
    parcelada = conta(
        tipo=TipoConta.PARCELADA,
        mes_inicio="2026-11",
        parcela_inicial=1,
        total_parcelas=2,
    )

    abertas = obter_abertas([parcelada], [], Mes(mes), Mes("2026-11"))

    assert [(item.mes_origem, item.atrasada) for item in abertas] == (
        [(Mes("2026-11"), False)]
        if mes == "2026-11"
        else [
            (Mes("2026-11"), True),
            (Mes("2026-12"), False),
        ]
    )
