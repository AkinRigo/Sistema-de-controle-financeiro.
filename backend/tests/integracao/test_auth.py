from painel.infra.seguranca import EmissorDeTokens


def _cadastro(cliente, email="ana@exemplo.com", senha="senha-segura"):
    return cliente.post("/auth/cadastro", json={"nome": "Ana", "email": email, "senha": senha})


def _login(cliente, email="ana@exemplo.com", senha="senha-segura"):
    return cliente.post("/auth/login", json={"email": email, "senha": senha})


def test_cadastro_manda_email_e_so_entra_depois_de_confirmar(cliente, caixa):
    r = _cadastro(cliente, email="  ANA@Exemplo.com ")
    assert r.status_code == 201
    assert "token" not in r.json() and "ana@exemplo.com" in r.json()["detail"]
    assert caixa.enviados[-1]["para"] == "ana@exemplo.com"
    assert "Ativar minha conta" in caixa.enviados[-1]["html"]

    nao_confirmado = _login(cliente)
    assert nao_confirmado.status_code == 403 and "Confirme" in nao_confirmado.json()["detail"]

    r = cliente.post("/auth/confirmar-email", json={"token": caixa.link("confirmar")})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["usuario"]["desde"] == "2026-11"
    eu = cliente.get("/auth/eu", headers={"Authorization": f"Bearer {corpo['token']}"})
    assert eu.status_code == 200 and eu.json()["nome"] == "Ana"
    assert _login(cliente).status_code == 200

    # clicar de novo no mesmo link não atrapalha
    again = cliente.post("/auth/confirmar-email", json={"token": caixa.link("confirmar")})
    assert again.status_code == 200


def test_confirmar_recusa_token_invalido_ou_de_outro_tipo(cliente, auth, app):
    assert cliente.post("/auth/confirmar-email", json={"token": "lixo"}).status_code == 400
    acesso = auth["Authorization"].removeprefix("Bearer ")
    assert cliente.post("/auth/confirmar-email", json={"token": acesso}).status_code == 400
    sumido = app.state.emissor.emitir_confirmacao("nao-existe")
    assert cliente.post("/auth/confirmar-email", json={"token": sumido}).status_code == 400
    # e o token de confirmação não serve como login
    _cadastro(cliente, email="bia@exemplo.com")
    confirmacao = app.state.enviador.link("confirmar", para="bia@exemplo.com")
    r = cliente.get("/bancos", headers={"Authorization": f"Bearer {confirmacao}"})
    assert r.status_code == 401


def test_reenviar_confirmacao(cliente, caixa, auth):
    _cadastro(cliente, email="bia@exemplo.com")
    antes = len(caixa.enviados)
    padrao = "Se essa conta ainda não foi ativada, enviamos um novo link."
    for email in ("bia@exemplo.com", "ana@exemplo.com", "ninguem@exemplo.com"):
        r = cliente.post("/auth/reenviar-confirmacao", json={"email": email})
        assert r.status_code == 202 and r.json()["detail"] == padrao
    # só a conta não confirmada recebeu e-mail novo
    assert [e["para"] for e in caixa.enviados[antes:]] == ["bia@exemplo.com"]


def test_cadastro_recusa_email_duplicado_e_invalido(cliente, auth):
    assert _cadastro(cliente).status_code == 409
    assert _cadastro(cliente, email="sem-arroba").status_code == 422
    assert _cadastro(cliente, email="b@b.com", senha="curta").status_code == 422


def test_login(cliente, auth):
    ok = _login(cliente, email="ANA@exemplo.com")
    assert ok.status_code == 200 and ok.json()["token"]
    assert _login(cliente, senha="outra-senha").status_code == 401
    assert _login(cliente, email="x@x.com").status_code == 401


def test_rotas_protegidas_exigem_token_valido(cliente, app):
    assert cliente.get("/bancos").status_code == 401
    assert cliente.get("/bancos", headers={"Authorization": "Bearer lixo"}).status_code == 401
    outra_chave = EmissorDeTokens(b"z" * 32, 60).emitir("qualquer")
    r = cliente.get("/bancos", headers={"Authorization": f"Bearer {outra_chave}"})
    assert r.status_code == 401
    usuario_inexistente = app.state.emissor.emitir("nao-existe")
    r = cliente.get("/bancos", headers={"Authorization": f"Bearer {usuario_inexistente}"})
    assert r.status_code == 401


def test_saude(cliente):
    assert cliente.get("/saude").json() == {"status": "ok"}
