"""Exportação e importação no formato JSON do protótipo (versão 2).

A importação substitui todos os dados do usuário. Os saldos dos bancos são gravados como
vieram no arquivo: pagamentos e ganhos importados não mexem neles de novo.
"""

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select

from painel.api.deps import SessaoDep, UsuarioDep
from painel.domain.entidades import Conta, TipoConta
from painel.domain.erros import ErroDeValidacao
from painel.domain.regras.categorias import CATEGORIAS, categoria_da_conta
from painel.domain.regras.ocorrencias import aparece_em
from painel.domain.valores import Dinheiro, Mes
from painel.infra import mapeamento
from painel.infra.modelos import (
    BancoModelo,
    ContaModelo,
    GanhoModelo,
    PagamentoModelo,
)

router = APIRouter(tags=["backup"])

_TIPO_PARA_JSON = {
    TipoConta.FIXA: "fixed",
    TipoConta.UNICA: "single",
    TipoConta.PARCELADA: "installment",
}
_TIPO_DO_JSON = {v: k for k, v in _TIPO_PARA_JSON.items()}


class _Solto(BaseModel):
    model_config = ConfigDict(extra="ignore")


class BancoJson(_Solto):
    id: str
    name: str = "Banco"
    balance: float | str | int = 0


class GanhoJson(_Solto):
    id: str
    name: str = "Ganho"
    value: float | str | int = 0
    date: date
    received: bool = False
    accountId: str | None = None


class ContaJson(_Solto):
    id: str
    name: str = "Conta"
    creditor: str | None = None
    value: float | str | int = 0
    dueDay: int = 0
    type: str = "single"
    startMonth: str
    endMonth: str | None = None
    startNumber: int = 1
    total: int = 1
    highInterest: bool = False
    uncertain: bool = False
    group: str = ""


class PagamentoJson(_Solto):
    amount: float | str | int = 0
    accountId: str | None = None
    date: date


class CorridasJson(_Solto):
    weekday: float | str | int = 0
    weekend: float | str | int = 0
    on: bool = False


class BackupJson(_Solto):
    version: int = 2
    since: str | None = None
    accounts: list[BancoJson] = Field(default_factory=list)
    incomes: list[GanhoJson] = Field(default_factory=list)
    bills: list[ContaJson] = Field(default_factory=list)
    payments: dict[str, dict[str, PagamentoJson]] = Field(default_factory=dict)
    sim: CorridasJson = Field(default_factory=CorridasJson)


class ResultadoImportacao(BaseModel):
    bancos: int
    contas: int
    ganhos: int
    pagamentos: int
    ignorados: int


def _dinheiro(valor: float | str | int) -> Decimal:
    try:
        texto = repr(valor) if isinstance(valor, float) else str(valor)
        return Dinheiro.de(Decimal(texto)).valor
    except (InvalidOperation, ErroDeValidacao):
        raise ErroDeValidacao(f"Valor inválido no backup: {valor!r}.") from None


def _texto(valor: Decimal) -> float:
    # O protótipo guarda números; devolvemos float só no arquivo de backup.
    return float(valor)


@router.get("/backup")
def exportar(sessao: SessaoDep, usuario: UsuarioDep) -> dict:
    def todos(modelo):
        return list(sessao.scalars(select(modelo).where(modelo.usuario_id == usuario.id)))

    contas = todos(ContaModelo)
    pagamentos: dict[str, dict[str, dict]] = {}
    for p in todos(PagamentoModelo):
        pagamentos.setdefault(p.mes_conta, {})[p.conta_id] = {
            "amount": _texto(p.valor_pago),
            "accountId": p.banco_id,
            "date": p.data_pagamento.isoformat(),
        }

    bills = []
    for m in contas:
        c = mapeamento.conta(m)
        grupo = categoria_da_conta(c)
        bills.append(
            {
                "id": c.id,
                "name": c.nome,
                "creditor": c.credor or CATEGORIAS[grupo],
                "value": _texto(c.valor.valor),
                "dueDay": c.dia_vencimento,
                "type": _TIPO_PARA_JSON[c.tipo],
                "startMonth": c.mes_inicio.valor,
                "endMonth": c.mes_fim.valor if c.mes_fim else None,
                "startNumber": c.parcela_inicial or 1,
                "total": c.total_parcelas or 1,
                "highInterest": c.juros_altos,
                "uncertain": m.incerto,
                "group": grupo,
            }
        )

    return {
        "version": 2,
        "since": usuario.desde,
        "accounts": [
            {"id": b.id, "name": b.nome, "balance": _texto(b.saldo)} for b in todos(BancoModelo)
        ],
        "incomes": [
            {
                "id": g.id,
                "name": g.nome,
                "value": _texto(g.valor),
                "date": g.data.isoformat(),
                "received": g.recebido,
                "accountId": g.banco_id,
            }
            for g in todos(GanhoModelo)
        ],
        "bills": bills,
        "payments": pagamentos,
        "sim": {
            "weekday": _texto(usuario.corridas_por_semana),
            "weekend": _texto(usuario.corridas_por_fim_de_semana),
            "on": usuario.contar_corridas,
        },
        "theme": "auto",
    }


def _conta_do_json(b: ContaJson, novo_id: str, usuario_id: str) -> Conta:
    tipo = _TIPO_DO_JSON.get(b.type, TipoConta.UNICA)
    grupo = b.group if b.group in CATEGORIAS else ""
    credor = (b.creditor or "").strip() or None
    if credor in {CATEGORIAS.get(grupo), "Outros"}:
        credor = None
    try:
        return Conta(
            id=novo_id,
            usuario_id=usuario_id,
            nome=b.name.strip() or "Conta",
            valor=Dinheiro.de(_dinheiro(b.value)),
            tipo=tipo,
            mes_inicio=Mes(b.startMonth),
            categoria=grupo,
            credor=credor,
            dia_vencimento=max(0, min(31, b.dueDay)),
            mes_fim=Mes(b.endMonth) if tipo is TipoConta.FIXA and b.endMonth else None,
            parcela_inicial=b.startNumber if tipo is TipoConta.PARCELADA else None,
            total_parcelas=b.total if tipo is TipoConta.PARCELADA else None,
            juros_altos=b.highInterest,
        )
    except ErroDeValidacao as erro:
        raise ErroDeValidacao(f"Conta “{b.name}”: {erro}") from None


@router.post("/backup", response_model=ResultadoImportacao)
def importar(dados: BackupJson, sessao: SessaoDep, usuario: UsuarioDep) -> ResultadoImportacao:
    if dados.version != 2:
        raise ErroDeValidacao("Versão de backup não suportada.")

    # Valida tudo antes de apagar qualquer coisa.
    ids_banco = {b.id: str(uuid.uuid4()) for b in dados.accounts}
    contas: dict[str, tuple[Conta, bool]] = {}
    for b in dados.bills:
        novo = str(uuid.uuid4())
        contas[b.id] = (_conta_do_json(b, novo, usuario.id), b.uncertain)
    desde = Mes(dados.since).valor if dados.since else usuario.desde

    for modelo in (PagamentoModelo, GanhoModelo, ContaModelo, BancoModelo):
        sessao.execute(delete(modelo).where(modelo.usuario_id == usuario.id))

    usuario.desde = desde
    usuario.corridas_por_semana = _dinheiro(dados.sim.weekday)
    usuario.corridas_por_fim_de_semana = _dinheiro(dados.sim.weekend)
    usuario.contar_corridas = dados.sim.on

    for b in dados.accounts:
        sessao.add(
            BancoModelo(
                id=ids_banco[b.id],
                usuario_id=usuario.id,
                nome=b.name.strip() or "Banco",
                saldo=_dinheiro(b.balance),
            )
        )
    for conta, incerto in contas.values():
        sessao.add(
            ContaModelo(
                id=conta.id,
                usuario_id=usuario.id,
                nome=conta.nome,
                valor=conta.valor.valor,
                tipo=conta.tipo.value,
                mes_inicio=conta.mes_inicio.valor,
                categoria=conta.categoria,
                credor=conta.credor,
                dia_vencimento=conta.dia_vencimento,
                mes_fim=conta.mes_fim.valor if conta.mes_fim else None,
                parcela_inicial=conta.parcela_inicial,
                total_parcelas=conta.total_parcelas,
                juros_altos=conta.juros_altos,
                incerto=incerto,
            )
        )
    for g in dados.incomes:
        sessao.add(
            GanhoModelo(
                id=str(uuid.uuid4()),
                usuario_id=usuario.id,
                nome=g.name.strip() or "Ganho",
                valor=_dinheiro(g.value),
                data=g.date,
                recebido=g.received,
                banco_id=ids_banco.get(g.accountId) if g.accountId else None,
            )
        )
    sessao.flush()

    importados = ignorados = 0
    for mes_texto, por_conta in dados.payments.items():
        try:
            mes = Mes(mes_texto)
        except ErroDeValidacao:
            ignorados += len(por_conta)
            continue
        for conta_id_json, p in por_conta.items():
            item = contas.get(conta_id_json)
            if item is None or not aparece_em(item[0], mes):
                ignorados += 1
                continue
            sessao.add(
                PagamentoModelo(
                    id=str(uuid.uuid4()),
                    usuario_id=usuario.id,
                    conta_id=item[0].id,
                    mes_conta=mes.valor,
                    valor_pago=_dinheiro(p.amount),
                    data_pagamento=p.date,
                    banco_id=ids_banco.get(p.accountId) if p.accountId else None,
                )
            )
            importados += 1

    return ResultadoImportacao(
        bancos=len(dados.accounts),
        contas=len(contas),
        ganhos=len(dados.incomes),
        pagamentos=importados,
        ignorados=ignorados,
    )
