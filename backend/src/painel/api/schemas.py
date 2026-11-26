"""Schemas de entrada e saída da API. Dinheiro trafega como texto decimal."""

import re
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
)

from painel.domain.entidades import TipoConta
from painel.domain.valores import Mes

_PADRAO_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validar_mes(valor: str) -> str:
    return Mes(valor).valor


def _sem_float(valor: object) -> object:
    if isinstance(valor, float):
        # JSON numérico chega como float; convertemos pelo texto para não herdar erro binário.
        return Decimal(repr(valor))
    return valor


DinheiroEntrada = Annotated[
    Decimal,
    Field(max_digits=14, decimal_places=2),
]
DinheiroSaida = Annotated[Decimal, PlainSerializer(lambda v: f"{v:.2f}", return_type=str)]
MesTexto = Annotated[str, AfterValidator(_validar_mes)]


class Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _ComDinheiro(Entrada):
    @field_validator("*", mode="before")
    @classmethod
    def _converter_float(cls, valor: object) -> object:
        return _sem_float(valor)


# ---------- autenticação ----------


class CadastroEntrada(Entrada):
    nome: str = Field(min_length=1, max_length=120)
    email: str = Field(max_length=254)
    senha: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, valor: str) -> str:
        valor = valor.strip().lower()
        if not _PADRAO_EMAIL.fullmatch(valor):
            raise ValueError("E-mail inválido.")
        return valor


class LoginEntrada(Entrada):
    email: str
    senha: str

    @field_validator("email")
    @classmethod
    def _email(cls, valor: str) -> str:
        return valor.strip().lower()


class EsqueciSenhaEntrada(Entrada):
    email: str

    @field_validator("email")
    @classmethod
    def _email(cls, valor: str) -> str:
        return valor.strip().lower()


class ConfirmarEmailEntrada(Entrada):
    token: str


class RedefinirSenhaEntrada(Entrada):
    token: str
    senha: str = Field(min_length=8, max_length=128)


class UsuarioSaida(BaseModel):
    id: str
    nome: str
    email: str
    desde: str
    admin: bool = False


class TokenSaida(BaseModel):
    token: str
    tipo: str = "bearer"
    usuario: UsuarioSaida


# ---------- corridas ----------


class CorridasEntrada(_ComDinheiro):
    por_semana: DinheiroEntrada = Field(ge=0)
    por_fim_de_semana: DinheiroEntrada = Field(ge=0)
    contar_na_previsao: bool


class CorridasSaida(BaseModel):
    por_semana: DinheiroSaida
    por_fim_de_semana: DinheiroSaida
    contar_na_previsao: bool
    # estimativa para o mês pedido em ?mes= (independe de contar na previsão)
    estimativa_mes: DinheiroSaida | None = None


# ---------- bancos ----------


class BancoEntrada(_ComDinheiro):
    nome: str = Field(min_length=1, max_length=120)
    saldo: DinheiroEntrada


class BancoSaida(BaseModel):
    id: str
    nome: str
    saldo: DinheiroSaida


# ---------- contas ----------


class ContaEntrada(_ComDinheiro):
    nome: str = Field(min_length=1, max_length=120)
    valor: DinheiroEntrada = Field(ge=0)
    tipo: TipoConta
    mes_inicio: MesTexto
    categoria: str = ""
    credor: str | None = Field(default=None, max_length=120)
    dia_vencimento: int = Field(default=0, ge=0, le=31)
    mes_fim: MesTexto | None = None
    parcela_inicial: int | None = None
    total_parcelas: int | None = None
    juros_altos: bool = False
    incerto: bool = False
    # Editar pelo mês aberto: o backend converte "parcela N em <mês>" no início certo,
    # e uma conta que vira fixa passa a começar no mês aberto.
    mes_referencia: MesTexto | None = None
    parcela_no_mes: int | None = Field(default=None, ge=1)


class PararContaEntrada(Entrada):
    a_partir_de: MesTexto


class ContaSaida(BaseModel):
    id: str
    nome: str
    valor: DinheiroSaida
    tipo: TipoConta
    mes_inicio: str
    categoria: str
    categoria_efetiva: str
    credor: str | None
    dia_vencimento: int
    mes_fim: str | None
    parcela_inicial: int | None
    total_parcelas: int | None
    juros_altos: bool
    incerto: bool
    ainda_devo: DinheiroSaida


# ---------- pagamentos ----------


class PagamentoEntrada(_ComDinheiro):
    conta_id: str
    mes_conta: MesTexto
    valor_pago: DinheiroEntrada | None = Field(default=None, ge=0)
    data_pagamento: date | None = None
    banco_id: str | None = None


class PagamentoSaida(BaseModel):
    id: str
    conta_id: str
    mes_conta: str
    valor_pago: DinheiroSaida
    data_pagamento: date
    banco_id: str | None
    numero_parcela: int | None = None


# ---------- ganhos ----------


class GanhoEntrada(_ComDinheiro):
    nome: str = Field(default="", max_length=120, validate_default=True)
    valor: DinheiroEntrada = Field(gt=0)
    data: date
    recebido: bool = False
    banco_id: str | None = None

    @field_validator("nome")
    @classmethod
    def _nome_padrao(cls, valor: str) -> str:
        return valor.strip() or "Ganho"


class GanhoSaida(BaseModel):
    id: str
    nome: str
    valor: DinheiroSaida
    data: date
    recebido: bool
    banco_id: str | None
    renda_id: str | None = None


class GanhoDoMesSaida(GanhoSaida):
    atrasado: bool


class ReceberEntrada(_ComDinheiro):
    valor: DinheiroEntrada = Field(gt=0)
    banco_id: str | None = None
    mes_aberto: MesTexto


# ---------- renda fixa ----------


class RendaEntrada(_ComDinheiro):
    nome: str = Field(min_length=1, max_length=120)
    valor: DinheiroEntrada = Field(gt=0)
    dia: int = Field(ge=1, le=31)
    banco_id: str | None = None
    mes_inicio: MesTexto | None = None


class RendaSaida(BaseModel):
    id: str
    nome: str
    valor: DinheiroSaida
    dia: int
    mes_inicio: str
    banco_id: str | None


# ---------- relatórios ----------


class ContaAbertaSaida(BaseModel):
    conta_id: str
    nome: str
    valor: DinheiroSaida
    categoria: str
    mes_origem: str
    atrasada: bool
    numero_parcela: int | None
    total_parcelas: int | None
    dia_vencimento: int
    juros_altos: bool
    vence_em_dias: int | None = None
    situacao_vencimento: str | None = None


class ResumoSaida(BaseModel):
    mes: str
    tenho: DinheiroSaida
    vai_entrar: DinheiroSaida
    recebido: DinheiroSaida
    corridas: DinheiroSaida
    falta_pagar: DinheiroSaida
    ja_pago: DinheiroSaida
    sobra: DinheiroSaida
    abertas: list[ContaAbertaSaida]
    pagas: list[PagamentoSaida]
    cobertura: int
    divida_total: DinheiroSaida


class ItemCategoriaSaida(BaseModel):
    conta_id: str
    nome: str
    credor: str | None
    tipo: TipoConta
    valor: DinheiroSaida
    valor_parcela: DinheiroSaida
    parcelas_restantes: int | None
    total_parcelas: int | None
    # mês em que a tela edita esta conta e o número da parcela nele
    mes_referencia: str
    parcela_no_mes: int | None


class CategoriaSaida(BaseModel):
    chave: str
    nome: str
    falta_pagar: DinheiroSaida
    ja_pago: DinheiroSaida
    fixas_por_mes: DinheiroSaida
    ainda_devo: DinheiroSaida
    itens: list[ItemCategoriaSaida] = []


class DividaSaida(BaseModel):
    total: DinheiroSaida
