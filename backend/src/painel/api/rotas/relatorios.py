"""Resumo mensal, totais por categoria e dívida total."""

from dataclasses import dataclass

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import Session

from painel.api.deps import HojeDep, SessaoDep, UsuarioDep
from painel.api.schemas import (
    CategoriaSaida,
    ContaAbertaSaida,
    DividaSaida,
    MesTexto,
    PagamentoSaida,
    ResumoSaida,
)
from painel.domain.entidades import Banco, Conta, Ganho, Pagamento, Usuario
from painel.domain.regras.categorias import CATEGORIAS, categoria_da_conta, resumir_categorias
from painel.domain.regras.divida import calcular_divida_total
from painel.domain.regras.resumo import calcular_resumo
from painel.domain.valores import Dinheiro, Mes
from painel.infra import mapeamento
from painel.infra.modelos import (
    BancoModelo,
    ContaModelo,
    GanhoModelo,
    PagamentoModelo,
    UsuarioModelo,
)

router = APIRouter(tags=["relatórios"])


@dataclass(frozen=True, slots=True)
class _Dados:
    usuario: Usuario
    bancos: list[Banco]
    contas: list[Conta]
    pagamentos: list[Pagamento]
    ganhos: list[Ganho]


def _carregar(sessao: Session, usuario: UsuarioModelo) -> _Dados:
    def todos(modelo, conversor):
        return [
            conversor(m)
            for m in sessao.scalars(select(modelo).where(modelo.usuario_id == usuario.id))
        ]

    return _Dados(
        usuario=mapeamento.usuario(usuario),
        bancos=todos(BancoModelo, mapeamento.banco),
        contas=todos(ContaModelo, mapeamento.conta),
        pagamentos=todos(PagamentoModelo, mapeamento.pagamento),
        ganhos=todos(GanhoModelo, mapeamento.ganho),
    )


@router.get("/resumo/{mes}", response_model=ResumoSaida)
def resumo(mes: MesTexto, sessao: SessaoDep, usuario: UsuarioDep, hoje: HojeDep) -> ResumoSaida:
    dados = _carregar(sessao, usuario)
    r = calcular_resumo(
        mes=Mes(mes),
        usuario=dados.usuario,
        bancos=dados.bancos,
        contas=dados.contas,
        pagamentos=dados.pagamentos,
        ganhos=dados.ganhos,
        hoje=hoje,
        por_semana=Dinheiro.de(usuario.corridas_por_semana),
        por_fim_de_semana=Dinheiro.de(usuario.corridas_por_fim_de_semana),
        contar_na_previsao=usuario.contar_corridas,
    )
    return ResumoSaida(
        mes=r.mes.valor,
        tenho=r.tenho.valor,
        vai_entrar=r.vai_entrar.valor,
        recebido=r.recebido.valor,
        corridas=r.corridas.valor,
        falta_pagar=r.falta_pagar.valor,
        ja_pago=r.ja_pago.valor,
        sobra=r.sobra.valor,
        abertas=[
            ContaAbertaSaida(
                conta_id=a.conta.id,
                nome=a.conta.nome,
                valor=a.conta.valor.valor,
                categoria=categoria_da_conta(a.conta),
                mes_origem=a.mes_origem.valor,
                atrasada=a.atrasada,
                numero_parcela=a.numero_parcela,
                total_parcelas=a.conta.total_parcelas,
                dia_vencimento=a.conta.dia_vencimento,
                juros_altos=a.conta.juros_altos,
            )
            for a in r.abertas
        ],
        pagas=[
            PagamentoSaida(
                id=p.id,
                conta_id=p.conta_id,
                mes_conta=p.mes_conta.valor,
                valor_pago=p.valor_pago.valor,
                data_pagamento=p.data_pagamento,
                banco_id=p.banco_id,
            )
            for p in r.pagas
        ],
    )


@router.get("/categorias/{mes}", response_model=list[CategoriaSaida])
def categorias(mes: MesTexto, sessao: SessaoDep, usuario: UsuarioDep) -> list[CategoriaSaida]:
    dados = _carregar(sessao, usuario)
    totais = resumir_categorias(Mes(mes), dados.usuario.desde, dados.contas, dados.pagamentos)
    return [
        CategoriaSaida(
            chave=chave,
            nome=CATEGORIAS[chave],
            falta_pagar=t.falta_pagar.valor,
            ja_pago=t.ja_pago.valor,
            fixas_por_mes=t.fixas_por_mes.valor,
            ainda_devo=t.ainda_devo.valor,
        )
        for chave, t in totais.items()
    ]


@router.get("/categorias", response_model=dict[str, str])
def listar_categorias() -> dict[str, str]:
    return CATEGORIAS


@router.get("/divida", response_model=DividaSaida)
def divida(sessao: SessaoDep, usuario: UsuarioDep) -> DividaSaida:
    dados = _carregar(sessao, usuario)
    total = calcular_divida_total(dados.contas, dados.usuario.desde, dados.pagamentos)
    return DividaSaida(total=total.valor)
