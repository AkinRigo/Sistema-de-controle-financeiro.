"""Cálculo da dívida remanescente de contas não fixas."""

from collections.abc import Iterable

from painel.domain.entidades import Conta, Pagamento, TipoConta
from painel.domain.regras.ocorrencias import aparece_em
from painel.domain.valores import Dinheiro, Mes, somar_dinheiro


def calcular_divida_conta(
    conta: Conta,
    desde: Mes,
    pagamentos: Iterable[Pagamento],
) -> Dinheiro:
    """Calcula o valor ainda devido para uma conta única ou parcelada."""
    if conta.tipo is TipoConta.FIXA:
        return Dinheiro.zero()

    pagamentos_lista = tuple(pagamentos)
    meses_pagos = {
        pagamento.mes_conta for pagamento in pagamentos_lista if pagamento.conta_id == conta.id
    }

    if conta.tipo is TipoConta.UNICA:
        return Dinheiro.zero() if conta.mes_inicio in meses_pagos else conta.valor

    assert conta.parcela_inicial is not None
    assert conta.total_parcelas is not None
    ultima_parcela = conta.mes_inicio.somar(conta.total_parcelas - conta.parcela_inicial)
    cursor = max(conta.mes_inicio, desde)
    quantidade_em_aberto = 0
    while cursor <= ultima_parcela:
        if aparece_em(conta, cursor) and cursor not in meses_pagos:
            quantidade_em_aberto += 1
        cursor = cursor.somar(1)
    return conta.valor * quantidade_em_aberto


def calcular_divida_total(
    contas: Iterable[Conta],
    desde: Mes,
    pagamentos: Iterable[Pagamento],
) -> Dinheiro:
    """Soma a dívida remanescente de todas as contas."""
    pagamentos_lista = tuple(pagamentos)
    return somar_dinheiro(calcular_divida_conta(conta, desde, pagamentos_lista) for conta in contas)
