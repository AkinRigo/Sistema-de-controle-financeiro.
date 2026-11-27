"""Testes para dívida pendente e classificação de despesas."""

from datetime import date

import pytest

from painel.domain.entidades import TipoConta
from painel.domain.erros import ErroDeValidacao
from painel.domain.regras.categorias import (
    CATEGORIAS,
    categoria_da_conta,
    resumir_categorias,
    sugerir_categoria,
)
from painel.domain.regras.divida import calcular_divida_conta, calcular_divida_total
from painel.domain.valores import Mes
from unit.domain.factories import conta, dinheiro, pagamento


def test_divida_de_unica_paga_e_nao_paga() -> None:
    unica = conta(id="unica", tipo=TipoConta.UNICA, valor="80.00")
    paga = pagamento(conta_id="unica", mes_conta="2026-11")

    assert calcular_divida_conta(unica, Mes("2026-11"), []) == dinheiro("80.00")
    assert calcular_divida_conta(unica, Mes("2026-11"), [paga]) == dinheiro("0.00")


def test_divida_parcelada_desconta_parcelas_pagas_e_respeita_desde() -> None:
    parcelada = conta(
        id="celular",
        valor="25.00",
        tipo=TipoConta.PARCELADA,
        mes_inicio="2026-11",
        parcela_inicial=1,
        total_parcelas=4,
    )
    pagamento_parcela = pagamento(
        conta_id="celular",
        mes_conta="2026-12",
    )

    assert calcular_divida_conta(
        parcelada,
        Mes("2026-11"),
        [pagamento_parcela],
    ) == dinheiro("75.00")
    assert calcular_divida_conta(
        parcelada,
        Mes("2027-01"),
        [pagamento_parcela],
    ) == dinheiro("50.00")
    assert calcular_divida_conta(
        parcelada,
        Mes("2027-01"),
        [],
    ) == dinheiro("50.00")


def test_conta_fixa_nao_e_divida_e_total_soma_contas() -> None:
    fixa = conta(id="aluguel", valor="500", tipo=TipoConta.FIXA)
    unica = conta(id="unica", valor="30")

    assert calcular_divida_conta(fixa, Mes("2026-11"), []) == dinheiro("0")
    assert calcular_divida_total([fixa, unica], Mes("2026-11"), []) == dinheiro("30")


@pytest.mark.parametrize(
    ("nome", "credor", "categoria"),
    [
        ("Gasolina", None, "moto"),
        ("Combustível", None, "moto"),
        ("Revisão", "Oficina do Zé", "moto"),
        ("Cartão de crédito", None, "cartoes"),
        ("Fatura", "Nubank", "cartoes"),
        ("Aluguel", None, "casa"),
        ("Conta de água", None, "casa"),
        ("Internet", "Inter", "cartoes"),
        ("Internet", None, "casa"),
        ("Açougue", None, "alimentacao"),
        ("Feira", None, "alimentacao"),
        ("Empréstimo", "Mãe", "cartoes"),
        ("Ajuda", "Mãe", "pessoas"),
        ("Ajuda", "Amiga", "pessoas"),
        ("Ajuda", "Tia", "pessoas"),
        ("Ajuda", "Prima", "pessoas"),
        ("Vó", None, "pessoas"),
        ("Devolução", None, "outros"),
        ("Cinema", None, "outros"),
    ],
)
def test_sugere_categoria_por_nome_e_credor(
    nome: str,
    credor: str | None,
    categoria: str,
) -> None:
    assert sugerir_categoria(nome, credor) == categoria


def test_categoria_informada_tem_precedencia_sobre_sugestao() -> None:
    aluguel = conta(nome="Aluguel", categoria="moto")

    assert categoria_da_conta(aluguel) == "moto"


def test_categoria_invalida_e_rejeitada() -> None:
    with pytest.raises(ErroDeValidacao):
        categoria_da_conta(conta(categoria="inválida"))


def test_resumo_por_categoria_ignora_pagamento_sem_conta() -> None:
    resumo = resumir_categorias(
        Mes("2026-11"),
        Mes("2026-11"),
        [],
        [pagamento(conta_id="removida", mes_conta="2026-11")],
    )

    assert all(totais.ja_pago == dinheiro("0") for totais in resumo.values())


def test_resumo_por_categoria_reune_abertas_pagamentos_fixas_e_divida() -> None:
    aluguel = conta(
        id="aluguel",
        nome="Aluguel",
        valor="100",
        tipo=TipoConta.FIXA,
        mes_inicio="2026-11",
    )
    compra = conta(
        id="compra",
        nome="Mercado",
        valor="20",
        tipo=TipoConta.UNICA,
        mes_inicio="2026-11",
    )
    pago = pagamento(
        conta_id="compra",
        mes_conta="2026-11",
        valor="18",
    )

    resumo = resumir_categorias(
        Mes("2026-11"),
        Mes("2026-11"),
        [aluguel, compra],
        [pago],
    )

    assert resumo["casa"].falta_pagar == dinheiro("100")
    assert resumo["casa"].fixas_por_mes == dinheiro("100")
    assert resumo["casa"].ainda_devo == dinheiro("0")
    assert resumo["alimentacao"].ja_pago == dinheiro("18")
    assert resumo["alimentacao"].ainda_devo == dinheiro("0")
    assert set(resumo) == set(CATEGORIAS)


def test_resumo_por_categoria_considera_somente_a_competencia_selecionada() -> None:
    aluguel = conta(
        id="aluguel",
        nome="Aluguel",
        valor="100",
        tipo=TipoConta.FIXA,
        mes_inicio="2026-10",
    )
    parcela = conta(
        id="parcela",
        nome="Celular",
        valor="50",
        tipo=TipoConta.PARCELADA,
        mes_inicio="2026-10",
        parcela_inicial=1,
        total_parcelas=3,
        categoria="moto",
    )
    conta_anterior = conta(
        id="anterior",
        nome="Compra",
        valor="25",
        tipo=TipoConta.UNICA,
        mes_inicio="2026-10",
    )
    pagamento_atrasado = pagamento(
        conta_id="anterior",
        mes_conta="2026-10",
        data_pagamento=date(2026, 11, 10),
    )

    resumo = resumir_categorias(
        Mes("2026-11"),
        Mes("2026-10"),
        [aluguel, parcela, conta_anterior],
        [pagamento_atrasado],
    )

    assert resumo["casa"].falta_pagar == dinheiro("100")
    assert resumo["moto"].falta_pagar == dinheiro("50")
    assert resumo["outros"].falta_pagar == dinheiro("0")
    assert resumo["outros"].ja_pago == dinheiro("0")
