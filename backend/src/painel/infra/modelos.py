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
    Text,
    UniqueConstraint,
    false,
    func,
    true,
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
    admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Desativado pelo admin: não entra mais, mas os dados ficam guardados.
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    ultimo_acesso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class RendaFixaModelo(Base):
    """Dinheiro que entra todo mês (salário, aluguel recebido...). Vira um ganho por mês."""

    __tablename__ = "rendas_fixas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    usuario_id: Mapped[str] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    nome: Mapped[str] = mapped_column(String(120))
    valor: Mapped[Decimal] = mapped_column(DINHEIRO)
    dia: Mapped[int] = mapped_column(Integer)
    mes_inicio: Mapped[str] = mapped_column(String(7))
    banco_id: Mapped[str | None] = mapped_column(
        ForeignKey("bancos.id", ondelete="SET NULL"), nullable=True
    )


class GanhoModelo(Base):
    __tablename__ = "ganhos"
    __table_args__ = (UniqueConstraint("renda_id", "mes_renda", name="uq_ganho_renda_mes"),)

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
    # Preenchidos quando o ganho foi gerado por uma renda fixa (um por mês).
    renda_id: Mapped[str | None] = mapped_column(
        ForeignKey("rendas_fixas.id", ondelete="SET NULL", name="fk_ganho_renda"),
        nullable=True,
        index=True,
    )
    mes_renda: Mapped[str | None] = mapped_column(String(7), nullable=True)


class ConviteModelo(Base):
    """Convite enviado pelo admin. Vira usuário quando a pessoa cria a senha."""

    __tablename__ = "convites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), index=True)
    # pendente | aceito | cancelado
    status: Mapped[str] = mapped_column(String(12), default="pendente")
    convidado_por: Mapped[str | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    enviado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    aceito_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EventoModelo(Base):
    """Log do sistema: acessos, erros e e-mails, para a aba Logs do admin."""

    __tablename__ = "eventos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    nivel: Mapped[str] = mapped_column(String(8))  # erro | aviso | info
    tipo: Mapped[str] = mapped_column(String(10))  # acesso | sistema | email
    acao: Mapped[str] = mapped_column(String(40), index=True)  # ex.: login_ok, login_falhou
    mensagem: Mapped[str] = mapped_column(String(300))
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    rota: Mapped[str | None] = mapped_column(String(200), nullable=True)
    codigo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requisicao: Mapped[str | None] = mapped_column(String(40), nullable=True)
    detalhe: Mapped[str | None] = mapped_column(Text, nullable=True)
