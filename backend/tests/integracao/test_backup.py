BACKUP = {
    "version": 2,
    "since": "2026-10",
    "accounts": [{"id": "a1", "name": "Nubank", "balance": 1234.5}],
    "incomes": [
        {
            "id": "i1",
            "name": "Salário",
            "value": 2000,
            "date": "2026-11-05",
            "received": True,
            "accountId": "a1",
        },
        {
            "id": "i2",
            "name": "FGTS",
            "value": 300.1,
            "date": "2026-11-28",
            "received": False,
            "accountId": None,
        },
    ],
    "bills": [
        {
            "id": "b1",
            "name": "Aluguel",
            "creditor": "Casa",
            "value": 900,
            "dueDay": 10,
            "type": "fixed",
            "startMonth": "2026-10",
            "endMonth": None,
            "startNumber": 1,
            "total": 1,
            "highInterest": False,
            "uncertain": False,
            "group": "casa",
        },
        {
            "id": "b2",
            "name": "Celular",
            "creditor": "Jayanne",
            "value": 150,
            "dueDay": 0,
            "type": "installment",
            "startMonth": "2026-10",
            "endMonth": None,
            "startNumber": 3,
            "total": 5,
            "highInterest": True,
            "uncertain": True,
            "group": "pessoas",
        },
    ],
    "payments": {
        "2026-10": {"b1": {"amount": 900, "accountId": "a1", "date": "2026-10-10"}},
        "2026-11": {
            "b2": {"amount": 150, "accountId": None, "date": "2026-11-03"},
            "inexistente": {"amount": 1, "accountId": None, "date": "2026-11-03"},
        },
        "2026-09": {"b1": {"amount": 900, "accountId": None, "date": "2026-09-10"}},
    },
    "sim": {"weekday": 350, "weekend": 120, "on": True},
    "theme": "dark",
}


def test_importar_e_exportar_ida_e_volta(cliente, auth):
    cliente.post("/bancos", json={"nome": "Antigo", "saldo": "1"}, headers=auth)
    r = cliente.post("/backup", json=BACKUP, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json() == {"bancos": 1, "contas": 2, "ganhos": 2, "pagamentos": 2, "ignorados": 2}

    bancos = cliente.get("/bancos", headers=auth).json()
    assert [(b["nome"], b["saldo"]) for b in bancos] == [("Nubank", "1234.50")]  # sem re-somar
    contas = {c["nome"]: c for c in cliente.get("/contas", headers=auth).json()}
    assert contas["Celular"]["incerto"] and contas["Celular"]["credor"] == "Jayanne"
    assert contas["Aluguel"]["credor"] is None  # "Casa" era só o nome da categoria
    assert contas["Celular"]["ainda_devo"] == "300.00"  # parcelas 3..5, a 4 (nov) paga
    assert cliente.get("/auth/eu", headers=auth).json()["desde"] == "2026-10"
    assert cliente.get("/configuracoes/corridas", headers=auth).json()["por_semana"] == "350.00"

    exportado = cliente.get("/backup", headers=auth).json()
    assert exportado["since"] == "2026-10"
    assert {b["name"] for b in exportado["bills"]} == {"Aluguel", "Celular"}
    assert sum(len(v) for v in exportado["payments"].values()) == 2
    banco_id = exportado["accounts"][0]["id"]
    assert exportado["incomes"][0]["accountId"] in {banco_id, None}

    # reimportar o próprio export não duplica nada
    r2 = cliente.post("/backup", json=exportado, headers=auth)
    assert r2.json()["contas"] == 2 and r2.json()["ignorados"] == 0
    assert len(cliente.get("/contas", headers=auth).json()) == 2


def test_importacao_invalida_nao_apaga_nada(cliente, auth):
    cliente.post("/bancos", json={"nome": "Fica", "saldo": "5"}, headers=auth)
    ruim = {**BACKUP, "bills": [{**BACKUP["bills"][1], "startNumber": 9}]}
    r = cliente.post("/backup", json=ruim, headers=auth)
    assert r.status_code == 422 and "Celular" in r.json()["detail"]
    assert [b["nome"] for b in cliente.get("/bancos", headers=auth).json()] == ["Fica"]
    assert cliente.post("/backup", json={**BACKUP, "version": 1}, headers=auth).status_code == 422
