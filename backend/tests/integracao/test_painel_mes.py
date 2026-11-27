"""GET /painel/{mes}: uma chamada só, com o MESMO conteúdo das rotas separadas."""


def _criar(cliente, auth, rota, dados):
    r = cliente.post(rota, json=dados, headers=auth)
    assert r.status_code in (200, 201), r.text
    return r.json()


def test_painel_igual_as_rotas_separadas(cliente, auth):
    nu = _criar(cliente, auth, "/bancos", {"nome": "Nu", "saldo": "1000"})
    _criar(cliente, auth, "/bancos", {"nome": "Caixa", "saldo": "50"})
    conta = {"valor": "700", "mes_inicio": "2026-10", "dia_vencimento": 25}
    luz = _criar(cliente, auth, "/contas", {"nome": "Luz", "tipo": "fixa", **conta})
    _criar(cliente, auth, "/contas", {"nome": "Aluguel", "tipo": "unica", **conta})
    _criar(cliente, auth, "/ganhos", {"nome": "Freela", "valor": "300", "data": "2026-11-28"})
    _criar(
        cliente,
        auth,
        "/rendas",
        {"nome": "Salário", "valor": "2000", "dia": 5, "banco_id": nu["id"]},
    )
    _criar(
        cliente,
        auth,
        "/pagamentos",
        {"conta_id": luz["id"], "mes_conta": "2026-10", "valor_pago": "700", "banco_id": nu["id"]},
    )

    r = cliente.get("/painel/2026-11", headers=auth)
    assert r.status_code == 200, r.text
    p = r.json()

    def get(rota):
        return cliente.get(rota, headers=auth).json()

    assert p["resumo"] == get("/resumo/2026-11")
    assert p["usuario"] == get("/auth/eu")
    assert p["contas"] == get("/contas")
    assert p["bancos"] == get("/bancos")
    assert p["rendas"] == get("/rendas")
    assert p["corridas"] == get("/configuracoes/corridas?mes=2026-11")
    assert p["categorias"] == get("/categorias/2026-11")
    por_id = lambda xs: sorted(xs, key=lambda x: x["id"])  # noqa: E731
    assert por_id(p["ganhos"]) == por_id(get("/ganhos/mes/2026-11"))
    assert any(g["nome"] == "Salário" for g in p["ganhos"])  # renda fixa gerada pelo painel


def test_painel_mes_invalido_e_sem_login(cliente, auth):
    assert cliente.get("/painel/2026-13", headers=auth).status_code == 422
    assert cliente.get("/painel/2026-11").status_code == 401
