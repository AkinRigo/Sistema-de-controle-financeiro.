"""Comando de voz. A rota só junta as peças:
dados do usuário → pedido → IA → conferência (domain/regras/voz.py) → proposta para a tela."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from painel.api.deps import HojeDep, SessaoDep, UsuarioDep
from painel.api.rotas.relatorios import _calcular
from painel.api.schemas import DinheiroSaida, MesTexto
from painel.domain.regras.painel import ganhos_do_mes
from painel.domain.regras.voz import (
    ESQUEMA,
    ContextoDeVoz,
    Opcao,
    Proposta,
    montar_pedido,
    validar_resposta,
)
from painel.domain.valores import Mes, somar_dinheiro

router = APIRouter(prefix="/voz", tags=["voz"])


class VozEntrada(BaseModel):
    texto: str = Field(min_length=1, max_length=300)
    mes: MesTexto


class ItemSaida(BaseModel):
    id: str
    nome: str
    valor: DinheiroSaida
    conta_id: str | None = None  # para pagar: qual conta e de qual mês
    mes_conta: str | None = None


class BancoSaida(BaseModel):
    id: str
    nome: str
    saldo: DinheiroSaida


class PropostaSaida(BaseModel):
    acao: str
    mensagem: str
    item: ItemSaida | None = None
    opcoes: list[ItemSaida] = []
    valor: DinheiroSaida | None = None
    banco: BancoSaida | None = None
    banco_destino: BancoSaida | None = None
    saldo_novo: DinheiroSaida | None = None
    nome: str = ""
    data: date | None = None
    tipo_conta: str = ""
    parcelas: int | None = None
    dia: int = 0
    mes_inicio: str | None = None


@router.post("/entender", response_model=PropostaSaida)
def entender(
    entrada: VozEntrada, request: Request, sessao: SessaoDep, usuario: UsuarioDep, hoje: HojeDep
) -> PropostaSaida:
    # 1. o que a pessoa pode citar
    dados, resumo = _calcular(sessao, usuario, entrada.mes, hoje)
    nomes = {c.id: c.nome for c in dados.contas}
    contexto = ContextoDeVoz(
        # a mesma conta pode estar aberta em dois meses (atrasada): o id leva o mês junto
        contas=tuple(
            Opcao(f"{a.conta.id}@{a.mes_origem.valor}", _nome_conta(a), a.conta.valor)
            for a in resumo.abertas
        ),
        ganhos=tuple(
            Opcao(g.ganho.id, g.ganho.nome, g.ganho.valor)
            for g in ganhos_do_mes(dados.ganhos, Mes(entrada.mes))
            if not g.ganho.recebido
        ),
        bancos=tuple(Opcao(b.id, b.nome, b.saldo) for b in dados.bancos),
        pagas=tuple(
            Opcao(p.id, nomes.get(p.conta_id, "Conta"), p.valor_pago) for p in resumo.pagas
        ),
    )

    # 2. a IA sugere; 3. a regra confere
    resposta = request.app.state.interpretador.interpretar(
        montar_pedido(entrada.texto, contexto, hoje), ESQUEMA
    )
    p = validar_resposta(resposta, contexto, hoje, Mes(entrada.mes))

    # 4. perguntas: quem responde é o backend, com os números do resumo (a IA não inventa valor)
    mensagem = p.mensagem
    if p.acao == "consultar_sobra":
        sobra = resumo.sobra.valor
        mensagem = (
            f"Se tudo que está previsto entrar, sobram R$ {_br(sobra)} no fim do mês."
            if sobra >= 0
            else f"Pra fechar o mês, faltam R$ {_br(-sobra)}."
        )
    elif p.acao == "consultar_falta":
        n = len(resumo.abertas)
        nomes_abertas = ", ".join(_nome_conta(a) for a in resumo.abertas[:4])
        mensagem = (
            f"Ainda faltam R$ {_br(resumo.falta_pagar.valor)} em {n} conta{'s' if n > 1 else ''}: "
            f"{nomes_abertas}{'…' if n > 4 else ''}."
            if n
            else "Nada! Todas as contas do mês estão pagas."
        )
    elif p.acao == "consultar_banco":
        total = somar_dinheiro(b.valor for b in contexto.bancos).valor
        mensagem = (
            f"O {p.banco.nome} está com R$ {_br(p.banco.valor.valor)}. " if p.banco else ""
        ) + f"No total, você tem R$ {_br(total)} nos bancos."

    return _saida(p, mensagem)


def _item(o: Opcao) -> ItemSaida:
    conta_id, _, mes_conta = o.id.partition("@")
    return ItemSaida(
        id=o.id,
        nome=o.nome,
        valor=o.valor.valor,
        conta_id=conta_id if mes_conta else None,
        mes_conta=mes_conta or None,
    )


def _banco(o: Opcao | None) -> BancoSaida | None:
    return BancoSaida(id=o.id, nome=o.nome, saldo=o.valor.valor) if o else None


def _saida(p: Proposta, mensagem: str) -> PropostaSaida:
    return PropostaSaida(
        acao=p.acao,
        mensagem=mensagem,
        item=_item(p.item) if p.item else None,
        opcoes=[_item(o) for o in p.opcoes],
        valor=p.valor.valor if p.valor else None,
        banco=_banco(p.banco),
        banco_destino=_banco(p.banco_destino),
        saldo_novo=p.saldo_novo.valor if p.saldo_novo else None,
        nome=p.nome,
        data=p.data,
        tipo_conta=p.tipo_conta,
        parcelas=p.parcelas,
        dia=p.dia,
        mes_inicio=p.mes_inicio.valor if p.mes_inicio else None,
    )


def _nome_conta(a) -> str:
    return f"{a.conta.nome} (atrasada de {a.mes_origem.valor})" if a.atrasada else a.conta.nome


def _br(valor: Decimal) -> str:
    """1234.5 → 1.234,50"""
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
