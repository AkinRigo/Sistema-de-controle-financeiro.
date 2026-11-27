"""Rota do comando de voz com um interpretador falso (sem internet, sem gastar cota)."""

import pytest

from integracao.conftest import HOJE, criar_app_teste
from painel.domain.erros import ErroDeValidacao


class InterpretadorFalso:
    def __init__(self) -> None:
        self.resposta: dict = {}
        self.pedidos: list[str] = []

    def interpretar(self, pedido: str, esquema: dict) -> dict:
        self.pedidos.append(pedido)
        if self.resposta == "cair":
            raise ErroDeValidacao("O serviço de voz não respondeu agora. Tenta de novo.")
        return self.resposta


@pytest.fixture
def ia():
    return InterpretadorFalso()


@pytest.fixture
def app(caixa, ia):  # substitui o app do conftest: o mesmo, com a IA falsa
    aplicacao = criar_app_teste(caixa)
    aplicacao.state.interpretador = ia
    return aplicacao


def _criar(cliente, auth, rota, dados):
    r = cliente.post(rota, json=dados, headers=auth)
    assert r.status_code in (200, 201), r.text
    return r.json()


def _falar(cliente, auth, texto):
    return cliente.post("/voz/entender", json={"texto": texto, "mes": "2026-11"}, headers=auth)


def test_pagar_conta_pela_voz(cliente, auth, ia):
    nu = _criar(cliente, auth, "/bancos", {"nome": "Nubank", "saldo": "1000"})
    luz = _criar(
        cliente,
        auth,
        "/contas",
        {"nome": "Luz", "valor": "180", "tipo": "unica", "mes_inicio": "2026-11"},
    )
    ia.resposta = {
        "acao": "pagar_conta",
        "item_id": f"{luz['id']}@2026-11",
        "valor": None,
        "banco_id": None,
    }

    r = _falar(cliente, auth, "paguei a luz")

    assert r.status_code == 200, r.text
    p = r.json()
    assert p["acao"] == "pagar_conta" and p["valor"] == "180.00"
    assert p["item"]["conta_id"] == luz["id"] and p["item"]["mes_conta"] == "2026-11"
    assert p["banco"] == {"id": nu["id"], "nome": "Nubank", "saldo": "1000.00"}  # único
    assert "paguei a luz" in ia.pedidos[0] and f"{luz['id']}@2026-11" in ia.pedidos[0]


def test_ia_inventando_id_nao_passa(cliente, auth, ia):
    ia.resposta = {"acao": "pagar_conta", "item_id": "nao-existe", "valor": None, "banco_id": None}
    assert _falar(cliente, auth, "paguei a luz").json()["acao"] == "nao_entendi"


def test_quanto_sobra_quem_responde_e_o_backend(cliente, auth, ia):
    _criar(cliente, auth, "/bancos", {"nome": "Nubank", "saldo": "1234.5"})
    ia.resposta = {"acao": "consultar_sobra", "item_id": None, "valor": None, "banco_id": None}
    assert "R$ 1.234,50" in _falar(cliente, auth, "quanto sobra?").json()["mensagem"]


def test_receber_ganho_e_sobra_negativa(cliente, auth, ia):
    g = _criar(cliente, auth, "/ganhos", {"nome": "Freela", "valor": "300", "data": "2026-11-28"})
    ia.resposta = {"acao": "receber_ganho", "item_id": g["id"], "valor": None, "banco_id": None}
    p = _falar(cliente, auth, "recebi o freela").json()
    assert p["item"]["nome"] == "Freela" and p["item"]["conta_id"] is None and p["banco"] is None

    _criar(
        cliente,
        auth,
        "/contas",
        {"nome": "Aluguel", "valor": "900", "tipo": "unica", "mes_inicio": "2026-11"},
    )
    ia.resposta = {"acao": "consultar_sobra", "item_id": None, "valor": None, "banco_id": None}
    assert "faltam R$ 600,00" in _falar(cliente, auth, "e aí?").json()["mensagem"]


def test_ia_fora_do_ar_e_frase_vazia(cliente, auth, ia):
    ia.resposta = "cair"
    r = _falar(cliente, auth, "paguei a luz")
    assert r.status_code == 422 and "Tenta de novo" in r.text
    assert _falar(cliente, auth, "").status_code == 422
    assert cliente.post("/voz/entender", json={"texto": "oi", "mes": "2026-11"}).status_code == 401


def test_hoje_dos_testes():
    assert HOJE.isoformat() == "2026-11-20"


def test_vai_entrar_300(cliente, auth, ia):
    ia.resposta = {
        "acao": "novo_ganho",
        "item_id": None,
        "valor": "300",
        "banco_id": None,
        "nome": None,
        "data": None,
    }
    p = _falar(cliente, auth, "vai entrar 300 reais").json()
    assert p["acao"] == "novo_ganho" and p["valor"] == "300.00"
    assert p["nome"] == "Entrada" and p["data"] == "2026-11-20"
    assert "Hoje é 2026-11-20" in ia.pedidos[0]


def _ia(acao, **campos):
    return {"acao": acao, **campos}


def test_perguntas_respondidas_pelo_backend(cliente, auth, ia):
    nu = _criar(cliente, auth, "/bancos", {"nome": "Nubank", "saldo": "1000"})
    _criar(cliente, auth, "/bancos", {"nome": "Caixa", "saldo": "500"})
    ia.resposta = _ia("consultar_banco", banco_id=nu["id"])
    msg = _falar(cliente, auth, "quanto tenho no nubank?").json()["mensagem"]
    assert "Nubank está com R$ 1.000,00" in msg and "total, você tem R$ 1.500,00" in msg

    ia.resposta = _ia("consultar_falta")
    assert "Todas as contas" in _falar(cliente, auth, "falta pagar?").json()["mensagem"]
    for nome in ("Luz", "Água", "Gás", "Net", "Aluguel"):
        _criar(
            cliente,
            auth,
            "/contas",
            {"nome": nome, "valor": "10", "tipo": "unica", "mes_inicio": "2026-11"},
        )
    msg = _falar(cliente, auth, "quanto falta pagar?").json()["mensagem"]
    assert "R$ 50,00 em 5 contas" in msg and msg.endswith("….")


def test_desfazer_e_opcoes(cliente, auth, ia):
    luz = _criar(
        cliente,
        auth,
        "/contas",
        {"nome": "Luz", "valor": "180", "tipo": "unica", "mes_inicio": "2026-11"},
    )
    agua = _criar(
        cliente,
        auth,
        "/contas",
        {"nome": "Água", "valor": "90", "tipo": "unica", "mes_inicio": "2026-11"},
    )
    pag = _criar(cliente, auth, "/pagamentos", {"conta_id": luz["id"], "mes_conta": "2026-11"})
    ia.resposta = _ia("desfazer_pagamento", item_id=pag["id"])
    p = _falar(cliente, auth, "ainda não paguei a luz").json()
    assert p["acao"] == "desfazer_pagamento" and p["item"]["nome"] == "Luz"
    assert "Luz" in ia.pedidos[-1] and pag["id"] in ia.pedidos[-1]

    ia.resposta = _ia("pagar_conta", opcoes_ids=[f"{agua['id']}@2026-11", f"{luz['id']}@2026-11"])
    p = _falar(cliente, auth, "paguei a conta").json()
    assert p["opcoes"] == []  # a luz já está paga: sobra uma opção só, que vira o item
    assert p["item"]["nome"] == "Água"


def test_nova_conta_e_bancos(cliente, auth, ia):
    nu = _criar(cliente, auth, "/bancos", {"nome": "Nubank", "saldo": "1000"})
    cx = _criar(cliente, auth, "/bancos", {"nome": "Caixa", "saldo": "500"})
    ia.resposta = _ia("nova_conta", nome="internet", valor="120", tipo_conta="fixa", dia=10)
    p = _falar(cliente, auth, "conta de internet 120 todo mês dia 10").json()
    assert p["tipo_conta"] == "fixa" and p["mes_inicio"] == "2026-12"  # hoje é dia 20

    ia.resposta = _ia("somar_banco", banco_id=nu["id"], valor="200")
    assert _falar(cliente, auth, "coloquei 200").json()["saldo_novo"] == "1200.00"

    ia.resposta = _ia("transferir", banco_id=nu["id"], banco_destino_id=cx["id"], valor="300")
    p = _falar(cliente, auth, "passei 300").json()
    assert p["banco"]["nome"] == "Nubank" and p["banco_destino"]["nome"] == "Caixa"


def test_rota_de_transferencia(cliente, auth):
    nu = _criar(cliente, auth, "/bancos", {"nome": "Nubank", "saldo": "1000"})
    cx = _criar(cliente, auth, "/bancos", {"nome": "Caixa", "saldo": "500"})
    r = cliente.post(
        "/bancos/transferir", json={"de": nu["id"], "para": cx["id"], "valor": "300"}, headers=auth
    )
    assert r.status_code == 200, r.text
    assert [b["saldo"] for b in r.json()] == ["700.00", "800.00"]
    mesmo = {"de": nu["id"], "para": nu["id"], "valor": "1"}
    assert cliente.post("/bancos/transferir", json=mesmo, headers=auth).status_code == 422
    alheio = {"de": nu["id"], "para": "nao-existe", "valor": "1"}
    assert cliente.post("/bancos/transferir", json=alheio, headers=auth).status_code == 404
    saldos = sorted(b["saldo"] for b in cliente.get("/bancos", headers=auth).json())
    assert saldos == ["700.00", "800.00"]  # a falha não mexeu em nada


def test_editar_e_apagar_pela_voz(cliente, auth, ia):
    conta = {"valor": "260", "mes_inicio": "2026-10", "dia_vencimento": 20}
    cel = _criar(cliente, auth, "/contas", {"nome": "Celular", "tipo": "fixa", **conta})
    gas = _criar(cliente, auth, "/contas", {"nome": "Gás", "tipo": "unica", **conta})

    # a IA recebe as contas cadastradas (inclusive as que não estão em aberto)
    ia.resposta = {"acao": "apagar_conta", "item_id": cel["id"]}
    p = _falar(cliente, auth, "apaga a conta do celular").json()
    assert cel["id"] in ia.pedidos[-1] and gas["id"] in ia.pedidos[-1]
    assert p["acao"] == "apagar_conta" and p["item"]["continua"] is True
    assert p["parar_em"] == "2026-12" and p["item"]["conta_id"] is None

    ia.resposta = {"acao": "apagar_conta", "item_id": gas["id"]}
    assert _falar(cliente, auth, "apaga o gás").json()["item"]["continua"] is False

    ia.resposta = {"acao": "editar_conta", "item_id": cel["id"], "dia": 5}
    p = _falar(cliente, auth, "o celular vence dia 5").json()
    assert p["acao"] == "editar_conta" and p["dia"] == 5 and p["valor"] is None
