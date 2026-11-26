from integracao.conftest import cadastrar


def _criar(cliente, auth, rota, dados):
    r = cliente.post(rota, json=dados, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def _saldo(cliente, auth, banco_id):
    return next(b for b in cliente.get("/bancos", headers=auth).json() if b["id"] == banco_id)[
        "saldo"
    ]


def test_bancos_crud_e_dinheiro_como_texto(cliente, auth):
    banco = _criar(cliente, auth, "/bancos", {"nome": "Nubank", "saldo": 0.1})
    assert banco["saldo"] == "0.10"  # número JSON vira Decimal pelo texto, sem erro binário
    tres_casas = cliente.post("/bancos", json={"nome": "X", "saldo": "1.555"}, headers=auth)
    assert tres_casas.status_code == 422
    r = cliente.put(f"/bancos/{banco['id']}", json={"nome": "Nu", "saldo": "50"}, headers=auth)
    assert r.json() == {"id": banco["id"], "nome": "Nu", "saldo": "50.00"}
    assert cliente.delete(f"/bancos/{banco['id']}", headers=auth).status_code == 204
    assert cliente.get("/bancos", headers=auth).json() == []


def test_dados_isolados_por_usuario(cliente, auth):
    banco = _criar(cliente, auth, "/bancos", {"nome": "Meu", "saldo": "10"})
    outro = cadastrar(cliente, "bia@exemplo.com")
    assert cliente.get("/bancos", headers=outro).json() == []
    r = cliente.put(f"/bancos/{banco['id']}", json={"nome": "X", "saldo": "0"}, headers=outro)
    assert r.status_code == 404
    assert cliente.delete(f"/bancos/{banco['id']}", headers=outro).status_code == 404


def test_contas_validacao_do_dominio(cliente, auth):
    base = {"nome": "Celular", "valor": "100", "tipo": "parcelada", "mes_inicio": "2026-11"}
    r = cliente.post("/contas", json=base, headers=auth)
    assert r.status_code == 422  # parcelada sem parcelas
    r = cliente.post("/contas", json={**base, "tipo": "unica", "categoria": "xyz"}, headers=auth)
    assert r.status_code == 422
    r = cliente.post("/contas", json={**base, "mes_inicio": "2026-13"}, headers=auth)
    assert r.status_code == 422
    conta = _criar(cliente, auth, "/contas", {**base, "parcela_inicial": 2, "total_parcelas": 4})
    assert conta["categoria_efetiva"] == "outros"
    assert conta["ainda_devo"] == "300.00"


def test_conta_sugere_categoria_e_edita(cliente, auth):
    conta = _criar(
        cliente,
        auth,
        "/contas",
        {"nome": "Aluguel", "valor": "900", "tipo": "fixa", "mes_inicio": "2026-11"},
    )
    assert conta["categoria_efetiva"] == "casa"
    r = cliente.put(
        f"/contas/{conta['id']}",
        json={
            "nome": "Aluguel",
            "valor": "950",
            "tipo": "fixa",
            "mes_inicio": "2026-11",
            "categoria": "outros",
        },
        headers=auth,
    )
    assert r.status_code == 200
    assert r.json()["valor"] == "950.00" and r.json()["categoria_efetiva"] == "outros"
    assert len(cliente.get("/contas", headers=auth).json()) == 1


def test_pagamento_debita_banco_e_desfazer_credita(cliente, auth):
    banco = _criar(cliente, auth, "/bancos", {"nome": "Inter", "saldo": "1000"})
    conta = _criar(
        cliente,
        auth,
        "/contas",
        {"nome": "Luz", "valor": "150.50", "tipo": "fixa", "mes_inicio": "2026-10"},
    )
    pag = _criar(
        cliente,
        auth,
        "/pagamentos",
        {"conta_id": conta["id"], "mes_conta": "2026-11", "banco_id": banco["id"]},
    )
    assert pag["valor_pago"] == "150.50"
    assert pag["data_pagamento"] == "2026-11-20"
    assert _saldo(cliente, auth, banco["id"]) == "849.50"

    dup = cliente.post(
        "/pagamentos", json={"conta_id": conta["id"], "mes_conta": "2026-11"}, headers=auth
    )
    assert dup.status_code == 409
    fora = cliente.post(
        "/pagamentos", json={"conta_id": conta["id"], "mes_conta": "2026-09"}, headers=auth
    )
    assert fora.status_code == 422

    assert [p["id"] for p in cliente.get("/pagamentos?mes=2026-11", headers=auth).json()] == [
        pag["id"]
    ]
    assert cliente.get("/pagamentos?mes=2026-10", headers=auth).json() == []

    assert cliente.delete(f"/pagamentos/{pag['id']}", headers=auth).status_code == 204
    assert _saldo(cliente, auth, banco["id"]) == "1000.00"


def test_excluir_conta_apaga_pagamentos_sem_mexer_no_saldo(cliente, auth):
    banco = _criar(cliente, auth, "/bancos", {"nome": "Neon", "saldo": "100"})
    conta = _criar(
        cliente,
        auth,
        "/contas",
        {"nome": "X", "valor": "40", "tipo": "unica", "mes_inicio": "2026-11"},
    )
    _criar(
        cliente,
        auth,
        "/pagamentos",
        {
            "conta_id": conta["id"],
            "mes_conta": "2026-11",
            "banco_id": banco["id"],
            "valor_pago": "30",
        },
    )
    assert _saldo(cliente, auth, banco["id"]) == "70.00"
    assert cliente.delete(f"/contas/{conta['id']}", headers=auth).status_code == 204
    assert _saldo(cliente, auth, banco["id"]) == "70.00"
    assert cliente.get("/pagamentos", headers=auth).json() == []


def test_ganhos_recebidos_creditam_banco(cliente, auth):
    banco = _criar(cliente, auth, "/bancos", {"nome": "PicPay", "saldo": "0"})
    ganho = _criar(
        cliente,
        auth,
        "/ganhos",
        {"nome": "Freela", "valor": "200", "data": "2026-11-25", "banco_id": banco["id"]},
    )
    assert _saldo(cliente, auth, banco["id"]) == "0.00"
    dados = {
        "nome": "Freela",
        "valor": "200",
        "data": "2026-11-25",
        "banco_id": banco["id"],
        "recebido": True,
    }
    assert cliente.put(f"/ganhos/{ganho['id']}", json=dados, headers=auth).status_code == 200
    assert _saldo(cliente, auth, banco["id"]) == "200.00"
    cliente.put(f"/ganhos/{ganho['id']}", json={**dados, "valor": "250"}, headers=auth)
    assert _saldo(cliente, auth, banco["id"]) == "250.00"
    assert len(cliente.get("/ganhos", headers=auth).json()) == 1
    assert cliente.delete(f"/ganhos/{ganho['id']}", headers=auth).status_code == 204
    assert _saldo(cliente, auth, banco["id"]) == "0.00"


def test_banco_de_outro_usuario_e_recusado(cliente, auth):
    outro = cadastrar(cliente, "bia@exemplo.com")
    banco_alheio = _criar(cliente, outro, "/bancos", {"nome": "Dela", "saldo": "10"})
    r = cliente.post(
        "/ganhos",
        json={"nome": "G", "valor": "1", "data": "2026-11-01", "banco_id": banco_alheio["id"]},
        headers=auth,
    )
    assert r.status_code == 404


def test_resumo_categorias_e_divida(cliente, auth):
    _criar(cliente, auth, "/bancos", {"nome": "Inter", "saldo": "1000"})
    aluguel = _criar(
        cliente,
        auth,
        "/contas",
        {
            "nome": "Aluguel",
            "valor": "800",
            "tipo": "fixa",
            "mes_inicio": "2026-11",
            "dia_vencimento": 10,
        },
    )
    _criar(
        cliente,
        auth,
        "/contas",
        {
            "nome": "Cartão Nubank",
            "valor": "100",
            "tipo": "parcelada",
            "mes_inicio": "2026-11",
            "parcela_inicial": 1,
            "total_parcelas": 3,
            "juros_altos": True,
        },
    )
    _criar(cliente, auth, "/ganhos", {"nome": "Salário", "valor": "500", "data": "2026-11-30"})
    _criar(cliente, auth, "/pagamentos", {"conta_id": aluguel["id"], "mes_conta": "2026-11"})
    corridas = cliente.put(
        "/configuracoes/corridas",
        json={"por_semana": "70", "por_fim_de_semana": "0", "contar_na_previsao": True},
        headers=auth,
    )
    assert corridas.json()["por_semana"] == "70.00"
    assert cliente.get("/configuracoes/corridas", headers=auth).json()["contar_na_previsao"]

    r = cliente.get("/resumo/2026-11", headers=auth).json()
    # 20 a 30/11 = 11 dias -> 70 * 11 / 7 = 110
    assert r["corridas"] == "110.00"
    assert r["tenho"] == "1000.00" and r["vai_entrar"] == "500.00"
    assert r["falta_pagar"] == "100.00" and r["ja_pago"] == "800.00"
    assert r["sobra"] == "1510.00"
    assert [a["nome"] for a in r["abertas"]] == ["Cartão Nubank"]
    assert r["abertas"][0]["numero_parcela"] == 1
    assert len(r["pagas"]) == 1

    cats = {c["chave"]: c for c in cliente.get("/categorias/2026-11", headers=auth).json()}
    assert cats["casa"]["ja_pago"] == "800.00"
    assert cats["cartoes"]["ainda_devo"] == "300.00"
    assert cliente.get("/divida", headers=auth).json() == {"total": "300.00"}
    assert "casa" in cliente.get("/categorias").json()
    assert cliente.get("/resumo/2026-1", headers=auth).status_code == 422


def test_conta_antes_do_cadastro_recua_desde_e_fica_atrasada(cliente, auth):
    dados = {"nome": "Luz", "valor": "80", "tipo": "unica", "mes_inicio": "2026-09"}
    _criar(cliente, auth, "/contas", dados)
    assert cliente.get("/auth/eu", headers=auth).json()["desde"] == "2026-09"
    abertas = cliente.get("/resumo/2026-11", headers=auth).json()["abertas"]
    assert [(a["nome"], a["atrasada"], a["mes_origem"]) for a in abertas] == [
        ("Luz", True, "2026-09")
    ]
