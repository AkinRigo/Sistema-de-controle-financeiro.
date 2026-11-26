import pytest
from fastapi.testclient import TestClient

from integracao.conftest import cadastrar, criar_app_teste
from painel.infra.seguranca import EmissorDeTokens


@pytest.fixture
def cli(caixa):
    c = TestClient(criar_app_teste(caixa, url_frontend="http://painel.local"))
    cadastrar(c, "ana@ex.com", senha="senha-velha")
    return c


def _login(cli, senha):
    return cli.post("/auth/login", json={"email": "ana@ex.com", "senha": senha}).status_code


def test_fluxo_completo(cli, caixa):
    r = cli.post("/auth/esqueci-senha", json={"email": " ANA@ex.com "})
    assert r.status_code == 202
    assert caixa.enviados[-1]["para"] == "ana@ex.com"
    assert "http://painel.local/?redefinir=" in caixa.enviados[-1]["texto"]
    token = caixa.link("redefinir")

    r = cli.post("/auth/redefinir-senha", json={"token": token, "senha": "senha-nova-123"})
    assert r.status_code == 200 and r.json()["usuario"]["email"] == "ana@ex.com"
    assert _login(cli, "senha-velha") == 401
    assert _login(cli, "senha-nova-123") == 200

    # o mesmo link não serve de novo
    r = cli.post("/auth/redefinir-senha", json={"token": token, "senha": "outra-senha-1"})
    assert r.status_code == 400


def test_email_inexistente_responde_igual_e_nao_envia(cli, caixa):
    antes = len(caixa.enviados)
    r = cli.post("/auth/esqueci-senha", json={"email": "ninguem@ex.com"})
    assert r.status_code == 202 and len(caixa.enviados) == antes


def test_tokens_nao_se_misturam(cli, caixa):
    acesso = cli.post("/auth/login", json={"email": "ana@ex.com", "senha": "senha-velha"}).json()
    r = cli.post(
        "/auth/redefinir-senha", json={"token": acesso["token"], "senha": "senha-nova-123"}
    )
    assert r.status_code == 400

    cli.post("/auth/esqueci-senha", json={"email": "ana@ex.com"})
    r = cli.get("/bancos", headers={"Authorization": f"Bearer {caixa.link('redefinir')}"})
    assert r.status_code == 401

    falso = EmissorDeTokens(b"z" * 32, 60).emitir_redefinicao("x", "y")
    r = cli.post("/auth/redefinir-senha", json={"token": falso, "senha": "senha-nova-123"})
    assert r.status_code == 400


def test_redefinir_senha_tambem_confirma_o_email(caixa):
    c = TestClient(criar_app_teste(caixa))
    c.post("/auth/cadastro", json={"nome": "B", "email": "b@ex.com", "senha": "senha-segura"})
    c.post("/auth/esqueci-senha", json={"email": "b@ex.com"})
    r = c.post(
        "/auth/redefinir-senha", json={"token": caixa.link("redefinir"), "senha": "senha-nova-1"}
    )
    assert r.status_code == 200
    login = c.post("/auth/login", json={"email": "b@ex.com", "senha": "senha-nova-1"})
    assert login.status_code == 200


def test_falha_no_envio_nao_quebra_a_resposta():
    class Quebrado:
        def enviar(self, *a):
            raise OSError("smtp fora do ar")

    c = TestClient(criar_app_teste(Quebrado()))
    r = c.post("/auth/cadastro", json={"nome": "B", "email": "b@ex.com", "senha": "senha-segura"})
    assert r.status_code == 201
    assert c.post("/auth/esqueci-senha", json={"email": "b@ex.com"}).status_code == 202
