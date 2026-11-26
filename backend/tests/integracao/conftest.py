import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from painel.api.app import criar_app
from painel.config import Config
from painel.infra.modelos import Base

HOJE = date(2026, 11, 20)


class EnviadorFalso:
    """Caixa de entrada de mentira: guarda os e-mails em vez de enviar."""

    def __init__(self) -> None:
        self.enviados: list[dict] = []

    def enviar(self, para, assunto, texto, html):
        self.enviados.append({"para": para, "assunto": assunto, "texto": texto, "html": html})

    def link(self, parametro: str, para: str | None = None) -> str:
        """Token do e-mail mais recente (opcionalmente para um destinatário) com ?parametro=."""
        for email in reversed(self.enviados):
            if para in (None, email["para"]):
                achado = re.search(rf"{parametro}=(\S+)", email["texto"])
                if achado:
                    return achado.group(1)
        raise AssertionError(f"nenhum e-mail com {parametro}=")


def criar_app_teste(caixa: EnviadorFalso, **config):
    cfg = Config(database_url="sqlite://", chave_token=b"k" * 32, **config)
    aplicacao = criar_app(cfg, relogio=lambda: HOJE, enviador=caixa)
    Base.metadata.create_all(aplicacao.state.engine)
    return aplicacao


@pytest.fixture
def caixa() -> EnviadorFalso:
    return EnviadorFalso()


@pytest.fixture
def app(caixa):
    return criar_app_teste(caixa)


@pytest.fixture
def cliente(app) -> TestClient:
    return TestClient(app)


def cadastrar(
    cliente: TestClient,
    email: str = "ana@exemplo.com",
    senha: str = "senha-segura",
    nome: str = "Ana",
) -> dict[str, str]:
    """Cadastra, confirma pelo link do e-mail e devolve o cabeçalho de autenticação."""
    r = cliente.post("/auth/cadastro", json={"nome": nome, "email": email, "senha": senha})
    assert r.status_code == 201, r.text
    token_link = cliente.app.state.enviador.link("confirmar", para=email.strip().lower())
    r = cliente.post("/auth/confirmar-email", json={"token": token_link})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def auth(cliente) -> dict[str, str]:
    return cadastrar(cliente)
