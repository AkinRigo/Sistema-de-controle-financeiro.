import pytest
from fastapi.testclient import TestClient

from integracao.conftest import EnviadorFalso, cadastrar, criar_app_teste
from painel.infra.modelos import UsuarioModelo


@pytest.fixture
def central(caixa):
    """App de teste com um admin (akin) e uma usuária comum (bia)."""
    app = criar_app_teste(caixa, url_frontend="http://painel.local")
    c = TestClient(app)
    admin = cadastrar(c, "akin@ex.com", nome="Akin")
    comum = cadastrar(c, "bia@ex.com", nome="Bia")
    with app.state.fabrica_sessoes() as s:
        s.query(UsuarioModelo).filter_by(email="akin@ex.com").one().admin = True
        s.commit()
    return app, c, admin, comum


def _id(c, admin, email):
    lista = c.get("/admin/usuarios", headers=admin).json()["usuarios"]
    return next(u["id"] for u in lista if u["email"] == email)


def _login(c, email, senha="senha-segura"):
    return c.post("/auth/login", json={"email": email, "senha": senha})


def test_so_admin_acessa(central):
    _, c, admin, comum = central
    assert c.get("/admin/usuarios", headers=comum).status_code == 403
    assert c.get("/admin/indicadores").status_code in (401, 503)
    assert c.get("/admin/usuarios", headers=admin).status_code == 200


def test_login_gera_logs_e_alerta_de_tentativas(central):
    _, c, admin, _ = central
    assert _login(c, "bia@ex.com").status_code == 200
    for _ in range(5):
        assert _login(c, "bia@ex.com", "errada-123").status_code == 401
    logs = c.get("/admin/logs?tipo=acesso", headers=admin).json()
    acoes = [log["acao"] for log in logs["logs"]]
    assert acoes.count("login_falhou") == 5 and "muitas_tentativas" in acoes
    assert "login_ok" in acoes
    assert logs["contagem"]["erro"] == 1 and logs["contagem"]["aviso"] == 5
    assert logs["logs"][0]["quando"].startswith("hoje ")

    so_erros = c.get("/admin/logs?nivel=erro", headers=admin).json()["logs"]
    assert [log["acao"] for log in so_erros] == ["muitas_tentativas"]
    busca = c.get("/admin/logs?busca=bia@ex.com", headers=admin).json()["logs"]
    assert all(log["email"] == "bia@ex.com" for log in busca)

    lista = c.get("/admin/usuarios", headers=admin).json()["usuarios"]
    bia = next(u for u in lista if u["email"] == "bia@ex.com")
    assert "5 senhas erradas em 24 h" in bia["detalhe"]
    ind = c.get("/admin/indicadores", headers=admin).json()
    assert [p["email"] for p in ind["pendencias"]] == ["bia@ex.com"]


def test_desativar_reativar_e_ativar(central, caixa):
    _, c, admin, comum = central
    bia = _id(c, admin, "bia@ex.com")
    r = c.post(f"/admin/usuarios/{bia}/desativar", headers=admin)
    assert r.status_code == 200 and "desativado" in r.json()["detail"]
    assert c.get("/contas", headers=comum).status_code == 401  # token antigo não serve
    negado = _login(c, "bia@ex.com")
    assert negado.status_code == 423 and "desativada" in negado.json()["detail"]
    assert c.get("/admin/logs?nivel=erro", headers=admin).json()["logs"][0]["acao"] == (
        "login_desativado"
    )
    assert c.post(f"/admin/usuarios/{bia}/reativar", headers=admin).status_code == 200
    assert _login(c, "bia@ex.com").status_code == 200

    akin = _id(c, admin, "akin@ex.com")
    assert c.post(f"/admin/usuarios/{akin}/desativar", headers=admin).status_code == 422

    # quem não ativou o e-mail: o admin ativa na mão
    c.post("/auth/cadastro", json={"nome": "Cris", "email": "cris@ex.com", "senha": "senha-segura"})
    cris = _id(c, admin, "cris@ex.com")
    lista = c.get("/admin/usuarios?status=nao_ativou", headers=admin).json()
    assert [u["email"] for u in lista["usuarios"]] == ["cris@ex.com"]
    assert lista["contagem"]["nao_ativou"] == 1
    antes = len(caixa.enviados)
    c.post(f"/admin/usuarios/{cris}/reenviar-ativacao", headers=admin)
    assert len(caixa.enviados) == antes + 1
    assert c.post(f"/admin/usuarios/{cris}/ativar", headers=admin).status_code == 200
    assert _login(c, "cris@ex.com").status_code == 200

    c.post(f"/admin/usuarios/{cris}/nova-senha", headers=admin)
    assert "redefinir=" in caixa.enviados[-1]["texto"]
    assert c.post("/admin/usuarios/nao-existe/ativar", headers=admin).status_code == 404


def test_convite_do_envio_ao_aceite(central, caixa):
    _, c, admin, _ = central
    r = c.post("/admin/convites", json={"nome": "Dani", "email": "Dani@Ex.com"}, headers=admin)
    assert r.status_code == 201
    email = caixa.enviados[-1]
    assert email["para"] == "dani@ex.com"
    assert email["assunto"] == "Você recebeu um convite especial para o No Corre das Notas"
    assert "convite especial" in email["texto"] and "sem custo nenhum" in email["texto"]
    assert "http://painel.local/?convite=" in email["texto"]

    lista = c.get("/admin/usuarios?status=convidado", headers=admin).json()["usuarios"]
    assert [(u["nome"], u["tipo"]) for u in lista] == [("Dani", "convite")]
    # convidar de novo o mesmo e-mail reaproveita o convite
    c.post("/admin/convites", json={"nome": "Daniela", "email": "dani@ex.com"}, headers=admin)
    lista = c.get("/admin/usuarios?status=convidado", headers=admin).json()["usuarios"]
    assert [u["nome"] for u in lista] == ["Daniela"]

    token = caixa.link("convite")
    assert c.get(f"/auth/convite/{token}").json() == {"nome": "Daniela", "email": "dani@ex.com"}
    r = c.post("/auth/aceitar-convite", json={"token": token, "senha": "senha-da-dani"})
    assert r.status_code == 201 and r.json()["usuario"]["email"] == "dani@ex.com"
    assert _login(c, "dani@ex.com", "senha-da-dani").status_code == 200
    # usado: não vale de novo e sai da lista de convites
    assert c.get(f"/auth/convite/{token}").status_code == 400
    contagem = c.get("/admin/usuarios", headers=admin).json()["contagem"]
    assert contagem["convidado"] == 0

    ja_tem = c.post("/admin/convites", json={"nome": "Bia", "email": "bia@ex.com"}, headers=admin)
    assert ja_tem.status_code == 409


def test_cancelar_e_reenviar_convite(central, caixa):
    _, c, admin, _ = central
    c.post("/admin/convites", json={"nome": "Eva", "email": "eva@ex.com"}, headers=admin)
    convite = c.get("/admin/usuarios?status=convidado", headers=admin).json()["usuarios"][0]
    antes = len(caixa.enviados)
    assert c.post(f"/admin/convites/{convite['id']}/reenviar", headers=admin).status_code == 200
    assert len(caixa.enviados) == antes + 1
    token = caixa.link("convite")
    assert c.delete(f"/admin/convites/{convite['id']}", headers=admin).status_code == 200
    r = c.post("/auth/aceitar-convite", json={"token": token, "senha": "senha-da-eva"})
    assert r.status_code == 400
    assert c.delete(f"/admin/convites/{convite['id']}", headers=admin).status_code == 404


def test_indicadores(central):
    _, c, admin, _ = central
    _login(c, "bia@ex.com")
    _login(c, "akin@ex.com")
    ind = c.get("/admin/indicadores?dias=7", headers=admin).json()
    assert len(ind["dias"]) == len(ind["logins"]) == len(ind["cadastros"]) == len(ind["erros"]) == 7
    assert ind["logins"][-1] == 2 and ind["logins_7d"] == 2
    assert ind["cadastros"][-1] == 2
    assert ind["usuarios_ativos"] == 2 and ind["nao_ativaram"] == 0
    assert ind["logins_7d_variacao"] is None  # sem semana anterior para comparar
    assert c.get("/admin/indicadores?dias=3", headers=admin).status_code == 422


def test_erro_inesperado_vira_log_e_resposta_clara(caixa):
    app = criar_app_teste(caixa)

    @app.get("/_quebra")
    def quebra():
        raise RuntimeError("algo explodiu")

    c = TestClient(app)
    r = c.get("/_quebra")
    assert r.status_code == 500 and "Código: req_" in r.json()["detail"]
    assert r.headers["X-Request-Id"].startswith("req_")
    admin = cadastrar(c, "akin@ex.com")
    with app.state.fabrica_sessoes() as s:
        s.query(UsuarioModelo).filter_by(email="akin@ex.com").one().admin = True
        s.commit()
    log = c.get("/admin/logs?tipo=sistema", headers=admin).json()["logs"][0]
    assert log["codigo"] == 500 and "RuntimeError" in log["detalhe"]
    assert log["requisicao"] == r.headers["X-Request-Id"]


def test_falha_no_envio_de_email_vira_log():
    class Quebrado(EnviadorFalso):
        def enviar(self, *a):
            raise OSError("smtp fora do ar")

    app = criar_app_teste(Quebrado())
    c = TestClient(app)
    c.post("/auth/cadastro", json={"nome": "F", "email": "f@ex.com", "senha": "senha-segura"})
    with app.state.fabrica_sessoes() as s:
        from painel.infra.modelos import EventoModelo

        erro = s.query(EventoModelo).filter_by(acao="email_falhou").one()
        assert erro.tipo == "email" and erro.email == "f@ex.com" and "OSError" in erro.detalhe
