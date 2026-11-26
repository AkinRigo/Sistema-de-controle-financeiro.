# HOJE nos testes é 2026-11-20.
ANTIGO = {
    "debts": [
        {
            "id": 1,
            "name": "Cartão Nubank",
            "category": "Nubank",
            "value": 250,
            "type": "installment",
            "startingRemaining": 4,
            "totalInstallments": 10,
            "dueDay": 5,
            "highInterest": True,
        },
        {"id": 2, "name": "Luz", "category": "Casa", "value": 120, "type": "fixed", "dueDay": 15},
        {"id": 3, "name": "Quitada", "type": "installment", "startingRemaining": 0, "value": 9},
        {"id": 4, "name": "Multa antiga", "type": "single", "value": 50},
    ],
    "months": {
        "2026-10": {"paidIds": [4]},
        "2026-11": {"paidIds": [2], "amounts": {"2": 130}},
    },
    "incomes": [{"id": 9, "name": "Salário", "value": 1500, "date": "2026-11-30", "pending": True}],
    "cashAccounts": [{"id": "c1", "name": "Inter", "balances": {"2026-10": 300, "2026-11": 450}}],
    "globalSim": {"weekday": 200, "weekend": 80},
}


def test_importa_backup_do_painel_antigo(cliente, auth):
    r = cliente.post("/backup", json=ANTIGO, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json() == {"bancos": 1, "contas": 2, "ganhos": 1, "pagamentos": 1, "ignorados": 0}

    contas = {c["nome"]: c for c in cliente.get("/contas", headers=auth).json()}
    assert set(contas) == {"Cartão Nubank", "Luz"}  # quitada e única já paga ficam de fora
    cartao = contas["Cartão Nubank"]
    assert (cartao["parcela_inicial"], cartao["total_parcelas"]) == (7, 10)
    assert cartao["categoria_efetiva"] == "cartoes" and cartao["juros_altos"]
    assert contas["Luz"]["valor"] == "130.00" and contas["Luz"]["categoria_efetiva"] == "casa"

    assert cliente.get("/bancos", headers=auth).json()[0]["saldo"] == "450.00"
    resumo = cliente.get("/resumo/2026-11", headers=auth).json()
    assert resumo["vai_entrar"] == "1500.00" and resumo["ja_pago"] == "130.00"
    corridas = cliente.get("/configuracoes/corridas", headers=auth).json()
    assert corridas["por_semana"] == "200.00" and not corridas["contar_na_previsao"]


def test_arquivo_qualquer_e_recusado(cliente, auth):
    r = cliente.post("/backup", json={"version": 2, "bills": "x"}, headers=auth)
    assert r.status_code == 422 and "backup" in r.json()["detail"]
