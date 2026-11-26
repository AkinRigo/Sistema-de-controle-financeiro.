from painel.api.erros import mensagem, mensagens


def test_mensagens_em_portugues():
    assert mensagem(
        {"loc": ("body", "nome"), "type": "string_too_short", "ctx": {"min_length": 1}}
    ) == ("Nome: preencha este campo.")
    assert mensagem(
        {"loc": ("body", "senha"), "type": "string_too_short", "ctx": {"min_length": 8}}
    ) == ("Senha: mínimo 8 caracteres.")
    assert mensagem({"loc": ("body", "valor"), "type": "greater_than", "ctx": {"gt": 0}}) == (
        "Valor: precisa ser maior que 0."
    )
    assert mensagem({"loc": ("body", "valor"), "type": "decimal_max_places"}).endswith(
        "2 casas decimais."
    )
    assert (
        mensagem({"loc": ("body", "dia"), "type": "int_parsing"}) == "Dia: digite um número válido."
    )
    assert (
        mensagem({"loc": ("body", "dia"), "type": "less_than_equal", "ctx": {"le": 31}})
        == "Dia: no máximo 31."
    )
    assert mensagem({"loc": ("body", "dia"), "type": "greater_than_equal", "ctx": {"ge": 1}}) == (
        "Dia: precisa ser pelo menos 1."
    )
    assert (
        mensagem({"loc": ("body", "data"), "type": "date_from_datetime_parsing"})
        == "Data: data inválida."
    )
    assert mensagem({"loc": ("body", "tipo"), "type": "enum"}) == "Tipo: opção inválida."
    assert mensagem(
        {"loc": ("body", "email"), "type": "value_error", "msg": "Value error, E-mail inválido."}
    ) == ("E-mail: E-mail inválido.")
    assert mensagem({"loc": ("body", "x"), "type": "extra_forbidden"}) == "Campo não esperado: x."
    assert mensagem({"loc": ("body",), "type": "missing"}) == "Dados: campo obrigatório."
    assert mensagem(
        {"loc": ("body", "nome"), "type": "string_too_long", "ctx": {"max_length": 120}}
    ) == ("Nome: máximo 120 caracteres.")
    assert (
        mensagem({"loc": ("body", "valor"), "type": "decimal_max_digits"})
        == "Valor: valor grande demais."
    )
    assert mensagem({"loc": ("body", "q"), "type": "algo"}) == "q: valor inválido."
    assert (
        mensagem({"loc": ("body", "q"), "type": "value_error", "msg": ""}) == "q: valor inválido."
    )
    dois = [{"loc": ("body", "nome"), "type": "missing"}] * 2
    assert mensagens(dois) == "Nome: campo obrigatório."


def test_api_devolve_texto_em_portugues(cliente, auth):
    r = cliente.post("/bancos", json={"nome": "", "saldo": "1.555"}, headers=auth)
    assert r.status_code == 422
    assert r.json()["detail"] == "Nome: preencha este campo. Saldo: use no máximo 2 casas decimais."


def test_ganho_sem_nome_vira_ganho(cliente, auth):
    r = cliente.post("/ganhos", json={"valor": "10", "data": "2026-11-10"}, headers=auth)
    assert r.status_code == 201 and r.json()["nome"] == "Ganho"
