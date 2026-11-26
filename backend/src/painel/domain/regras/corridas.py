"""Estimativa de renda de corridas de moto."""

from datetime import date, timedelta
from decimal import Decimal

from painel.domain.entidades import Corridas
from painel.domain.valores import Dinheiro, Mes


def estimar_corridas(corridas: Corridas, mes: Mes, hoje: date) -> Dinheiro:
    """Estima ganhos até o fim do mês, contando o dia atual inclusive."""
    mes_atual = Mes(f"{hoje.year:04d}-{hoje.month:02d}")
    if not corridas.contar_na_previsao or mes < mes_atual:
        return Dinheiro.zero()

    inicio = hoje if mes == mes_atual else date(int(mes.valor[:4]), int(mes.valor[5:]), 1)

    ano, numero_mes = (int(parte) for parte in mes.valor.split("-"))
    proximo_mes = Mes(f"{ano:04d}-{numero_mes:02d}").somar(1)
    fim = date(int(proximo_mes.valor[:4]), int(proximo_mes.valor[5:]), 1) - timedelta(days=1)
    dias_restantes = (fim - inicio).days + 1

    sabados = 0
    dia = inicio
    while dia <= fim:
        if dia.weekday() == 5:
            sabados += 1
        dia += timedelta(days=1)

    estimativa = corridas.por_semana.valor * Decimal(dias_restantes) / Decimal(
        7
    ) + corridas.por_fim_de_semana.valor * Decimal(sabados)
    return Dinheiro(estimativa)
