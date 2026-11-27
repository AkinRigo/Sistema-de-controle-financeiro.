"""Categorias fixas e sugestão automática pelo texto da conta."""

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from painel.domain.entidades import Conta, Pagamento, TipoConta
from painel.domain.erros import ErroDeValidacao
from painel.domain.regras.divida import calcular_divida_conta
from painel.domain.regras.ocorrencias import obter_abertas
from painel.domain.valores import Dinheiro, Mes, somar_dinheiro

CATEGORIAS: dict[str, str] = {
    "casa": "Casa",
    "pessoas": "Devo a pessoas",
    "moto": "Locomoção",
    "cartoes": "Cartões e banco",
    "alimentacao": "Alimentação",
    "outros": "Outros",
}

_TERMOS_POR_CATEGORIA: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "moto",
        (
            "moto",
            "gasolina",
            "combustivel",
            "mobilidade",
            "ipva",
            "licenciamento",
            "oficina",
            "pneu",
            "multa",
        ),
    ),
    (
        "cartoes",
        (
            "cartao",
            "cartoes",
            "nubank",
            "neon",
            "inter",
            "banco",
            "cheque",
            "emprestimo",
            "fatura",
            "picpay",
            "mercado pago",
        ),
    ),
    (
        "casa",
        ("casa", "aluguel", "condominio", "luz", "energia", "agua", "internet", "gas", "iptu"),
    ),
    (
        "alimentacao",
        (
            "mercado",
            "aliment",
            "comida",
            "ifood",
            "feira",
            "padaria",
            "acougue",
            "lanche",
            "restaurante",
        ),
    ),
    (
        "pessoas",
        (
            "pai",
            "mae",
            "irma",
            "irmao",
            "amigo",
            "amiga",
            "tio",
            "tia",
            "primo",
            "prima",
            "avo",
            "vo",
            "namorad",
            "sogr",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class ResumoCategoria:
    falta_pagar: Dinheiro
    ja_pago: Dinheiro
    fixas_por_mes: Dinheiro
    ainda_devo: Dinheiro


def _normalizar(texto: str) -> str:
    decomposicao = unicodedata.normalize("NFD", texto.casefold())
    return "".join(caractere for caractere in decomposicao if not unicodedata.combining(caractere))


def _corresponde_a_termo(termo: str, palavras: list[str]) -> bool:
    if " " in termo:
        texto = " ".join(palavras)
        return termo in texto
    if termo in {"aliment", "namorad", "sogr"}:
        return any(palavra.startswith(termo) for palavra in palavras)
    return termo in palavras


def sugerir_categoria(nome: str, credor: str | None = None) -> str:
    """Sugere uma categoria pelo credor e nome, sem diferenciar acentos."""
    texto = _normalizar(f"{credor or ''} {nome}")
    palavras = re.findall(r"[a-z0-9]+", texto)
    for categoria, termos in _TERMOS_POR_CATEGORIA:
        if any(_corresponde_a_termo(termo, palavras) for termo in termos):
            return categoria
    return "outros"


def categoria_da_conta(conta: Conta) -> str:
    """Usa a categoria informada ou sugere uma a partir do texto."""
    if not conta.categoria:
        return sugerir_categoria(conta.nome, conta.credor)
    if conta.categoria not in CATEGORIAS:
        raise ErroDeValidacao(f"Categoria desconhecida: {conta.categoria}.")
    return conta.categoria


def resumir_categorias(
    mes: Mes,
    desde: Mes,
    contas: Iterable[Conta],
    pagamentos: Iterable[Pagamento],
) -> dict[str, ResumoCategoria]:
    """Calcula totais por categoria para o mês consultado."""
    contas_lista = tuple(contas)
    pagamentos_lista = tuple(pagamentos)
    abertas = tuple(
        aberta
        for aberta in obter_abertas(contas_lista, pagamentos_lista, mes, desde)
        if aberta.mes_origem == mes
    )
    categorias = {
        chave: {
            "falta_pagar": [],
            "ja_pago": [],
            "fixas_por_mes": [],
            "ainda_devo": [],
        }
        for chave in CATEGORIAS
    }
    contas_por_id = {conta.id: conta for conta in contas_lista}

    for aberta in abertas:
        categorias[categoria_da_conta(aberta.conta)]["falta_pagar"].append(aberta.conta.valor)
    for pagamento in pagamentos_lista:
        conta = contas_por_id.get(pagamento.conta_id)
        if conta is not None and pagamento.mes_conta == mes:
            categorias[categoria_da_conta(conta)]["ja_pago"].append(pagamento.valor_pago)
    for conta in contas_lista:
        categoria = categoria_da_conta(conta)
        if (
            conta.tipo is TipoConta.FIXA
            and conta.mes_inicio <= mes
            and (conta.mes_fim is None or mes <= conta.mes_fim)
        ):
            categorias[categoria]["fixas_por_mes"].append(conta.valor)
        categorias[categoria]["ainda_devo"].append(
            calcular_divida_conta(conta, desde, pagamentos_lista)
        )

    return {
        categoria: ResumoCategoria(
            falta_pagar=somar_dinheiro(totais["falta_pagar"]),
            ja_pago=somar_dinheiro(totais["ja_pago"]),
            fixas_por_mes=somar_dinheiro(totais["fixas_por_mes"]),
            ainda_devo=somar_dinheiro(totais["ainda_devo"]),
        )
        for categoria, totais in categorias.items()
    }
