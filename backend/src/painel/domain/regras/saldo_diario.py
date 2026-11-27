"""Saldo dia a dia do mês, para o gráfico de barras.

- Dias até hoje: o saldo de hoje nos bancos, desfazendo o que entrou e saiu depois daquele dia.
- Dias depois de hoje: o saldo de hoje mais os ganhos previstos e menos as contas em aberto,
  cada um na sua data. O que já está atrasado entra no dia seguinte a hoje.
- O último dia fecha em tenho + vai entrar − falta pagar (corridas ficam de fora).
"""

from calendar import monthrange
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from painel.domain.entidades import Conta, Ganho, Pagamento, ResumoMensal
from painel.domain.valores import Dinheiro, Mes, somar_dinheiro


@dataclass(frozen=True, slots=True)
class Movimento:
    nome: str
    valor: Dinheiro  # positivo entra, negativo sai
    previsto: bool


@dataclass(frozen=True, slots=True)
class DiaDeSaldo:
    dia: int
    saldo: Dinheiro
    previsao: bool
    movimentos: tuple[Movimento, ...]


@dataclass(frozen=True, slots=True)
class SaldoDiario:
    dias: tuple[DiaDeSaldo, ...]
    hoje: int | None  # dia de hoje, se hoje cai neste mês
    menor: DiaDeSaldo | None  # menor saldo previsto (de hoje em diante)


def _negativo(valor: Dinheiro) -> Dinheiro:
    return Dinheiro.zero() - valor


def saldo_dia_a_dia(
    resumo: ResumoMensal,
    hoje: date,
    contas: Iterable[Conta],
    pagamentos: Iterable[Pagamento],
    ganhos: Iterable[Ganho],
) -> SaldoDiario:
    ano, mes = (int(p) for p in resumo.mes.valor.split("-"))
    ultimo = monthrange(ano, mes)[1]
    primeiro_dia, ultimo_dia = date(ano, mes, 1), date(ano, mes, ultimo)
    nomes = {c.id: c.nome for c in contas}
    ganhos = list(ganhos)

    # o que já aconteceu (até hoje): ganhos recebidos e pagamentos feitos
    feitos: list[tuple[date, Movimento]] = [
        (g.data, Movimento(g.nome, g.valor, False)) for g in ganhos if g.recebido and g.data <= hoje
    ] + [
        (
            p.data_pagamento,
            Movimento(nomes.get(p.conta_id, "Conta"), _negativo(p.valor_pago), False),
        )
        for p in pagamentos
        if p.data_pagamento <= hoje
    ]

    # o que está previsto: mesmo critério do resumo (vai entrar e falta pagar)
    amanha = max(hoje + timedelta(days=1), primeiro_dia)

    def quando(alvo: date) -> date:
        return min(max(alvo, amanha), ultimo_dia)

    previstos: list[tuple[date, Movimento]] = [
        (quando(g.data), Movimento(g.nome, g.valor, True))
        for g in ganhos
        if not g.recebido and Mes(g.data.strftime("%Y-%m")) <= resumo.mes
    ]
    for a in resumo.abertas:
        dia = a.conta.dia_vencimento
        alvo = primeiro_dia if a.atrasada or not dia else date(ano, mes, min(dia, ultimo))
        previstos.append((quando(alvo), Movimento(a.conta.nome, _negativo(a.conta.valor), True)))

    if ultimo_dia < hoje:  # mês que já passou: só o que aconteceu
        previstos = []

    dias: list[DiaDeSaldo] = []
    for n in range(1, ultimo + 1):
        d = date(ano, mes, n)
        if d <= hoje:
            depois = somar_dinheiro(m.valor for quando_, m in feitos if d < quando_ <= hoje)
            saldo = resumo.tenho - depois
            movs = [m for quando_, m in feitos if quando_ == d]
            # se hoje é o último dia do mês, o que falta entra hoje mesmo
            movs_prev = [m for quando_, m in previstos if quando_ == d]
            saldo += somar_dinheiro(m.valor for m in movs_prev)
            previsao = bool(movs_prev)
        else:
            saldo = resumo.tenho + somar_dinheiro(
                m.valor for quando_, m in previstos if quando_ <= d
            )
            movs = [m for quando_, m in previstos if quando_ == d]
            movs_prev = []
            previsao = True
        dias.append(DiaDeSaldo(n, saldo, previsao, tuple(movs + movs_prev)))

    futuros = [x for x in dias if date(ano, mes, x.dia) >= hoje]
    menor = min(futuros, key=lambda x: (x.saldo.valor, x.dia)) if futuros else None
    dia_hoje = hoje.day if primeiro_dia <= hoje <= ultimo_dia else None
    return SaldoDiario(tuple(dias), dia_hoje, menor)
