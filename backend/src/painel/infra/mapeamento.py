"""Conversão entre linhas do banco e entidades do domínio."""

from painel.domain.entidades import Banco, Conta, Ganho, Pagamento, TipoConta, Usuario
from painel.domain.valores import Dinheiro, Mes
from painel.infra.modelos import (
    BancoModelo,
    ContaModelo,
    GanhoModelo,
    PagamentoModelo,
    UsuarioModelo,
)


def usuario(m: UsuarioModelo) -> Usuario:
    return Usuario(id=m.id, desde=Mes(m.desde))


def banco(m: BancoModelo) -> Banco:
    return Banco(id=m.id, usuario_id=m.usuario_id, nome=m.nome, saldo=Dinheiro.de(m.saldo))


def conta(m: ContaModelo) -> Conta:
    return Conta(
        id=m.id,
        usuario_id=m.usuario_id,
        nome=m.nome,
        valor=Dinheiro.de(m.valor),
        tipo=TipoConta(m.tipo),
        mes_inicio=Mes(m.mes_inicio),
        categoria=m.categoria or "",
        credor=m.credor,
        dia_vencimento=m.dia_vencimento,
        mes_fim=Mes(m.mes_fim) if m.mes_fim else None,
        parcela_inicial=m.parcela_inicial,
        total_parcelas=m.total_parcelas,
        juros_altos=m.juros_altos,
    )


def pagamento(m: PagamentoModelo) -> Pagamento:
    return Pagamento(
        id=m.id,
        usuario_id=m.usuario_id,
        conta_id=m.conta_id,
        mes_conta=Mes(m.mes_conta),
        valor_pago=Dinheiro.de(m.valor_pago),
        data_pagamento=m.data_pagamento,
        banco_id=m.banco_id,
    )


def ganho(m: GanhoModelo) -> Ganho:
    return Ganho(
        id=m.id,
        usuario_id=m.usuario_id,
        nome=m.nome,
        valor=Dinheiro.de(m.valor),
        data=m.data,
        recebido=m.recebido,
        banco_id=m.banco_id,
    )
