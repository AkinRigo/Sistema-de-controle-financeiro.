"""Tipos de valor imutáveis usados pelas regras de negócio."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from painel.domain.erros import ErroDeValidacao

_CENTAVO = Decimal("0.01")
_PADRAO_MES = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


@dataclass(frozen=True, slots=True, order=True)
class Mes:
    """Mês de calendário no formato AAAA-MM."""

    valor: str

    def __post_init__(self) -> None:
        if not isinstance(self.valor, str) or not _PADRAO_MES.fullmatch(self.valor):
            raise ErroDeValidacao("Mês deve estar no formato AAAA-MM.")

    def somar(self, quantidade: int) -> Mes:
        """Retorna o mês deslocado pela quantidade informada."""
        if isinstance(quantidade, bool) or not isinstance(quantidade, int):
            raise ErroDeValidacao("A quantidade de meses deve ser um inteiro.")
        ano, mes = (int(parte) for parte in self.valor.split("-"))
        indice = ano * 12 + mes - 1 + quantidade
        novo_ano, indice_mes = divmod(indice, 12)
        if novo_ano < 1:
            raise ErroDeValidacao("O mês calculado deve ter ano positivo.")
        return Mes(f"{novo_ano:04d}-{indice_mes + 1:02d}")

    def diferenca(self, outro: Mes) -> int:
        """Retorna quantos meses este mês está à frente de outro."""
        ano, mes = (int(parte) for parte in self.valor.split("-"))
        outro_ano, outro_mes = (int(parte) for parte in outro.valor.split("-"))
        return (ano - outro_ano) * 12 + mes - outro_mes

    def comparar(self, outro: Mes) -> int:
        """Compara cronologicamente: -1 antes, 0 igual, 1 depois."""
        return (self.valor > outro.valor) - (self.valor < outro.valor)


@dataclass(frozen=True, slots=True, order=True)
class Dinheiro:
    """Quantia decimal arredondada a centavos, sem conversão por ponto flutuante."""

    valor: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.valor, Decimal):
            raise TypeError("Dinheiro deve ser construído com Decimal, nunca float.")
        if not self.valor.is_finite():
            raise ErroDeValidacao("O valor monetário deve ser finito.")
        try:
            arredondado = self.valor.quantize(_CENTAVO, rounding=ROUND_HALF_UP)
        except InvalidOperation as erro:
            raise ErroDeValidacao("O valor monetário não pode ser representado.") from erro
        object.__setattr__(self, "valor", arredondado)

    @classmethod
    def zero(cls) -> Dinheiro:
        return cls(Decimal("0.00"))

    @classmethod
    def de(cls, valor: Decimal | str | int) -> Dinheiro:
        """Cria dinheiro a partir de Decimal, texto ou inteiro; float é recusado."""
        if isinstance(valor, (bool, float)):
            raise TypeError("Use Decimal, texto ou inteiro para representar dinheiro.")
        try:
            return cls(valor if isinstance(valor, Decimal) else Decimal(valor))
        except (InvalidOperation, ValueError) as erro:
            raise ErroDeValidacao("Valor monetário inválido.") from erro

    def __add__(self, outro: Dinheiro) -> Dinheiro:
        if not isinstance(outro, Dinheiro):
            return NotImplemented
        return Dinheiro(self.valor + outro.valor)

    def __sub__(self, outro: Dinheiro) -> Dinheiro:
        if not isinstance(outro, Dinheiro):
            return NotImplemented
        return Dinheiro(self.valor - outro.valor)

    def __mul__(self, fator: Decimal | int) -> Dinheiro:
        if isinstance(fator, (bool, float)):
            raise TypeError("Multiplique dinheiro apenas por Decimal ou inteiro.")
        if not isinstance(fator, (Decimal, int)):
            return NotImplemented
        return Dinheiro(self.valor * Decimal(fator))

    def __truediv__(self, divisor: Decimal | int) -> Dinheiro:
        if isinstance(divisor, (bool, float)):
            raise TypeError("Divida dinheiro apenas por Decimal ou inteiro.")
        if not isinstance(divisor, (Decimal, int)):
            return NotImplemented
        if divisor == 0:
            raise ZeroDivisionError("Não é possível dividir dinheiro por zero.")
        return Dinheiro(self.valor / Decimal(divisor))


def somar_dinheiro(valores: Iterable[Dinheiro]) -> Dinheiro:
    """Soma valores monetários sem recorrer a float."""
    total = Dinheiro.zero()
    for valor in valores:
        total += valor
    return total
