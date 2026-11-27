"""Regras que saíram da tela e agora a API devolve prontas. HOJE = 2026-11-20."""


def _criar(cliente, auth, rota, dados):
    r = cliente.post(rota, json=dados, headers=auth)
    assert r.status_code in (200, 201), r.text
    return r.json()


def _conta(nome, **extra):
    base = {"nome": nome, "valor": "100", "tipo": "unica", "mes_inicio": "2026-11"}
    return {**base, **extra}


def test_resumo_traz_vencimento_cobertura_parcela_e_divida(cliente, auth):
    _criar(cliente, auth, "/bancos", {"nome": "Nu", "saldo": "50"})
    _criar(cliente, auth, "/contas", _conta("Luz", dia_vencimento=25))
    parcelada = _criar(
        cliente,
        auth,
        "/contas",
        _conta(
            "Celular", tipo="parcelada", mes_inicio="2026-10", parcela_inicial=2, total_parcelas=4
        ),
    )
    _criar(cliente, auth, "/pagamentos", {"conta_id": parcelada["id"], "mes_conta": "2026-11"})

    r = cliente.get("/resumo/2026-11", headers=auth).json()
    luz = next(a for a in r["abertas"] if a["nome"] == "Luz")
    assert luz["vence_em_dias"] == 5
    atrasada = next(a for a in r["abertas"] if a["nome"] == "Celular")
    assert atrasada["atrasada"] and atrasada["vence_em_dias"] is None
    assert r["pagas"][0]["numero_parcela"] == 3
    # 50 no banco cobrem 25% dos 200 em aberto (luz + parcela atrasada)
    assert r["cobertura"] == 25
    assert r["divida_total"] == "300.00"  # luz 100 + celular out 100 + dez 100
    proximo = cliente.get("/resumo/2026-12", headers=auth).json()
    assert all(a["vence_em_dias"] is None for a in proximo["abertas"])


def test_categorias_trazem_itens(cliente, auth):
    _criar(cliente, auth, "/contas", _conta("Aluguel", tipo="fixa", valor="900"))
    _criar(
        cliente,
        auth,
        "/contas",
        _conta(
            "Air fryer",
            categoria="pessoas",
            credor="Irmã",
            tipo="parcelada",
            valor="89.90",
            parcela_inicial=3,
            total_parcelas=8,
        ),
    )
    cats = {c["chave"]: c for c in cliente.get("/categorias/2026-11", headers=auth).json()}
    assert [(i["nome"], i["valor"], i["tipo"]) for i in cats["casa"]["itens"]] == [
        ("Aluguel", "900.00", "fixa")
    ]
    air = cats["pessoas"]["itens"][0]
    assert air["parcelas_restantes"] == 6 and air["total_parcelas"] == 8
    assert air["valor"] == "539.40" and air["valor_parcela"] == "89.90"
    assert air["credor"] == "Irmã"


def test_ganhos_do_mes_receber_e_desfazer(cliente, auth):
    banco = _criar(cliente, auth, "/bancos", {"nome": "Nu", "saldo": "0"})
    out = _criar(cliente, auth, "/ganhos", {"nome": "Bico", "valor": "80", "data": "2026-10-03"})
    _criar(cliente, auth, "/ganhos", {"nome": "Freela", "valor": "200", "data": "2026-11-28"})
    _criar(cliente, auth, "/ganhos", {"nome": "Dez", "valor": "1", "data": "2026-12-01"})

    lista = cliente.get("/ganhos/mes/2026-11", headers=auth).json()
    assert [(g["nome"], g["atrasado"]) for g in lista] == [("Freela", False), ("Bico", True)]

    r = cliente.post(
        f"/ganhos/{out['id']}/receber",
        json={"valor": "90", "banco_id": banco["id"], "mes_aberto": "2026-11"},
        headers=auth,
    ).json()
    assert r["recebido"] and r["valor"] == "90.00" and r["data"] == "2026-11-20"
    saldo = cliente.get("/bancos", headers=auth).json()[0]["saldo"]
    assert saldo == "90.00"

    r = cliente.post(f"/ganhos/{out['id']}/desfazer", headers=auth).json()
    assert not r["recebido"] and r["banco_id"] is None
    assert cliente.get("/bancos", headers=auth).json()[0]["saldo"] == "0.00"


def test_editar_pelo_mes_aberto_e_parar(cliente, auth):
    c = _criar(
        cliente,
        auth,
        "/contas",
        _conta("TV", tipo="parcelada", mes_inicio="2026-09", parcela_inicial=1, total_parcelas=8),
    )
    dados = _conta(
        "TV",
        tipo="parcelada",
        mes_inicio="2026-09",
        total_parcelas=8,
        mes_referencia="2026-11",
        parcela_no_mes=4,
    )
    r = cliente.put(f"/contas/{c['id']}", json=dados, headers=auth).json()
    assert (r["mes_inicio"], r["parcela_inicial"]) == ("2026-09", 2)
    ruim = {**dados, "parcela_no_mes": 9}
    assert cliente.put(f"/contas/{c['id']}", json=ruim, headers=auth).status_code == 422

    virou_fixa = _conta("TV", tipo="fixa", mes_inicio="2026-09", mes_referencia="2026-11")
    r = cliente.put(f"/contas/{c['id']}", json=virou_fixa, headers=auth).json()
    assert r["tipo"] == "fixa" and r["mes_inicio"] == "2026-11"

    r = cliente.post(f"/contas/{c['id']}/parar", json={"a_partir_de": "2026-12"}, headers=auth)
    assert r.status_code == 200 and r.json()["mes_fim"] == "2026-11"
    r = cliente.post(f"/contas/{c['id']}/parar", json={"a_partir_de": "2026-11"}, headers=auth)
    assert r.status_code == 422


def test_criar_parcelada_pelo_mes_aberto(cliente, auth):
    dados = _conta(
        "Geladeira",
        tipo="parcelada",
        total_parcelas=10,
        mes_referencia="2026-11",
        parcela_no_mes=3,
    )
    r = _criar(cliente, auth, "/contas", dados)
    assert (r["mes_inicio"], r["parcela_inicial"]) == ("2026-11", 3)


def test_corridas_estimativa_do_mes(cliente, auth):
    cliente.put(
        "/configuracoes/corridas",
        json={"por_semana": "70", "por_fim_de_semana": "0", "contar_na_previsao": False},
        headers=auth,
    )
    r = cliente.get("/configuracoes/corridas?mes=2026-11", headers=auth).json()
    assert r["estimativa_mes"] == "110.00"  # 11 dias restantes de novembro
    assert cliente.get("/configuracoes/corridas", headers=auth).json()["estimativa_mes"] is None


def test_saldo_diario_do_mes(cliente, auth):
    _criar(cliente, auth, "/bancos", {"nome": "Nu", "saldo": "1000"})
    _criar(cliente, auth, "/contas", _conta("Aluguel", valor="700", dia_vencimento=25))
    _criar(cliente, auth, "/ganhos", {"nome": "Freela", "valor": "300", "data": "2026-11-28"})

    r = cliente.get("/saldo-diario/2026-11", headers=auth).json()
    assert r["hoje"] == 20 and len(r["dias"]) == 30
    dias = {d["dia"]: d for d in r["dias"]}
    assert dias[20]["saldo"] == "1000.00" and not dias[20]["previsao"]
    assert dias[25]["saldo"] == "300.00" and dias[25]["movimentos"][0]["nome"] == "Aluguel"
    assert dias[30]["saldo"] == "600.00"
    assert r["menor"]["dia"] == 25
    assert cliente.get("/saldo-diario/2026-13", headers=auth).status_code == 422
