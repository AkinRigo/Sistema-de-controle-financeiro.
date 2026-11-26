"""Renda fixa: dinheiro que entra todo mês (salário, pensão, aluguel recebido...).

Cada renda gera um ganho "vai entrar" por mês, a partir de `mes_inicio`, criado sob demanda
quando alguém consulta um mês. Assim "Recebi", saldos de banco e o resumo funcionam como
para qualquer ganho. Editar ou excluir a renda mexe só nos ganhos ainda não recebidos do
mês atual em diante; o histórico recebido fica como está.
"""

import calendar
import uuid
from datetime import date

from fastapi import APIRouter, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from painel.api.deps import HojeDep, SessaoDep, UsuarioDep, nao_encontrado
from painel.api.schemas import RendaEntrada, RendaSaida
from painel.domain.valores import Dinheiro, Mes
from painel.infra.modelos import BancoModelo, GanhoModelo, RendaFixaModelo, UsuarioModelo

router = APIRouter(tags=["renda fixa"])

_LIMITE_MESES = 120  # proteção contra laços enormes (10 anos)


def _mes_de(d: date) -> Mes:
    return Mes(f"{d.year:04d}-{d.month:02d}")


def data_no_mes(dia: int, mes: Mes) -> date:
    """Dia da renda dentro do mês; 31 vira o último dia em meses curtos."""
    ano, m = (int(x) for x in mes.valor.split("-"))
    return date(ano, m, min(dia, calendar.monthrange(ano, m)[1]))


def garantir_rendas(sessao: Session, usuario: UsuarioModelo, ate: Mes) -> None:
    """Cria os ganhos mensais que faltam de cada renda fixa até o mês `ate`."""
    rendas = list(
        sessao.scalars(select(RendaFixaModelo).where(RendaFixaModelo.usuario_id == usuario.id))
    )
    if not rendas:
        return
    existentes = {
        (g.renda_id, g.mes_renda)
        for g in sessao.scalars(
            select(GanhoModelo).where(
                GanhoModelo.usuario_id == usuario.id, GanhoModelo.renda_id.is_not(None)
            )
        )
    }
    for renda in rendas:
        cursor = Mes(renda.mes_inicio)
        for _ in range(_LIMITE_MESES):
            if cursor > ate:
                break
            if (renda.id, cursor.valor) not in existentes:
                sessao.add(
                    GanhoModelo(
                        id=str(uuid.uuid4()),
                        usuario_id=usuario.id,
                        nome=renda.nome,
                        valor=renda.valor,
                        data=data_no_mes(renda.dia, cursor),
                        recebido=False,
                        banco_id=renda.banco_id,
                        renda_id=renda.id,
                        mes_renda=cursor.valor,
                    )
                )
            cursor = cursor.somar(1)
    sessao.flush()


def _saida(r: RendaFixaModelo) -> RendaSaida:
    return RendaSaida(
        id=r.id,
        nome=r.nome,
        valor=Dinheiro.de(r.valor).valor,
        dia=r.dia,
        mes_inicio=r.mes_inicio,
        banco_id=r.banco_id,
    )


def _da_conta(sessao: Session, renda_id: str, usuario: UsuarioModelo) -> RendaFixaModelo:
    renda = sessao.get(RendaFixaModelo, renda_id)
    if renda is None or renda.usuario_id != usuario.id:
        raise nao_encontrado("Renda fixa")
    return renda


def _banco_valido(sessao: Session, banco_id: str | None, usuario: UsuarioModelo) -> str | None:
    if banco_id is None:
        return None
    banco = sessao.get(BancoModelo, banco_id)
    if banco is None or banco.usuario_id != usuario.id:
        raise nao_encontrado("Banco")
    return banco.id


def _pendentes_a_partir(sessao: Session, renda: RendaFixaModelo, mes: Mes) -> list[GanhoModelo]:
    return list(
        sessao.scalars(
            select(GanhoModelo).where(
                GanhoModelo.renda_id == renda.id,
                GanhoModelo.recebido.is_(False),
                GanhoModelo.mes_renda >= mes.valor,
            )
        )
    )


@router.get("/rendas", response_model=list[RendaSaida])
def listar_rendas(sessao: SessaoDep, usuario: UsuarioDep) -> list[RendaSaida]:
    rendas = sessao.scalars(
        select(RendaFixaModelo)
        .where(RendaFixaModelo.usuario_id == usuario.id)
        .order_by(RendaFixaModelo.dia, RendaFixaModelo.nome)
    )
    return [_saida(r) for r in rendas]


@router.post("/rendas", response_model=RendaSaida, status_code=status.HTTP_201_CREATED)
def criar_renda(
    dados: RendaEntrada, sessao: SessaoDep, usuario: UsuarioDep, hoje: HojeDep
) -> RendaSaida:
    renda = RendaFixaModelo(
        id=str(uuid.uuid4()),
        usuario_id=usuario.id,
        nome=dados.nome,
        valor=Dinheiro.de(dados.valor).valor,
        dia=dados.dia,
        mes_inicio=dados.mes_inicio or _mes_de(hoje).valor,
        banco_id=_banco_valido(sessao, dados.banco_id, usuario),
    )
    sessao.add(renda)
    sessao.flush()
    return _saida(renda)


@router.put("/rendas/{renda_id}", response_model=RendaSaida)
def editar_renda(
    renda_id: str, dados: RendaEntrada, sessao: SessaoDep, usuario: UsuarioDep, hoje: HojeDep
) -> RendaSaida:
    renda = _da_conta(sessao, renda_id, usuario)
    renda.nome = dados.nome
    renda.valor = Dinheiro.de(dados.valor).valor
    renda.dia = dados.dia
    renda.banco_id = _banco_valido(sessao, dados.banco_id, usuario)
    if dados.mes_inicio:
        renda.mes_inicio = dados.mes_inicio
    for g in _pendentes_a_partir(sessao, renda, _mes_de(hoje)):
        g.nome, g.valor, g.banco_id = renda.nome, renda.valor, renda.banco_id
        g.data = data_no_mes(renda.dia, Mes(g.mes_renda))
    # meses antes do novo início que ainda não foram recebidos deixam de valer
    for g in _pendentes_a_partir(sessao, renda, Mes("0001-01")):
        if g.mes_renda < renda.mes_inicio:
            sessao.delete(g)
    return _saida(renda)


@router.delete("/rendas/{renda_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_renda(
    renda_id: str, sessao: SessaoDep, usuario: UsuarioDep, hoje: HojeDep
) -> Response:
    renda = _da_conta(sessao, renda_id, usuario)
    for g in _pendentes_a_partir(sessao, renda, _mes_de(hoje)):
        sessao.delete(g)
    sessao.flush()
    sessao.delete(renda)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
