"""Testes para os tipos de valor e invariantes das entidades."""

from decimal import Decimal

import pytest

from painel.domain.entidades import TipoConta
from painel.domain.erros import ErroDeValidacao
from painel.domain.valores import Dinheiro, Mes, somar_dinheiro
from unit.domain.factories import conta, dinheiro


def test_mes_soma_com_virada_de_ano_e_compara() -> None:
    novembro = Mes("2026-11")
    janeiro = novembro.somar(2)

    assert janeiro == Mes("2027-01")
    assert janeiro.diferenca(novembro) == 2
    assert janeiro.comparar(novembro) == 1
    assert novembro.comparar(janeiro) == -1
    assert novembro.comparar(Mes("2026-11")) == 0


@pytest.mark.parametrize("valor", ["2026-00", "2026-13", "26-11", "2026/11", ""])
def test_mes_recusa_formatos_invalidos(valor: str) -> None:
    with pytest.raises(ErroDeValidacao):
        Mes(valor)


def test_mes_recusa_tipo_invalido_e_ano_zero() -> None:
    with pytest.raises(ErroDeValidacao):
        Mes("2026-11").somar(1.5)  # type: ignore[arg-type]
    with pytest.raises(ErroDeValidacao):
        Mes("2026-11").somar(True)
    with pytest.raises(ErroDeValidacao):
        Mes("0001-01").somar(-1)


def test_mes_recusa_valor_que_nao_seja_texto() -> None:
    with pytest.raises(ErroDeValidacao):
        Mes(202611)  # type: ignore[arg-type]


def test_dinheiro_arredonda_e_mantem_duas_casas() -> None:
    quantia = Dinheiro.de("10.125")

    assert quantia == dinheiro("10.13")
    assert quantia.valor == Decimal("10.13")
    assert Dinheiro.de(12) == dinheiro("12.00")
    assert Dinheiro.de(Decimal("2.50")) == dinheiro("2.50")


def test_dinheiro_recusa_texto_invalido_e_quantia_grande_demais() -> None:
    with pytest.raises(ErroDeValidacao):
        Dinheiro.de("não é dinheiro")
    with pytest.raises(ErroDeValidacao):
        Dinheiro(Decimal("1e1000"))


def test_dinheiro_faz_operacoes_sem_float() -> None:
    total = dinheiro("10.00") + dinheiro("2.50")
    total -= dinheiro("1.00")

    assert total == dinheiro("11.50")
    assert total * 2 == dinheiro("23.00")
    assert total / 2 == dinheiro("5.75")
    assert somar_dinheiro([total, dinheiro("0.50")]) == dinheiro("12.00")


@pytest.mark.parametrize("valor", [1.5, True])
def test_dinheiro_recusa_float_e_booleano(valor: float | bool) -> None:
    with pytest.raises(TypeError):
        Dinheiro.de(valor)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Dinheiro(valor)  # type: ignore[arg-type]


@pytest.mark.parametrize("valor", [Decimal("NaN"), Decimal("Infinity")])
def test_dinheiro_recusa_valor_nao_finito(valor: Decimal) -> None:
    with pytest.raises(ErroDeValidacao):
        Dinheiro(valor)


def test_dinheiro_recusa_divisao_por_zero() -> None:
    with pytest.raises(ZeroDivisionError):
        dinheiro("1.00") / 0


def test_operacoes_de_dinheiro_recusam_tipos_nao_suportados() -> None:
    quantia = dinheiro("1.00")

    assert quantia.__add__(1) is NotImplemented
    assert quantia.__sub__(1) is NotImplemented
    assert quantia.__mul__("2") is NotImplemented  # type: ignore[arg-type]
    assert quantia.__truediv__("2") is NotImplemented  # type: ignore[arg-type]


@pytest.mark.parametrize("fator", [1.5, True])
def test_dinheiro_recusa_float_em_multiplicacao_e_divisao(fator: float | bool) -> None:
    quantia = dinheiro("1.00")

    with pytest.raises(TypeError):
        quantia * fator  # type: ignore[operator]
    with pytest.raises(TypeError):
        quantia / fator  # type: ignore[operator]


def test_conta_valida_campos_conforme_tipo() -> None:
    assert conta(tipo=TipoConta.FIXA, mes_fim="2026-12").mes_fim == Mes("2026-12")
    assert (
        conta(
            tipo=TipoConta.PARCELADA,
            parcela_inicial=3,
            total_parcelas=8,
        ).total_parcelas
        == 8
    )


@pytest.mark.parametrize(
    "campos",
    [
        {"tipo": TipoConta.FIXA, "mes_fim": "2026-10"},
        {"tipo": TipoConta.FIXA, "parcela_inicial": 1, "total_parcelas": 2},
        {"tipo": TipoConta.PARCELADA},
        {"tipo": TipoConta.PARCELADA, "parcela_inicial": 0, "total_parcelas": 2},
        {"tipo": TipoConta.PARCELADA, "parcela_inicial": 3, "total_parcelas": 2},
        {
            "tipo": TipoConta.PARCELADA,
            "parcela_inicial": 1,
            "total_parcelas": 2,
            "mes_fim": "2026-12",
        },
        {"tipo": TipoConta.UNICA, "mes_fim": "2026-12"},
        {"tipo": TipoConta.UNICA, "parcela_inicial": 1, "total_parcelas": 2},
        {"dia_vencimento": 32},
        {"dia_vencimento": -1},
    ],
)
def test_conta_recusa_combinacoes_invalidas(campos: dict[str, object]) -> None:
    with pytest.raises(ErroDeValidacao):
        conta(**campos)  # type: ignore[arg-type]
