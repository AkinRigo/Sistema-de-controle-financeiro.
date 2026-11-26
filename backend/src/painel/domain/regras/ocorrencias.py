"""Regras de ocorrência mensal e contas atrasadas."""

from collections.abc import Iterable

from painel.domain.entidades import Conta, ContaAberta, Pagamento, TipoConta
from painel.domain.valores import Mes


def numero_parcela(conta: Conta, mes: Mes) -> int | None:
    """Retorna o número da parcela no mês, ou None quando não se aplica."""
    if conta.tipo is not TipoConta.PARCELADA or mes < conta.mes_inicio:
        return None
    assert conta.parcela_inicial is not None
    assert conta.total_parcelas is not None
    numero = conta.parcela_inicial + mes.diferenca(conta.mes_inicio)
    return numero if numero <= conta.total_parcelas else None


def aparece_em(conta: Conta, mes: Mes) -> bool:
    """Indica se a conta gera uma ocorrência no mês."""
    if mes < conta.mes_inicio:
        return False
    if conta.tipo is TipoConta.FIXA:
        return conta.mes_fim is None or mes <= conta.mes_fim
    if conta.tipo is TipoConta.UNICA:
        return mes == conta.mes_inicio
    return numero_parcela(conta, mes) is not None


def _mes_pago(pagamentos: Iterable[Pagamento]) -> set[tuple[str, Mes]]:
    return {(pagamento.conta_id, pagamento.mes_conta) for pagamento in pagamentos}


def obter_atrasadas(
    contas: Iterable[Conta],
    pagamentos: Iterable[Pagamento],
    mes: Mes,
    desde: Mes,
) -> tuple[ContaAberta, ...]:
    """Lista ocorrências não pagas anteriores ao mês consultado e desde o cadastro."""
    contas_lista = tuple(contas)
    pagamentos_lista = tuple(pagamentos)
    meses_pagos = _mes_pago(pagamentos_lista)
    atrasadas: list[ContaAberta] = []
    for conta in contas_lista:
        inicio = max(conta.mes_inicio, desde)
        cursor = inicio
        while cursor < mes:
            if aparece_em(conta, cursor) and (conta.id, cursor) not in meses_pagos:
                atrasadas.append(
                    ContaAberta(
                        conta=conta,
                        mes_origem=cursor,
                        atrasada=True,
                        numero_parcela=numero_parcela(conta, cursor),
                    )
                )
            cursor = cursor.somar(1)
    return tuple(atrasadas)


def ordenar_abertas(contas_abertas: Iterable[ContaAberta]) -> tuple[ContaAberta, ...]:
    """Ordena atrasadas primeiro, depois juros altos e dia de vencimento."""
    return tuple(
        sorted(
            contas_abertas,
            key=lambda aberta: (
                not aberta.atrasada,
                not aberta.conta.juros_altos,
                aberta.conta.dia_vencimento == 0,
                aberta.conta.dia_vencimento or 32,
                aberta.conta.nome.casefold(),
                aberta.mes_origem.valor,
            ),
        )
    )


def obter_abertas(
    contas: Iterable[Conta],
    pagamentos: Iterable[Pagamento],
    mes: Mes,
    desde: Mes,
) -> tuple[ContaAberta, ...]:
    """Retorna atrasadas e ocorrências do mês atual ainda não pagas."""
    contas_lista = tuple(contas)
    pagamentos_lista = tuple(pagamentos)
    meses_pagos = _mes_pago(pagamentos_lista)
    abertas = list(obter_atrasadas(contas_lista, pagamentos_lista, mes, desde))
    for conta in contas_lista:
        if aparece_em(conta, mes) and (conta.id, mes) not in meses_pagos:
            abertas.append(
                ContaAberta(
                    conta=conta,
                    mes_origem=mes,
                    atrasada=False,
                    numero_parcela=numero_parcela(conta, mes),
                )
            )
    return ordenar_abertas(abertas)
