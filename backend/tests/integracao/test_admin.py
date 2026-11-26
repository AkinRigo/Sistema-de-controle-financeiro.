from fastapi.testclient import TestClient

from integracao.conftest import criar_app_teste

NOVO = {"nome": "Bia", "email": "Bia@Ex.com", "senha": "senha-da-bia"}


def _cliente(caixa, chave="segredo-admin"):
    return TestClient(criar_app_teste(caixa, admin_api_key=chave))


def test_admin_cria_usuario_ja_ativado(caixa):
    c = _cliente(caixa)
    r = c.post("/admin/users", json=NOVO, headers={"X-Admin-Key": "segredo-admin"})
    assert r.status_code == 201 and r.json()["email"] == "bia@ex.com"
    assert caixa.enviados == []  # sem e-mail de ativação
    login = c.post("/auth/login", json={"email": "bia@ex.com", "senha": "senha-da-bia"})
    assert login.status_code == 200
    dup = c.post("/admin/users", json=NOVO, headers={"X-Admin-Key": "segredo-admin"})
    assert dup.status_code == 409


def test_admin_exige_a_chave(caixa):
    c = _cliente(caixa)
    assert c.post("/admin/users", json=NOVO).status_code == 401
    errada = c.post("/admin/users", json=NOVO, headers={"X-Admin-Key": "outra"})
    assert errada.status_code == 401
    # token de usuário comum não serve como chave de admin
    assert (
        c.post("/admin/users", json=NOVO, headers={"Authorization": "Bearer x"}).status_code == 401
    )


def test_admin_desligado_sem_chave_configurada(caixa):
    c = _cliente(caixa, chave="")
    r = c.post("/admin/users", json=NOVO, headers={"X-Admin-Key": ""})
    assert r.status_code == 503


def test_rotas_publicas_e_protegidas(cliente):
    assert cliente.get("/").json()["status"] == "ok"
    for rota in ("/contas", "/bancos", "/ganhos", "/rendas", "/resumo/2026-11", "/backup"):
        assert cliente.get(rota).status_code == 401, rota


def test_get_current_user_e_a_dependencia_das_rotas():
    from painel.api.deps import get_current_user, obter_usuario_atual

    assert get_current_user is obter_usuario_atual


def test_usuario_admin_usa_o_proprio_login(caixa):
    from integracao.conftest import cadastrar

    app = criar_app_teste(caixa, admin_api_key="")
    c = TestClient(app)
    auth = cadastrar(c, "akin@ex.com")
    assert c.get("/auth/eu", headers=auth).json()["admin"] is False
    # usuário comum logado: proibido
    assert c.post("/admin/users", json=NOVO, headers=auth).status_code == 403

    sessao = app.state.fabrica_sessoes()
    from painel.infra.modelos import UsuarioModelo

    u = sessao.query(UsuarioModelo).filter_by(email="akin@ex.com").one()
    u.admin = True
    sessao.commit()
    sessao.close()

    assert c.get("/auth/eu", headers=auth).json()["admin"] is True
    r = c.post("/admin/users", json=NOVO, headers=auth)
    assert r.status_code == 201  # sem ADMIN_API_KEY, só com o login de admin


def test_backend_entrega_o_site_quando_configurado(caixa, tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>No Corre</title>", encoding="utf-8")
    (tmp_path / "assets" / "app-123.js").write_text("console.log(1)", encoding="utf-8")
    c = TestClient(criar_app_teste(caixa, frontend_dist=str(tmp_path)))
    r = c.get("/")
    assert r.status_code == 200 and "<title>No Corre</title>" in r.text
    assert r.headers["cache-control"] == "no-cache"
    assert c.get("/assets/app-123.js").text == "console.log(1)"
    assert c.get("/saude").json() == {"status": "ok"}  # a API continua


def test_sem_site_a_raiz_responde_json(cliente):
    assert cliente.get("/").json()["app"] == "No Corre das Notas"
