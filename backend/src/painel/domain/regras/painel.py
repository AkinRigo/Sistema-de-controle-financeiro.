"""Regras que antes ficavam na tela: cobertura, vencimento, itens por categoria, ganhos do mês."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from painel.domain.entidades import Conta, Ganho, Pagamento, ResumoMensal, TipoConta
from painel.domain.erros import ErroDeValidacao
from painel.domain.regras.categorias import categoria_da_conta
from painel.domain.regras.divida import calcular_divida_conta
from painel.domain.regras.ocorrencias import aparece_em, numero_parcela
from painel.domain.valores import Dinheiro, Mes


def mes_de(d: date) -> Mes:
    return Mes(f"{d.year:04d}-{d.month:02d}")


def cobertura_percentual(resumo: ResumoMensal) -> int:
    """Quanto (0–100%) do que falta pagar o dinheiro disponível e previsto cobre."""
    falta = resumo.falta_pagar.valor
    if falta <= 0:
        return 100
    entra = resumo.tenho.valor + resumo.vai_entrar.valor + resumo.corridas.valor
    pct = (entra / falta * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(max(Decimal(0), min(Decimal(100), pct)))


def dias_para_vencer(conta: Conta, mes: Mes, hoje: date, atrasada: bool) -> int | None:
    """Dias até o vencimento no mês corrente, se a conta tem dia (negativo: já venceu)."""
    if atrasada or not conta.dia_vencimento or mes != mes_de(hoje):
        return None
    return conta.dia_vencimento - hoje.day


DIAS_DE_AVISO = 5


def situacao_vencimento(dias: int | None) -> str | None:
    """ "venceu", "hoje", "em_breve" (até 5 dias) ou "no_prazo"; None sem data no mês."""
    if dias is None:
        return None
    if dias < 0:
        return "venceu"
    if dias == 0:
        return "hoje"
    return "em_breve" if dias <= DIAS_DE_AVISO else "no_prazo"


def numero_parcela_paga(conta: Conta, pagamento: Pagamento) -> int | None:
    return numero_parcela(conta, pagamento.mes_conta)


@dataclass(frozen=True, slots=True)
class ItemCategoria:
    conta: Conta
    valor: Dinheiro
    parcelas_restantes: int | None


def itens_por_categoria(
    mes: Mes, desde: Mes, contas: Iterable[Conta], pagamentos: Iterable[Pagamento]
) -> dict[str, list[ItemCategoria]]:
    """Ocorrências não pagas da competência, com o valor devido naquele mês."""
    pagamentos_lista = tuple(pagamentos)
    meses_pagos = {(pagamento.conta_id, pagamento.mes_conta) for pagamento in pagamentos_lista}
    itens: dict[str, list[ItemCategoria]] = {}
    for conta in contas:
        if not aparece_em(conta, mes) or (conta.id, mes) in meses_pagos:
            continue

        chave = categoria_da_conta(conta)
        restantes = None
        if conta.tipo is TipoConta.PARCELADA and conta.valor.valor > 0:
            devo = calcular_divida_conta(conta, desde, pagamentos_lista)
            restantes = int((devo.valor / conta.valor.valor).to_integral_value(ROUND_HALF_UP))
        itens.setdefault(chave, []).append(ItemCategoria(conta, conta.valor, restantes))
    return itens


@dataclass(frozen=True, slots=True)
class GanhoDoMes:
    ganho: Ganho
    atrasado: bool


def ganhos_do_mes(ganhos: Iterable[Ganho], mes: Mes) -> list[GanhoDoMes]:
    """Ganhos com data no mês, mais os não recebidos de meses anteriores (atrasados).
    Mais recentes primeiro."""
    lista = []
    for g in ganhos:
        m = mes_de(g.data)
        if m == mes:
            lista.append(GanhoDoMes(g, False))
        elif not g.recebido and m < mes:
            lista.append(GanhoDoMes(g, True))
    return sorted(lista, key=lambda x: (x.ganho.data, x.ganho.id), reverse=True)


def data_do_recebimento(data_prevista: date, mes_aberto: Mes, hoje: date) -> date:
    """Ao marcar "recebi": data futura ou de mês anterior ao aberto vira hoje."""
    if data_prevista > hoje or mes_de(data_prevista) < mes_aberto:
        return hoje
    return data_prevista


def inicio_pela_parcela(
    conta_atual: Conta | None, mes_referencia: Mes, parcela_no_mes: int, total: int
) -> tuple[Mes, int]:
    """Converte "parcela N de T em <mês>" em (mês de início, parcela inicial).

    Mantém o início atual quando possível, para não perder meses já cadastrados."""
    if not 1 <= parcela_no_mes <= total:
        raise ErroDeValidacao("Confira a parcela e o total de parcelas.")
    if (
        conta_atual is None
        or conta_atual.tipo is not TipoConta.PARCELADA
        or conta_atual.mes_inicio > mes_referencia
    ):
        return mes_referencia, parcela_no_mes
    inicial = parcela_no_mes - mes_referencia.diferenca(conta_atual.mes_inicio)
    if inicial < 1:
        return mes_referencia, parcela_no_mes
    return conta_atual.mes_inicio, inicial


def referencia_para_editar(conta: Conta, mes: Mes) -> tuple[Mes, int | None]:
    """Mês em que a tela edita a conta e o número da parcela nele.

    Única: o próprio mês da conta. Parcelada: o mês aberto, se houver parcela nele;
    senão o início (parcela inicial)."""
    if conta.tipo is TipoConta.UNICA or mes < conta.mes_inicio:
        return conta.mes_inicio, conta.parcela_inicial
    n = numero_parcela(conta, mes)
    if conta.tipo is TipoConta.PARCELADA and n is None:
        return conta.mes_inicio, conta.parcela_inicial
    return mes, n


def mes_fim_ao_parar(conta: Conta, a_partir_de: Mes) -> Mes:
    """Conta fixa deixa de aparecer a partir do mês informado."""
    if conta.tipo is not TipoConta.FIXA:
        raise ErroDeValidacao(
            "Só contas fixas podem parar de cobrar; as outras podem ser apagadas."
        )
    if a_partir_de <= conta.mes_inicio:
        raise ErroDeValidacao("Ela começa neste mês: para tirar, apague a conta.")
    return a_partir_de.somar(-1)
