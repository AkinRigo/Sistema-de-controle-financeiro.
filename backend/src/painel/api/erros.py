"""Mensagens de validação em português, prontas para a tela mostrar."""

from typing import Any

_CAMPOS = {
    "nome": "Nome",
    "email": "E-mail",
    "senha": "Senha",
    "valor": "Valor",
    "valor_pago": "Valor pago",
    "saldo": "Saldo",
    "dia": "Dia",
    "dia_vencimento": "Vence dia",
    "data": "Data",
    "tipo": "Tipo",
    "mes": "Mês",
    "mes_inicio": "Mês",
    "mes_fim": "Mês final",
    "mes_referencia": "Mês",
    "mes_aberto": "Mês",
    "a_partir_de": "Mês",
    "parcela_inicial": "Parcela",
    "parcela_no_mes": "Parcela",
    "total_parcelas": "Total de parcelas",
    "credor": "Para quem",
    "por_semana": "Por semana",
    "por_fim_de_semana": "Por fim de semana",
}


def _campo(loc: tuple[Any, ...]) -> str:
    nomes = [str(p) for p in loc if p not in ("body", "query", "path")]
    return _CAMPOS.get(nomes[-1], nomes[-1]) if nomes else "Dados"


def mensagem(erro: dict[str, Any]) -> str:
    campo = _campo(tuple(erro.get("loc", ())))
    tipo = erro.get("type", "")
    ctx = erro.get("ctx") or {}
    if tipo == "missing":
        return f"{campo}: campo obrigatório."
    if tipo == "string_too_short":
        minimo = ctx.get("min_length", 1)
        return (
            f"{campo}: preencha este campo."
            if minimo <= 1
            else f"{campo}: mínimo {minimo} caracteres."
        )
    if tipo == "string_too_long":
        return f"{campo}: máximo {ctx.get('max_length')} caracteres."
    if tipo == "greater_than":
        return f"{campo}: precisa ser maior que {ctx.get('gt')}."
    if tipo == "greater_than_equal":
        return f"{campo}: precisa ser pelo menos {ctx.get('ge')}."
    if tipo == "less_than_equal":
        return f"{campo}: no máximo {ctx.get('le')}."
    if tipo == "decimal_max_places":
        return f"{campo}: use no máximo 2 casas decimais."
    if tipo == "decimal_max_digits":
        return f"{campo}: valor grande demais."
    if tipo.startswith(("int_", "decimal_", "float_")):
        return f"{campo}: digite um número válido."
    if tipo.startswith(("date_", "datetime_")):
        return f"{campo}: data inválida."
    if tipo == "enum":
        return f"{campo}: opção inválida."
    if tipo == "value_error":
        texto = str(erro.get("msg", "")).removeprefix("Value error, ")
        return f"{campo}: {texto}" if texto else f"{campo}: valor inválido."
    if tipo == "extra_forbidden":
        return f"Campo não esperado: {campo}."
    return f"{campo}: valor inválido."


def mensagens(erros: list[dict[str, Any]]) -> str:
    vistas: list[str] = []
    for e in erros:
        m = mensagem(e)
        if m not in vistas:
            vistas.append(m)
    return " ".join(vistas)
