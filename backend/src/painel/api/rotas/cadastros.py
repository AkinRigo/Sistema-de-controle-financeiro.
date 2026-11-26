"""CRUD de bancos, contas, ganhos, pagamentos e configuração de corridas.

Saldos de banco são ajustados automaticamente: um pagamento com banco debita o valor,
e um ganho recebido com banco credita o valor. Editar um ganho ou desfazer um pagamento
desfaz o efeito anterior; excluir uma conta mantém os saldos (o dinheiro pago já saiu do banco).
"""

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from painel.api.deps import HojeDep, SessaoDep, UsuarioDep, nao_encontrado
from painel.api.rotas.rendas import garantir_rendas
from painel.api.schemas import (
    BancoEntrada,
    BancoSaida,
    ContaEntrada,
    ContaSaida,
    CorridasEntrada,
    CorridasSaida,
    GanhoEntrada,
    GanhoSaida,
    MesTexto,
    PagamentoEntrada,
    PagamentoSaida,
)
from painel.domain.entidades import Conta
from painel.domain.erros import ErroDeValidacao
from painel.domain.regras.categorias import categoria_da_conta
from painel.domain.regras.divida import calcular_divida_conta
from painel.domain.regras.ocorrencias import aparece_em
from painel.domain.valores import Dinheiro, Mes
from painel.infra import mapeamento
from painel.infra.modelos import (
    BancoModelo,
    ContaModelo,
    GanhoModelo,
    PagamentoModelo,
    UsuarioModelo,
)

router = APIRouter()


def _novo_id() -> str:
    return str(uuid.uuid4())


def _do_usuario(sessao: Session, modelo, id_: str, usuario: UsuarioModelo, recurso: str):
    registro = sessao.get(modelo, id_)
    if registro is None or registro.usuario_id != usuario.id:
        raise nao_encontrado(recurso)
    return registro


def _banco_opcional(
    sessao: Session, banco_id: str | None, usuario: UsuarioModelo
) -> BancoModelo | None:
    if banco_id is None:
        return None
    return _do_usuario(sessao, BancoModelo, banco_id, usuario, "Banco")


def _ajustar_saldo(sessao: Session, banco_id: str | None, delta: Decimal) -> None:
    if banco_id is None or delta == 0:
        return
    banco = sessao.get(BancoModelo, banco_id)
    if banco is not None:
        banco.saldo = Dinheiro.de(banco.saldo).valor + delta


def _sem_conteudo() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------- corridas ----------------


@router.get("/configuracoes/corridas", response_model=CorridasSaida, tags=["configurações"])
def obter_corridas(usuario: UsuarioDep) -> CorridasSaida:
    return CorridasSaida(
        por_semana=usuario.corridas_por_semana,
        por_fim_de_semana=usuario.corridas_por_fim_de_semana,
        contar_na_previsao=usuario.contar_corridas,
    )


@router.put("/configuracoes/corridas", response_model=CorridasSaida, tags=["configurações"])
def salvar_corridas(dados: CorridasEntrada, usuario: UsuarioDep) -> CorridasSaida:
    usuario.corridas_por_semana = Dinheiro.de(dados.por_semana).valor
    usuario.corridas_por_fim_de_semana = Dinheiro.de(dados.por_fim_de_semana).valor
    usuario.contar_corridas = dados.contar_na_previsao
    return obter_corridas(usuario)


# ---------------- bancos ----------------


def _banco_saida(m: BancoModelo) -> BancoSaida:
    return BancoSaida(id=m.id, nome=m.nome, saldo=Dinheiro.de(m.saldo).valor)


@router.get("/bancos", response_model=list[BancoSaida], tags=["bancos"])
def listar_bancos(sessao: SessaoDep, usuario: UsuarioDep) -> list[BancoSaida]:
    bancos = sessao.scalars(
        select(BancoModelo).where(BancoModelo.usuario_id == usuario.id).order_by(BancoModelo.nome)
    )
    return [_banco_saida(b) for b in bancos]


@router.post(
    "/bancos", response_model=BancoSaida, status_code=status.HTTP_201_CREATED, tags=["bancos"]
)
def criar_banco(dados: BancoEntrada, sessao: SessaoDep, usuario: UsuarioDep) -> BancoSaida:
    banco = BancoModelo(
        id=_novo_id(),
        usuario_id=usuario.id,
        nome=dados.nome,
        saldo=Dinheiro.de(dados.saldo).valor,
    )
    sessao.add(banco)
    return _banco_saida(banco)


@router.put("/bancos/{banco_id}", response_model=BancoSaida, tags=["bancos"])
def editar_banco(
    banco_id: str, dados: BancoEntrada, sessao: SessaoDep, usuario: UsuarioDep
) -> BancoSaida:
    banco = _do_usuario(sessao, BancoModelo, banco_id, usuario, "Banco")
    banco.nome = dados.nome
    banco.saldo = Dinheiro.de(dados.saldo).valor
    return _banco_saida(banco)


@router.delete("/bancos/{banco_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["bancos"])
def excluir_banco(banco_id: str, sessao: SessaoDep, usuario: UsuarioDep) -> Response:
    sessao.delete(_do_usuario(sessao, BancoModelo, banco_id, usuario, "Banco"))
    return _sem_conteudo()


# ---------------- contas ----------------


def _pagamentos_do_usuario(sessao: Session, usuario: UsuarioModelo):
    return [
        mapeamento.pagamento(p)
        for p in sessao.scalars(
            select(PagamentoModelo).where(PagamentoModelo.usuario_id == usuario.id)
        )
    ]


def _conta_saida(conta: Conta, incerto: bool, desde: Mes, pagamentos) -> ContaSaida:
    return ContaSaida(
        id=conta.id,
        nome=conta.nome,
        valor=conta.valor.valor,
        tipo=conta.tipo,
        mes_inicio=conta.mes_inicio.valor,
        categoria=conta.categoria,
        categoria_efetiva=categoria_da_conta(conta),
        credor=conta.credor,
        dia_vencimento=conta.dia_vencimento,
        mes_fim=conta.mes_fim.valor if conta.mes_fim else None,
        parcela_inicial=conta.parcela_inicial,
        total_parcelas=conta.total_parcelas,
        juros_altos=conta.juros_altos,
        incerto=incerto,
        ainda_devo=calcular_divida_conta(conta, desde, pagamentos).valor,
    )


def _aplicar_conta(modelo: ContaModelo, dados: ContaEntrada, usuario_id: str) -> Conta:
    """Valida pelo domínio antes de gravar; levanta ErroDeValidacao se inválido."""
    conta = Conta(
        id=modelo.id,
        usuario_id=usuario_id,
        nome=dados.nome,
        valor=Dinheiro.de(dados.valor),
        tipo=dados.tipo,
        mes_inicio=Mes(dados.mes_inicio),
        categoria=dados.categoria,
        credor=dados.credor or None,
        dia_vencimento=dados.dia_vencimento,
        mes_fim=Mes(dados.mes_fim) if dados.mes_fim else None,
        parcela_inicial=dados.parcela_inicial,
        total_parcelas=dados.total_parcelas,
        juros_altos=dados.juros_altos,
    )
    categoria_da_conta(conta)  # recusa categoria desconhecida
    modelo.usuario_id = usuario_id
    modelo.nome = conta.nome
    modelo.valor = conta.valor.valor
    modelo.tipo = conta.tipo.value
    modelo.mes_inicio = conta.mes_inicio.valor
    modelo.categoria = conta.categoria
    modelo.credor = conta.credor
    modelo.dia_vencimento = conta.dia_vencimento
    modelo.mes_fim = dados.mes_fim
    modelo.parcela_inicial = conta.parcela_inicial
    modelo.total_parcelas = conta.total_parcelas
    modelo.juros_altos = conta.juros_altos
    modelo.incerto = dados.incerto
    return conta


def _recuar_desde(usuario: UsuarioModelo, conta: Conta) -> None:
    """Conta lançada antes do início do painel passa a contar como atrasada (igual ao protótipo)."""
    if conta.mes_inicio < Mes(usuario.desde):
        usuario.desde = conta.mes_inicio.valor


@router.get("/contas", response_model=list[ContaSaida], tags=["contas"])
def listar_contas(sessao: SessaoDep, usuario: UsuarioDep) -> list[ContaSaida]:
    desde = Mes(usuario.desde)
    pagamentos = _pagamentos_do_usuario(sessao, usuario)
    contas = sessao.scalars(
        select(ContaModelo).where(ContaModelo.usuario_id == usuario.id).order_by(ContaModelo.nome)
    )
    return [_conta_saida(mapeamento.conta(c), c.incerto, desde, pagamentos) for c in contas]


@router.post(
    "/contas", response_model=ContaSaida, status_code=status.HTTP_201_CREATED, tags=["contas"]
)
def criar_conta(dados: ContaEntrada, sessao: SessaoDep, usuario: UsuarioDep) -> ContaSaida:
    modelo = ContaModelo(id=_novo_id())
    conta = _aplicar_conta(modelo, dados, usuario.id)
    _recuar_desde(usuario, conta)
    sessao.add(modelo)
    return _conta_saida(conta, modelo.incerto, Mes(usuario.desde), [])


@router.put("/contas/{conta_id}", response_model=ContaSaida, tags=["contas"])
def editar_conta(
    conta_id: str, dados: ContaEntrada, sessao: SessaoDep, usuario: UsuarioDep
) -> ContaSaida:
    modelo = _do_usuario(sessao, ContaModelo, conta_id, usuario, "Conta")
    conta = _aplicar_conta(modelo, dados, usuario.id)
    _recuar_desde(usuario, conta)
    return _conta_saida(
        conta, modelo.incerto, Mes(usuario.desde), _pagamentos_do_usuario(sessao, usuario)
    )


@router.delete("/contas/{conta_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["contas"])
def excluir_conta(conta_id: str, sessao: SessaoDep, usuario: UsuarioDep) -> Response:
    """Apaga a conta e seu histórico. Os saldos não mudam: o dinheiro pago já saiu do banco."""
    modelo = _do_usuario(sessao, ContaModelo, conta_id, usuario, "Conta")
    sessao.execute(delete(PagamentoModelo).where(PagamentoModelo.conta_id == modelo.id))
    sessao.delete(modelo)
    return _sem_conteudo()


# ---------------- pagamentos ----------------


def _pagamento_saida(m: PagamentoModelo) -> PagamentoSaida:
    p = mapeamento.pagamento(m)
    return PagamentoSaida(
        id=p.id,
        conta_id=p.conta_id,
        mes_conta=p.mes_conta.valor,
        valor_pago=p.valor_pago.valor,
        data_pagamento=p.data_pagamento,
        banco_id=p.banco_id,
    )


@router.get("/pagamentos", response_model=list[PagamentoSaida], tags=["pagamentos"])
def listar_pagamentos(
    sessao: SessaoDep, usuario: UsuarioDep, mes: Annotated[MesTexto | None, Query()] = None
) -> list[PagamentoSaida]:
    consulta = select(PagamentoModelo).where(PagamentoModelo.usuario_id == usuario.id)
    if mes is not None:
        consulta = consulta.where(PagamentoModelo.mes_conta == mes)
    consulta = consulta.order_by(PagamentoModelo.data_pagamento, PagamentoModelo.id)
    return [_pagamento_saida(p) for p in sessao.scalars(consulta)]


@router.post(
    "/pagamentos",
    response_model=PagamentoSaida,
    status_code=status.HTTP_201_CREATED,
    tags=["pagamentos"],
)
def pagar(
    dados: PagamentoEntrada, sessao: SessaoDep, usuario: UsuarioDep, hoje: HojeDep
) -> PagamentoSaida:
    conta_modelo = _do_usuario(sessao, ContaModelo, dados.conta_id, usuario, "Conta")
    conta = mapeamento.conta(conta_modelo)
    mes = Mes(dados.mes_conta)
    if not aparece_em(conta, mes):
        raise ErroDeValidacao("Essa conta não vence no mês informado.")
    ja_pago = sessao.scalar(
        select(PagamentoModelo).where(
            PagamentoModelo.conta_id == conta.id, PagamentoModelo.mes_conta == mes.valor
        )
    )
    if ja_pago is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Essa conta já foi paga nesse mês."
        )
    banco = _banco_opcional(sessao, dados.banco_id, usuario)
    valor = Dinheiro.de(dados.valor_pago) if dados.valor_pago is not None else conta.valor
    modelo = PagamentoModelo(
        id=_novo_id(),
        usuario_id=usuario.id,
        conta_id=conta.id,
        mes_conta=mes.valor,
        valor_pago=valor.valor,
        data_pagamento=dados.data_pagamento or hoje,
        banco_id=banco.id if banco else None,
    )
    sessao.add(modelo)
    _ajustar_saldo(sessao, modelo.banco_id, -valor.valor)
    return _pagamento_saida(modelo)


@router.delete(
    "/pagamentos/{pagamento_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["pagamentos"]
)
def desfazer_pagamento(pagamento_id: str, sessao: SessaoDep, usuario: UsuarioDep) -> Response:
    modelo = _do_usuario(sessao, PagamentoModelo, pagamento_id, usuario, "Pagamento")
    _ajustar_saldo(sessao, modelo.banco_id, Dinheiro.de(modelo.valor_pago).valor)
    sessao.delete(modelo)
    return _sem_conteudo()


# ---------------- ganhos ----------------


def _ganho_saida(m: GanhoModelo) -> GanhoSaida:
    g = mapeamento.ganho(m)
    return GanhoSaida(
        id=g.id,
        nome=g.nome,
        valor=g.valor.valor,
        data=g.data,
        recebido=g.recebido,
        banco_id=g.banco_id,
        renda_id=m.renda_id,
    )


def _efeito_ganho(m: GanhoModelo) -> Decimal:
    return Dinheiro.de(m.valor).valor if m.recebido and m.banco_id else Decimal("0")


@router.get("/ganhos", response_model=list[GanhoSaida], tags=["ganhos"])
def listar_ganhos(
    sessao: SessaoDep,
    usuario: UsuarioDep,
    ate: Annotated[MesTexto | None, Query(description="gera as rendas fixas até este mês")] = None,
) -> list[GanhoSaida]:
    if ate is not None:
        garantir_rendas(sessao, usuario, Mes(ate))
    ganhos = sessao.scalars(
        select(GanhoModelo)
        .where(GanhoModelo.usuario_id == usuario.id)
        .order_by(GanhoModelo.data, GanhoModelo.id)
    )
    return [_ganho_saida(g) for g in ganhos]


@router.post(
    "/ganhos", response_model=GanhoSaida, status_code=status.HTTP_201_CREATED, tags=["ganhos"]
)
def criar_ganho(dados: GanhoEntrada, sessao: SessaoDep, usuario: UsuarioDep) -> GanhoSaida:
    banco = _banco_opcional(sessao, dados.banco_id, usuario)
    modelo = GanhoModelo(
        id=_novo_id(),
        usuario_id=usuario.id,
        nome=dados.nome,
        valor=Dinheiro.de(dados.valor).valor,
        data=dados.data,
        recebido=dados.recebido,
        banco_id=banco.id if banco else None,
    )
    sessao.add(modelo)
    _ajustar_saldo(sessao, modelo.banco_id, _efeito_ganho(modelo))
    return _ganho_saida(modelo)


@router.put("/ganhos/{ganho_id}", response_model=GanhoSaida, tags=["ganhos"])
def editar_ganho(
    ganho_id: str, dados: GanhoEntrada, sessao: SessaoDep, usuario: UsuarioDep
) -> GanhoSaida:
    modelo = _do_usuario(sessao, GanhoModelo, ganho_id, usuario, "Ganho")
    banco = _banco_opcional(sessao, dados.banco_id, usuario)
    _ajustar_saldo(sessao, modelo.banco_id, -_efeito_ganho(modelo))
    modelo.nome = dados.nome
    modelo.valor = Dinheiro.de(dados.valor).valor
    modelo.data = dados.data
    modelo.recebido = dados.recebido
    modelo.banco_id = banco.id if banco else None
    _ajustar_saldo(sessao, modelo.banco_id, _efeito_ganho(modelo))
    return _ganho_saida(modelo)


@router.delete("/ganhos/{ganho_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["ganhos"])
def excluir_ganho(ganho_id: str, sessao: SessaoDep, usuario: UsuarioDep) -> Response:
    modelo = _do_usuario(sessao, GanhoModelo, ganho_id, usuario, "Ganho")
    _ajustar_saldo(sessao, modelo.banco_id, -_efeito_ganho(modelo))
    sessao.delete(modelo)
    return _sem_conteudo()
