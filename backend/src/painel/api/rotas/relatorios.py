"""Resumo mensal, totais por categoria e dívida total."""

from dataclasses import dataclass

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import Session

from painel.api.deps import HojeDep, SessaoDep, UsuarioDep
from painel.api.rotas.rendas import garantir_rendas
from painel.api.schemas import (
    CategoriaSaida,
    ContaAbertaSaida,
    DividaSaida,
    ItemCategoriaSaida,
    MesTexto,
    PagamentoSaida,
    ResumoSaida,
    SaldoDiarioSaida,
)
from painel.domain.entidades import Banco, Conta, Ganho, Pagamento, Usuario
from painel.domain.regras.categorias import CATEGORIAS, categoria_da_conta, resumir_categorias
from painel.domain.regras.divida import calcular_divida_total
from painel.domain.regras.painel import (
    cobertura_percentual,
    dias_para_vencer,
    itens_por_categoria,
    numero_parcela_paga,
    referencia_para_editar,
    situacao_vencimento,
)
from painel.domain.regras.resumo import calcular_resumo
from painel.domain.regras.saldo_diario import DiaDeSaldo, saldo_dia_a_dia
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


def _calcular(sessao: Session, usuario: UsuarioModelo, mes: str, hoje):
    garantir_rendas(sessao, usuario, Mes(mes))
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
    return dados, r


@router.get("/resumo/{mes}", response_model=ResumoSaida)
def resumo(mes: MesTexto, sessao: SessaoDep, usuario: UsuarioDep, hoje: HojeDep) -> ResumoSaida:
    dados, r = _calcular(sessao, usuario, mes, hoje)
    contas_por_id = {c.id: c for c in dados.contas}
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
                vence_em_dias=dias_para_vencer(a.conta, r.mes, hoje, a.atrasada),
                situacao_vencimento=situacao_vencimento(
                    dias_para_vencer(a.conta, r.mes, hoje, a.atrasada)
                ),
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
                numero_parcela=(
                    numero_parcela_paga(contas_por_id[p.conta_id], p)
                    if p.conta_id in contas_por_id
                    else None
                ),
            )
            for p in r.pagas
        ],
        cobertura=cobertura_percentual(r),
        divida_total=calcular_divida_total(
            dados.contas, dados.usuario.desde, dados.pagamentos
        ).valor,
    )


def _dia(d: DiaDeSaldo) -> dict:
    return {
        "dia": d.dia,
        "saldo": d.saldo.valor,
        "previsao": d.previsao,
        "movimentos": [
            {"nome": m.nome, "valor": m.valor.valor, "previsto": m.previsto} for m in d.movimentos
        ],
    }


@router.get("/saldo-diario/{mes}", response_model=SaldoDiarioSaida)
def saldo_diario(
    mes: MesTexto, sessao: SessaoDep, usuario: UsuarioDep, hoje: HojeDep
) -> SaldoDiarioSaida:
    """Saldo no fim de cada dia do mês (gráfico de barras). Corridas ficam de fora."""
    dados, r = _calcular(sessao, usuario, mes, hoje)
    s = saldo_dia_a_dia(r, hoje, dados.contas, dados.pagamentos, dados.ganhos)
    return SaldoDiarioSaida(
        mes=mes,
        hoje=s.hoje,
        dias=[_dia(d) for d in s.dias],
        menor=_dia(s.menor) if s.menor else None,
    )


@router.get("/categorias/{mes}", response_model=list[CategoriaSaida])
def categorias(mes: MesTexto, sessao: SessaoDep, usuario: UsuarioDep) -> list[CategoriaSaida]:
    dados = _carregar(sessao, usuario)
    totais = resumir_categorias(Mes(mes), dados.usuario.desde, dados.contas, dados.pagamentos)
    itens = itens_por_categoria(Mes(mes), dados.usuario.desde, dados.contas, dados.pagamentos)
    return [
        CategoriaSaida(
            chave=chave,
            nome=CATEGORIAS[chave],
            falta_pagar=t.falta_pagar.valor,
            ja_pago=t.ja_pago.valor,
            fixas_por_mes=t.fixas_por_mes.valor,
            ainda_devo=t.ainda_devo.valor,
            itens=[
                ItemCategoriaSaida(
                    conta_id=i.conta.id,
                    nome=i.conta.nome,
                    credor=i.conta.credor,
                    tipo=i.conta.tipo,
                    valor=i.valor.valor,
                    valor_parcela=i.conta.valor.valor,
                    parcelas_restantes=i.parcelas_restantes,
                    total_parcelas=i.conta.total_parcelas,
                    mes_referencia=referencia_para_editar(i.conta, Mes(mes))[0].valor,
                    parcela_no_mes=referencia_para_editar(i.conta, Mes(mes))[1],
                )
                for i in itens.get(chave, [])
            ],
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
