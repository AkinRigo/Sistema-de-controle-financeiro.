"""Fábricas pequenas para os testes do domínio."""

from datetime import date

from painel.domain.entidades import Banco, Conta, Ganho, Pagamento, TipoConta, Usuario
from painel.domain.valores import Dinheiro, Mes


def dinheiro(valor: str | int) -> Dinheiro:
    return Dinheiro.de(valor)


def conta(
    *,
    id: str = "conta-1",
    nome: str = "Conta",
    valor: str = "10.00",
    tipo: TipoConta = TipoConta.UNICA,
    mes_inicio: str = "2026-11",
    categoria: str = "",
    credor: str | None = None,
    dia_vencimento: int = 0,
    mes_fim: str | None = None,
    parcela_inicial: int | None = None,
    total_parcelas: int | None = None,
    juros_altos: bool = False,
) -> Conta:
    return Conta(
        id=id,
        usuario_id="usuario-1",
        nome=nome,
        valor=dinheiro(valor),
        tipo=tipo,
        mes_inicio=Mes(mes_inicio),
        categoria=categoria,
        credor=credor,
        dia_vencimento=dia_vencimento,
        mes_fim=Mes(mes_fim) if mes_fim else None,
        parcela_inicial=parcela_inicial,
        total_parcelas=total_parcelas,
        juros_altos=juros_altos,
    )


def pagamento(
    *,
    conta_id: str = "conta-1",
    mes_conta: str = "2026-11",
    valor: str = "10.00",
    data_pagamento: date = date(2026, 11, 10),
    id: str = "pagamento-1",
    banco_id: str | None = None,
) -> Pagamento:
    return Pagamento(
        id=id,
        usuario_id="usuario-1",
        conta_id=conta_id,
        mes_conta=Mes(mes_conta),
        valor_pago=dinheiro(valor),
        data_pagamento=data_pagamento,
        banco_id=banco_id,
    )


def ganho(
    *,
    id: str = "ganho-1",
    valor: str = "10.00",
    data: date = date(2026, 11, 10),
    recebido: bool = False,
) -> Ganho:
    return Ganho(
        id=id,
        usuario_id="usuario-1",
        nome="Trabalho",
        valor=dinheiro(valor),
        data=data,
        recebido=recebido,
    )


def banco(*, id: str = "banco-1", saldo: str = "100.00") -> Banco:
    return Banco(
        id=id,
        usuario_id="usuario-1",
        nome="Banco",
        saldo=dinheiro(saldo),
    )


def usuario(*, desde: str = "2026-11") -> Usuario:
    return Usuario(id="usuario-1", desde=Mes(desde))
