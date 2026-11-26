"""Resumo financeiro mensal calculado a partir de entidades do domínio."""

from collections.abc import Iterable
from datetime import date

from painel.domain.entidades import (
    Banco,
    Conta,
    Corridas,
    Ganho,
    Pagamento,
    ResumoMensal,
    Usuario,
)
from painel.domain.regras.corridas import estimar_corridas
from painel.domain.regras.ocorrencias import obter_abertas
from painel.domain.valores import Dinheiro, Mes, somar_dinheiro


def calcular_resumo(
    mes: Mes,
    usuario: Usuario,
    bancos: Iterable[Banco],
    contas: Iterable[Conta],
    pagamentos: Iterable[Pagamento],
    ganhos: Iterable[Ganho],
    hoje: date,
    por_semana: Dinheiro,
    por_fim_de_semana: Dinheiro,
    contar_na_previsao: bool,
) -> ResumoMensal:
    """Calcula entradas, saídas previstas e saldo projetado do mês."""
    bancos_lista = tuple(bancos)
    contas_lista = tuple(contas)
    pagamentos_lista = tuple(pagamentos)
    ganhos_lista = tuple(ganhos)

    abertas = obter_abertas(contas_lista, pagamentos_lista, mes, usuario.desde)
    pagas = tuple(
        sorted(
            (
                pagamento
                for pagamento in pagamentos_lista
                if pagamento.mes_conta == mes
                or pagamento.data_pagamento.strftime("%Y-%m") == mes.valor
            ),
            key=lambda pagamento: (pagamento.data_pagamento, pagamento.id),
        )
    )
    tenho = somar_dinheiro(banco.saldo for banco in bancos_lista)
    vai_entrar = somar_dinheiro(
        ganho.valor
        for ganho in ganhos_lista
        if not ganho.recebido and ganho.data.strftime("%Y-%m") <= mes.valor
    )
    recebido = somar_dinheiro(
        ganho.valor
        for ganho in ganhos_lista
        if ganho.recebido and ganho.data.strftime("%Y-%m") == mes.valor
    )
    corridas_estimadas = estimar_corridas(
        Corridas(por_semana, por_fim_de_semana, contar_na_previsao), mes, hoje
    )
    falta_pagar = somar_dinheiro(aberta.conta.valor for aberta in abertas)
    ja_pago = somar_dinheiro(pagamento.valor_pago for pagamento in pagas)
    sobra = tenho + vai_entrar + corridas_estimadas - falta_pagar

    return ResumoMensal(
        mes=mes,
        tenho=tenho,
        vai_entrar=vai_entrar,
        recebido=recebido,
        corridas=corridas_estimadas,
        abertas=abertas,
        falta_pagar=falta_pagar,
        pagas=pagas,
        ja_pago=ja_pago,
        sobra=sobra,
    )
