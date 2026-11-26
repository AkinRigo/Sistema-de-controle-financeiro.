from integracao.conftest import cadastrar

# HOJE nos testes é 2026-11-20.


def _criar(cliente, auth, rota, dados):
    r = cliente.post(rota, json=dados, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def _saldo(cliente, auth, banco_id):
    return next(b for b in cliente.get("/bancos", headers=auth).json() if b["id"] == banco_id)[
        "saldo"
    ]


def _da_renda(cliente, auth, renda_id, ate="2026-11"):
    ganhos = cliente.get(f"/ganhos?ate={ate}", headers=auth).json()
    return sorted((g for g in ganhos if g["renda_id"] == renda_id), key=lambda g: g["data"])


def test_renda_gera_um_ganho_por_mes_e_entra_no_resumo(cliente, auth):
    renda = _criar(
        cliente,
        auth,
        "/rendas",
        {"nome": "Salário", "valor": "2500", "dia": 31, "mes_inicio": "2026-10"},
    )
    assert renda["mes_inicio"] == "2026-10" and renda["valor"] == "2500.00"

    r = cliente.get("/resumo/2026-11", headers=auth).json()
    assert r["vai_entrar"] == "5000.00"  # outubro (não entrou) + novembro

    ganhos = _da_renda(cliente, auth, renda["id"], ate="2026-12")
    assert [g["data"] for g in ganhos] == ["2026-10-31", "2026-11-30", "2026-12-31"]
    assert all(not g["recebido"] and g["nome"] == "Salário" for g in ganhos)
    # consultar de novo não duplica
    assert len(_da_renda(cliente, auth, renda["id"], ate="2026-12")) == 3
    assert cliente.get("/resumo/2026-12", headers=auth).status_code == 200
    assert len(_da_renda(cliente, auth, renda["id"], ate="2026-12")) == 3


def test_criar_sem_mes_comeca_no_mes_atual(cliente, auth):
    renda = _criar(cliente, auth, "/rendas", {"nome": "Pensão", "valor": "300", "dia": 5})
    assert renda["mes_inicio"] == "2026-11"
    assert cliente.get("/rendas", headers=auth).json()[0]["nome"] == "Pensão"


def test_receber_credita_banco_e_editar_so_muda_pendentes(cliente, auth):
    banco = _criar(cliente, auth, "/bancos", {"nome": "Nubank", "saldo": "0"})
    renda = _criar(
        cliente,
        auth,
        "/rendas",
        {
            "nome": "Salário",
            "valor": "2000",
            "dia": 5,
            "mes_inicio": "2026-10",
            "banco_id": banco["id"],
        },
    )
    outubro, novembro = _da_renda(cliente, auth, renda["id"])
    recebido = {**outubro, "recebido": True}
    for k in ("id", "renda_id"):
        recebido.pop(k)
    r = cliente.put(f"/ganhos/{outubro['id']}", json=recebido, headers=auth)
    assert r.status_code == 200
    assert _saldo(cliente, auth, banco["id"]) == "2000.00"

    r = cliente.put(
        f"/rendas/{renda['id']}",
        json={"nome": "Salário novo", "valor": "2600", "dia": 10, "banco_id": banco["id"]},
        headers=auth,
    )
    assert r.status_code == 200
    outubro2, novembro2 = _da_renda(cliente, auth, renda["id"])
    assert outubro2["valor"] == "2000.00" and outubro2["nome"] == "Salário"  # já recebido
    assert novembro2["valor"] == "2600.00" and novembro2["data"] == "2026-11-10"


def test_excluir_apaga_pendentes_e_mantem_recebidos(cliente, auth):
    renda = _criar(
        cliente,
        auth,
        "/rendas",
        {"nome": "Bico", "valor": "100", "dia": 1, "mes_inicio": "2026-09"},
    )
    setembro, *_ = _da_renda(cliente, auth, renda["id"])
    dados = {k: v for k, v in setembro.items() if k not in ("id", "renda_id")}
    cliente.put(f"/ganhos/{setembro['id']}", json={**dados, "recebido": True}, headers=auth)

    assert cliente.delete(f"/rendas/{renda['id']}", headers=auth).status_code == 204
    assert cliente.get("/rendas", headers=auth).json() == []
    sobraram = cliente.get("/ganhos?ate=2026-12", headers=auth).json()
    assert [(g["nome"], g["recebido"]) for g in sobraram] == [("Bico", True)]


def test_renda_de_outro_usuario_e_banco_alheio(cliente, auth):
    renda = _criar(cliente, auth, "/rendas", {"nome": "X", "valor": "1", "dia": 1})
    outro = cadastrar(cliente, "bia@exemplo.com")
    assert cliente.delete(f"/rendas/{renda['id']}", headers=outro).status_code == 404
    banco_alheio = _criar(cliente, outro, "/bancos", {"nome": "Dela", "saldo": "1"})
    r = cliente.post(
        "/rendas",
        json={"nome": "Y", "valor": "1", "dia": 1, "banco_id": banco_alheio["id"]},
        headers=auth,
    )
    assert r.status_code == 404
    assert (
        cliente.post(
            "/rendas", json={"nome": "Z", "valor": "1", "dia": 32}, headers=auth
        ).status_code
        == 422
    )


def test_backup_leva_as_rendas(cliente, auth):
    renda = _criar(
        cliente,
        auth,
        "/rendas",
        {"nome": "Salário", "valor": "1500", "dia": 5, "mes_inicio": "2026-10"},
    )
    _da_renda(cliente, auth, renda["id"])  # gera outubro e novembro
    exportado = cliente.get("/backup", headers=auth).json()
    assert [r["name"] for r in exportado["fixedIncomes"]] == ["Salário"]

    assert cliente.post("/backup", json=exportado, headers=auth).status_code == 200
    novas = cliente.get("/rendas", headers=auth).json()
    assert len(novas) == 1
    ganhos = _da_renda(cliente, auth, novas[0]["id"])
    assert [g["data"] for g in ganhos] == ["2026-10-05", "2026-11-05"]  # sem duplicar
