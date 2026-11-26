"""Tabelas do banco de dados (ORM). Valores monetários usam NUMERIC, nunca float."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DINHEIRO = Numeric(14, 2, asdecimal=True)


class Base(DeclarativeBase):
    pass


class UsuarioModelo(Base):
    __tablename__ = "usuarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(120))
    senha_hash: Mapped[str] = mapped_column(String(255))
    desde: Mapped[str] = mapped_column(String(7))
    corridas_por_semana: Mapped[Decimal] = mapped_column(DINHEIRO, default=Decimal("0"))
    corridas_por_fim_de_semana: Mapped[Decimal] = mapped_column(DINHEIRO, default=Decimal("0"))
    contar_corridas: Mapped[bool] = mapped_column(Boolean, default=False)
    email_confirmado: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BancoModelo(Base):
    __tablename__ = "bancos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    usuario_id: Mapped[str] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    nome: Mapped[str] = mapped_column(String(120))
    saldo: Mapped[Decimal] = mapped_column(DINHEIRO)


class ContaModelo(Base):
    __tablename__ = "contas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    usuario_id: Mapped[str] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    nome: Mapped[str] = mapped_column(String(120))
    valor: Mapped[Decimal] = mapped_column(DINHEIRO)
    tipo: Mapped[str] = mapped_column(String(20))
    mes_inicio: Mapped[str] = mapped_column(String(7))
    categoria: Mapped[str] = mapped_column(String(30), default="")
    credor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dia_vencimento: Mapped[int] = mapped_column(Integer, default=0)
    mes_fim: Mapped[str | None] = mapped_column(String(7), nullable=True)
    parcela_inicial: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_parcelas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    juros_altos: Mapped[bool] = mapped_column(Boolean, default=False)
    incerto: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


class PagamentoModelo(Base):
    __tablename__ = "pagamentos"
    __table_args__ = (UniqueConstraint("conta_id", "mes_conta", name="uq_pagamento_conta_mes"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    usuario_id: Mapped[str] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    conta_id: Mapped[str] = mapped_column(ForeignKey("contas.id", ondelete="CASCADE"), index=True)
    mes_conta: Mapped[str] = mapped_column(String(7))
    valor_pago: Mapped[Decimal] = mapped_column(DINHEIRO)
    data_pagamento: Mapped[date] = mapped_column(Date)
    banco_id: Mapped[str | None] = mapped_column(
        ForeignKey("bancos.id", ondelete="SET NULL"), nullable=True
    )


class GanhoModelo(Base):
    __tablename__ = "ganhos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    usuario_id: Mapped[str] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    nome: Mapped[str] = mapped_column(String(120))
    valor: Mapped[Decimal] = mapped_column(DINHEIRO)
    data: Mapped[date] = mapped_column(Date)
    recebido: Mapped[bool] = mapped_column(Boolean, default=False)
    banco_id: Mapped[str | None] = mapped_column(
        ForeignKey("bancos.id", ondelete="SET NULL"), nullable=True
    )
