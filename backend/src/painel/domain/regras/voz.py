"""Comando de voz: monta o pedido para a IA e confere o que ela respondeu.

A IA só SUGERE uma ação. Esta regra é quem DECIDE: confere se a conta/ganho/banco
existem e são do usuário, e se os valores fazem sentido. Não sabe que existe IA nem internet.

Para ensinar uma ação nova: (1) ESQUEMA, (2) texto em montar_pedido, (3) uma função _conferir_*
registrada em CONFERIR, (4) testes.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from painel.domain.valores import Dinheiro, Mes

ACOES = (
    "pagar_conta",
    "desfazer_pagamento",
    "receber_ganho",
    "novo_ganho",
    "nova_conta",
    "novo_banco",
    "somar_banco",
    "ajustar_saldo",
    "transferir",
    "editar_conta",
    "editar_ganho",
    "editar_banco",
    "apagar_conta",
    "apagar_ganho",
    "apagar_banco",
    "consultar_sobra",
    "consultar_falta",
    "consultar_banco",
    "nao_entendi",
)
TIPOS_CONTA = ("unica", "fixa", "parcelada")


def _campo(tipo: str, descricao: str, **extra) -> dict:
    return {"type": tipo, "nullable": True, "description": descricao, **extra}


# O "formulário" que a IA preenche (formato de esquema do Gemini). Campo que não se aplica: null.
ESQUEMA = {
    "type": "OBJECT",
    "properties": {
        "acao": {"type": "STRING", "enum": list(ACOES)},
        "item_id": _campo("STRING", "id da conta, ganho ou pagamento citado"),
        "opcoes_ids": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "se a fala serve para mais de um item, os ids possíveis",
        },
        "valor": _campo("STRING", "valor falado com ponto decimal, ex.: 180.00"),
        "banco_id": _campo("STRING", "id do banco citado (na transferência: o de origem)"),
        "banco_destino_id": _campo("STRING", "transferir: id do banco de destino"),
        "nome": _campo("STRING", "nome do ganho, conta ou banco novo; no editar, o nome NOVO"),
        "data": _campo("STRING", "novo_ganho/editar_ganho: quando entra, AAAA-MM-DD"),
        "tipo_conta": _campo(
            "STRING", "nova_conta: unica, fixa ou parcelada", enum=list(TIPOS_CONTA)
        ),
        "parcelas": _campo("INTEGER", "nova_conta parcelada: número de parcelas"),
        "dia": _campo("INTEGER", "nova_conta/editar_conta: dia do vencimento (1 a 31)"),
    },
    "required": [
        "acao",
        "item_id",
        "opcoes_ids",
        "valor",
        "banco_id",
        "banco_destino_id",
        "nome",
        "data",
        "tipo_conta",
        "parcelas",
        "dia",
    ],
}


@dataclass(frozen=True, slots=True)
class Opcao:
    """Algo que a pessoa pode citar na fala: conta, ganho, pagamento ou banco."""

    id: str
    nome: str
    valor: Dinheiro = Dinheiro.zero()  # valor da conta/ganho/pagamento, ou saldo do banco


@dataclass(frozen=True, slots=True)
class ContextoDeVoz:
    contas: tuple[Opcao, ...]  # contas em aberto no mês
    ganhos: tuple[Opcao, ...]  # ganhos que ainda vão entrar
    bancos: tuple[Opcao, ...]
    pagas: tuple[Opcao, ...] = ()  # pagamentos feitos no mês (para desfazer)
    cadastro: tuple[Opcao, ...] = ()  # todas as contas cadastradas (para editar/apagar)


@dataclass(frozen=True, slots=True)
class Proposta:
    """O que o backend devolve para a tela confirmar. Só os campos da ação vêm preenchidos."""

    acao: str
    mensagem: str = ""
    item: Opcao | None = None
    opcoes: tuple[Opcao, ...] = ()  # mais de um item possível: a tela pergunta qual
    valor: Dinheiro | None = None
    banco: Opcao | None = None
    banco_destino: Opcao | None = None
    saldo_novo: Dinheiro | None = None  # somar/ajustar: como o banco fica
    nome: str = ""
    data: date | None = None
    tipo_conta: str = ""
    parcelas: int | None = None
    dia: int = 0
    mes_inicio: Mes | None = None
    parar_em: Mes | None = None  # apagar conta de todo mês: "parar a partir de"


NAO_ENTENDI = (
    "Não entendi direito. Dá pra falar, por exemplo: “paguei a luz”, “recebi o salário”, "
    "“vai entrar 300 do freela dia 10”, “conta de internet 120 todo mês” ou “quanto sobra?”."
)
NOME_PADRAO_GANHO = "Entrada"
DIAS_PARA_TRAS, DIAS_PARA_FRENTE = 31, 366  # datas fora disso são engano: viram hoje
MAX_PARCELAS = 120


def _nao(mensagem: str = NAO_ENTENDI) -> Proposta:
    return Proposta("nao_entendi", mensagem=mensagem)


# ---------------- o pedido para a IA ----------------


def montar_pedido(texto: str, contexto: ContextoDeVoz, hoje: date) -> str:
    """O texto que vai para a IA: as ações, as regras, as opções do usuário (com ids) e a frase."""

    def lista(opcoes: tuple[Opcao, ...]) -> str:
        if not opcoes:
            return "  (nenhum)"
        return "\n".join(f"  - id={o.id} | {o.nome} | R$ {o.valor.valor}" for o in opcoes)

    return f"""Você interpreta comandos de voz de um app de finanças pessoais em português.
Hoje é {hoje.isoformat()}. Escolha UMA ação:
- pagar_conta: pagou uma conta em aberto ("paguei a luz").
- desfazer_pagamento: diz que uma conta paga ainda NÃO foi paga ("ainda não paguei a luz").
- receber_ganho: recebeu um ganho previsto ("recebi o freela", "caiu o salário").
- novo_ganho: vai entrar um dinheiro que NÃO está nos ganhos previstos ("vai entrar 300").
- nova_conta: cadastrar conta nova ("conta de internet 120 todo mês dia 10",
  "parcelei a geladeira em 10 vezes de 300", "conta do mecânico 400").
- novo_banco: cadastrar banco ("adiciona o banco Inter com 500").
- somar_banco: entrou dinheiro num banco que não é ganho previsto ("coloquei 200 no nubank").
- ajustar_saldo: informa o saldo atual de um banco ("o nubank tá com 1500").
- transferir: passou dinheiro de um banco para outro ("passei 300 do nubank pra caixa").
- editar_conta: mudar valor, dia de vencimento ou nome de uma conta cadastrada
  ("muda o aluguel pra 1400", "a conta do celular vence dia 5").
- editar_ganho: mudar valor, data ou nome de um ganho que vai entrar ("o fgts entra dia 30").
- editar_banco: trocar o nome de um banco ("troca o nome do nubank pra nu").
- apagar_conta: apagar/remover/excluir uma conta cadastrada ("apaga a conta do celular").
- apagar_ganho: apagar ganho(s) que vão entrar ("apaga o freela"). "Todos" = todos os ids
  em opcoes_ids.
- apagar_banco: apagar/remover um banco ("apaga o banco caixa").
- consultar_sobra: pergunta quanto sobra no mês.
- consultar_falta: pergunta quanto ainda falta pagar.
- consultar_banco: pergunta quanto tem num banco ou no total.
- nao_entendi: qualquer outra coisa.

Regras:
- Use SOMENTE ids das listas abaixo. Nunca invente id.
- Se a fala servir para mais de um item, deixe item_id null e ponha os ids em opcoes_ids.
- valor: só se a pessoa falou um valor ("180", "cento e oitenta"), no formato 180.00.
  Na conta parcelada, valor é o de CADA parcela.
- tipo_conta: "todo mês" = fixa; "em N vezes" = parcelada; senão unica.
- data e dia: "dia 10" = dia 10 deste mês, ou do próximo se já passou; "amanhã", "sexta"
  etc. a partir de hoje.
- No editar: valor, dia, data e nome são os NOVOS; só preencha o que a pessoa pediu pra mudar.
- Campo que não se aplica à ação: null.

Contas em aberto (para pagar):
{lista(contexto.contas)}

Contas cadastradas (para editar ou apagar):
{lista(contexto.cadastro)}

Contas já pagas neste mês:
{lista(contexto.pagas)}

Ganhos que vão entrar:
{lista(contexto.ganhos)}

Bancos (valor = saldo):
{lista(contexto.bancos)}

Frase falada: "{texto}"
"""


# ---------------- ajudantes de conferência ----------------


def _valor(bruto: object, *, aceita_zero: bool = False) -> Dinheiro | None:
    """Texto da IA → Dinheiro. None se veio vazio. ValueError se veio lixo ou valor inválido."""
    if bruto in (None, ""):
        return None
    try:
        valor = Dinheiro.de(Decimal(str(bruto).replace(",", ".")))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("valor inválido") from None
    if valor.valor < 0 or (valor.valor == 0 and not aceita_zero):
        raise ValueError("valor precisa ser positivo")
    return valor


def _valor_ou_none(bruto: object) -> Dinheiro | None:
    try:
        return _valor(bruto)
    except ValueError:
        return None


def _achar(opcoes: tuple[Opcao, ...], id_: object) -> Opcao | None:
    return next((o for o in opcoes if o.id == id_), None)


def _nome(bruto: object) -> str:
    nome = str(bruto or "").strip()[:120]
    return nome[:1].upper() + nome[1:]


def _data(bruto: object, hoje: date) -> date:
    """Data da IA; vazia, inválida ou absurda vira hoje."""
    return _data_ou_none(bruto, hoje) or hoje


def _mes_de(d: date) -> Mes:
    return Mes(f"{d.year:04d}-{d.month:02d}")


# ---------------- uma função por ação ----------------
# Todas recebem (resposta, contexto, hoje, mes) e devolvem uma Proposta.


def _escolher_item(acao: str, resposta: dict, onde: tuple[Opcao, ...]) -> Proposta:
    """Comum a pagar, desfazer e receber: um item certo, várias opções, ou não entendi."""
    item = _achar(onde, resposta.get("item_id"))
    if item is None:
        opcoes = tuple(o for i in resposta.get("opcoes_ids") or [] if (o := _achar(onde, i)))
        if len(opcoes) >= 2:
            return Proposta(acao, opcoes=opcoes, mensagem="Qual destes?")
        if not opcoes:
            return _nao()
        item = opcoes[0]
    return Proposta(acao, item=item)


def _banco_citado(resposta: dict, contexto: ContextoDeVoz) -> Opcao | None:
    """O banco que a pessoa citou. A IA às vezes põe o id do banco em item_id: aceita os dois
    (o id é conferido contra os bancos do usuário do mesmo jeito)."""
    return _achar(contexto.bancos, resposta.get("banco_id")) or _achar(
        contexto.bancos, resposta.get("item_id")
    )


def _banco_falado_ou_unico(resposta: dict, contexto: ContextoDeVoz) -> Opcao | None:
    banco = _banco_citado(resposta, contexto)
    if banco is None and len(contexto.bancos) == 1:
        banco = contexto.bancos[0]  # só tem um banco: não precisa perguntar
    return banco


def _conferir_item_com_valor(acao: str, onde: Callable[[ContextoDeVoz], tuple[Opcao, ...]]):
    """Pagar e receber: o item, o valor falado (ou o do item) e o banco."""

    def conferir(resposta, contexto, hoje, mes):
        p = _escolher_item(acao, resposta, onde(contexto))
        if p.acao == "nao_entendi":
            return p
        try:
            valor = _valor(resposta.get("valor"))
        except ValueError:
            return _nao("Não entendi o valor. Fala de novo com o valor.")
        banco = _banco_falado_ou_unico(resposta, contexto)
        return replace(p, valor=valor or (p.item.valor if p.item else None), banco=banco)

    return conferir


def _conferir_desfazer(resposta, contexto, hoje, mes):
    p = _escolher_item("desfazer_pagamento", resposta, contexto.pagas)
    return replace(p, valor=p.item.valor) if p.item else p


def _conferir_novo_ganho(resposta, contexto, hoje, mes):
    valor = _valor_ou_none(resposta.get("valor"))
    if valor is None:  # sem valor não dá pra anotar
        return _nao("Quanto vai entrar? Fala de novo com o valor.")
    return Proposta(
        "novo_ganho",
        valor=valor,
        nome=_nome(resposta.get("nome")) or NOME_PADRAO_GANHO,
        data=_data(resposta.get("data"), hoje),
    )


def _conferir_nova_conta(resposta, contexto, hoje, mes):
    nome = _nome(resposta.get("nome"))
    if not nome:
        return _nao("Qual o nome da conta? Ex.: “conta de internet 120 todo mês”.")
    valor = _valor_ou_none(resposta.get("valor"))
    if valor is None:
        return _nao(f"Qual o valor de {nome}? Fala de novo com o valor.")
    tipo = resposta.get("tipo_conta") if resposta.get("tipo_conta") in TIPOS_CONTA else "unica"
    parcelas = resposta.get("parcelas")
    if tipo == "parcelada" and not (isinstance(parcelas, int) and 2 <= parcelas <= MAX_PARCELAS):
        return _nao("Em quantas vezes? Ex.: “parcelei a geladeira em 10 vezes de 300”.")
    dia = resposta.get("dia")
    dia = dia if isinstance(dia, int) and 1 <= dia <= 31 else 0
    # conta que não é parcelada e já venceu neste mês começa no mês seguinte
    inicio = mes
    if tipo != "parcelada" and dia and mes == _mes_de(hoje) and dia < hoje.day:
        inicio = mes.somar(1)
    return Proposta(
        "nova_conta",
        nome=nome,
        valor=valor,
        tipo_conta=tipo,
        parcelas=parcelas if tipo == "parcelada" else None,
        dia=dia,
        mes_inicio=inicio,
    )


def _conferir_novo_banco(resposta, contexto, hoje, mes):
    nome = _nome(resposta.get("nome"))
    if not nome:
        return _nao("Qual o nome do banco? Ex.: “adiciona o banco Inter com 500”.")
    if any(b.nome.casefold() == nome.casefold() for b in contexto.bancos):
        return _nao(f"Você já tem o banco {nome}. Pra mudar o saldo, fala “o {nome} tá com…”.")
    try:
        saldo = _valor(resposta.get("valor"), aceita_zero=True)
    except ValueError:
        return _nao("Não entendi o saldo. Fala de novo com o valor.")
    return Proposta("novo_banco", nome=nome, valor=saldo or Dinheiro.zero())


def _conferir_saldo(acao: str):
    """Somar ao saldo ou definir o saldo de um banco."""

    def conferir(resposta, contexto, hoje, mes):
        banco = _banco_falado_ou_unico(resposta, contexto)
        if banco is None:
            return _nao("Qual banco? Fala o nome do banco junto.")
        try:
            valor = _valor(resposta.get("valor"), aceita_zero=acao == "ajustar_saldo")
        except ValueError:
            valor = None
        if valor is None:
            return _nao("Qual o valor? Fala de novo com o valor.")
        novo = banco.valor + valor if acao == "somar_banco" else valor
        return Proposta(acao, banco=banco, valor=valor, saldo_novo=novo)

    return conferir


def _conferir_transferir(resposta, contexto, hoje, mes):
    origem = _achar(contexto.bancos, resposta.get("banco_id"))
    destino = _achar(contexto.bancos, resposta.get("banco_destino_id"))
    if origem is None or destino is None or origem == destino:
        return _nao("De qual banco pra qual? Ex.: “passei 300 do Nubank pra Caixa”.")
    valor = _valor_ou_none(resposta.get("valor"))
    if valor is None:
        return _nao("Quanto você passou? Fala de novo com o valor.")
    return Proposta("transferir", banco=origem, banco_destino=destino, valor=valor)


def _data_ou_none(bruto: object, hoje: date) -> date | None:
    """Data nova falada no editar; vazia ou absurda = não muda."""
    try:
        d = date.fromisoformat(str(bruto))
    except ValueError:
        return None
    if not hoje - timedelta(DIAS_PARA_TRAS) <= d <= hoje + timedelta(DIAS_PARA_FRENTE):
        return None
    return d


def _dia_ou_zero(bruto: object) -> int:
    return bruto if isinstance(bruto, int) and 1 <= bruto <= 31 else 0


def _conferir_editar(acao: str, onde: Callable[[ContextoDeVoz], tuple[Opcao, ...]], *, usa: str):
    """Editar conta (valor, dia, nome) ou ganho (valor, data, nome): só o que foi pedido muda."""

    def conferir(resposta, contexto, hoje, mes):
        p = _escolher_item(acao, resposta, onde(contexto))
        if p.acao == "nao_entendi":
            return p
        try:
            valor = _valor(resposta.get("valor"))
        except ValueError:
            return _nao("Não entendi o valor novo. Fala de novo com o valor.")
        dia = _dia_ou_zero(resposta.get("dia")) if usa == "dia" else 0
        data = _data_ou_none(resposta.get("data"), hoje) if usa == "data" else None
        nome = _nome(resposta.get("nome"))
        if p.item and nome.casefold() == p.item.nome.casefold():
            nome = ""  # repetiu o nome atual: não é renomear
        if not (valor or dia or data or nome):
            quem = p.item.nome if p.item else "isso"
            quando = "o dia" if usa == "dia" else "a data"
            return _nao(f"O que você quer mudar em {quem}? O valor, {quando} ou o nome.")
        return replace(p, valor=valor, dia=dia, data=data, nome=nome)

    return conferir


def _conferir_editar_banco(resposta, contexto, hoje, mes):
    banco = _banco_falado_ou_unico(resposta, contexto)
    if banco is None:
        return _nao("Qual banco? Fala o nome do banco junto.")
    nome = _nome(resposta.get("nome"))
    if not nome or nome.casefold() == banco.nome.casefold():
        return _nao(
            f"Qual o nome novo do {banco.nome}? Pra mudar o saldo, fala “o {banco.nome} tá com…”."
        )
    if any(b.nome.casefold() == nome.casefold() for b in contexto.bancos):
        return _nao(f"Você já tem o banco {nome}.")
    return Proposta("editar_banco", banco=banco, nome=nome)


def _conferir_apagar_conta(resposta, contexto, hoje, mes):
    p = _escolher_item("apagar_conta", resposta, contexto.cadastro)
    # conta de todo mês: a tela pergunta se para a partir do mês seguinte ou apaga de vez
    return replace(p, parar_em=mes.somar(1)) if p.acao == "apagar_conta" else p


def _conferir_apagar_ganho(resposta, contexto, hoje, mes):
    p = _escolher_item("apagar_ganho", resposta, contexto.ganhos)
    return replace(p, mensagem="Apagar estes ganhos?") if p.opcoes else p


def _conferir_apagar_banco(resposta, contexto, hoje, mes):
    # apagar é sério: só o banco que a pessoa citou (nunca o "único" por conta própria)
    banco = _banco_citado(resposta, contexto)
    if banco is None:
        return _nao("Qual banco você quer apagar? Fala o nome dele.")
    return Proposta("apagar_banco", banco=banco)


def _conferir_consulta(acao: str):
    def conferir(resposta, contexto, hoje, mes):
        # consultar_banco: o banco citado, ou None = total de todos
        return Proposta(acao, banco=_banco_citado(resposta, contexto))

    return conferir


CONFERIR: dict[str, Callable[[dict, ContextoDeVoz, date, Mes], Proposta]] = {
    "pagar_conta": _conferir_item_com_valor("pagar_conta", lambda c: c.contas),
    "receber_ganho": _conferir_item_com_valor("receber_ganho", lambda c: c.ganhos),
    "desfazer_pagamento": _conferir_desfazer,
    "novo_ganho": _conferir_novo_ganho,
    "nova_conta": _conferir_nova_conta,
    "novo_banco": _conferir_novo_banco,
    "somar_banco": _conferir_saldo("somar_banco"),
    "ajustar_saldo": _conferir_saldo("ajustar_saldo"),
    "transferir": _conferir_transferir,
    "editar_conta": _conferir_editar("editar_conta", lambda c: c.cadastro, usa="dia"),
    "editar_ganho": _conferir_editar("editar_ganho", lambda c: c.ganhos, usa="data"),
    "editar_banco": _conferir_editar_banco,
    "apagar_conta": _conferir_apagar_conta,
    "apagar_ganho": _conferir_apagar_ganho,
    "apagar_banco": _conferir_apagar_banco,
    "consultar_sobra": _conferir_consulta("consultar_sobra"),
    "consultar_falta": _conferir_consulta("consultar_falta"),
    "consultar_banco": _conferir_consulta("consultar_banco"),
}


def validar_resposta(resposta: dict, contexto: ContextoDeVoz, hoje: date, mes: Mes) -> Proposta:
    """Confere o JSON da IA contra os dados do usuário. Na dúvida, "não entendi"."""
    conferir = CONFERIR.get(resposta.get("acao"))
    return conferir(resposta, contexto, hoje, mes) if conferir else _nao()
