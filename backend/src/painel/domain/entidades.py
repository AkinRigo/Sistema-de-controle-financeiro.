"""Entidades puras do domínio, sem dependências de banco ou HTTP."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from painel.domain.erros import ErroDeValidacao
from painel.domain.valores import Dinheiro, Mes


class TipoConta(StrEnum):
    FIXA = "fixa"
    UNICA = "unica"
    PARCELADA = "parcelada"


@dataclass(frozen=True, slots=True)
class Usuario:
    id: str
    desde: Mes


@dataclass(frozen=True, slots=True)
class Banco:
    id: str
    usuario_id: str
    nome: str
    saldo: Dinheiro


@dataclass(frozen=True, slots=True)
class Conta:
    id: str
    usuario_id: str
    nome: str
    valor: Dinheiro
    tipo: TipoConta
    mes_inicio: Mes
    categoria: str = ""
    credor: str | None = None
    dia_vencimento: int = 0
    mes_fim: Mes | None = None
    parcela_inicial: int | None = None
    total_parcelas: int | None = None
    juros_altos: bool = False

    def __post_init__(self) -> None:
        if not 0 <= self.dia_vencimento <= 31:
            raise ErroDeValidacao("Dia de vencimento deve estar entre 0 e 31.")
        if self.tipo is TipoConta.FIXA:
            if self.mes_fim is not None and self.mes_fim < self.mes_inicio:
                raise ErroDeValidacao("Mês final da conta fixa não pode anteceder o início.")
            if self.parcela_inicial is not None or self.total_parcelas is not None:
                raise ErroDeValidacao("Conta fixa não pode ter dados de parcelamento.")
        elif self.tipo is TipoConta.PARCELADA:
            if (
                self.parcela_inicial is None
                or self.total_parcelas is None
                or self.parcela_inicial < 1
                or self.total_parcelas < self.parcela_inicial
            ):
                raise ErroDeValidacao("Conta parcelada exige números de parcela válidos.")
            if self.mes_fim is not None:
                raise ErroDeValidacao("Conta parcelada não usa mês final.")
        elif (
            self.mes_fim is not None
            or self.parcela_inicial is not None
            or self.total_parcelas is not None
        ):
            raise ErroDeValidacao("Conta única não aceita campos de conta fixa ou parcelada.")


@dataclass(frozen=True, slots=True)
class Pagamento:
    id: str
    usuario_id: str
    conta_id: str
    mes_conta: Mes
    valor_pago: Dinheiro
    data_pagamento: date
    banco_id: str | None = None


@dataclass(frozen=True, slots=True)
class Ganho:
    id: str
    usuario_id: str
    nome: str
    valor: Dinheiro
    data: date
    recebido: bool
    banco_id: str | None = None


@dataclass(frozen=True, slots=True)
class Corridas:
    por_semana: Dinheiro
    por_fim_de_semana: Dinheiro
    contar_na_previsao: bool


@dataclass(frozen=True, slots=True)
class ContaAberta:
    conta: Conta
    mes_origem: Mes
    atrasada: bool
    numero_parcela: int | None = None


@dataclass(frozen=True, slots=True)
class ResumoMensal:
    mes: Mes
    tenho: Dinheiro
    vai_entrar: Dinheiro
    recebido: Dinheiro
    corridas: Dinheiro
    abertas: tuple[ContaAberta, ...]
    falta_pagar: Dinheiro
    pagas: tuple[Pagamento, ...]
    ja_pago: Dinheiro
    sobra: Dinheiro
