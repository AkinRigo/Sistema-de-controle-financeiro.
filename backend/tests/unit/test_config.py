import pytest

from painel.config import Config


def test_chave_hex_e_chave_longa(monkeypatch):
    monkeypatch.setenv("PAINEL_CHAVE_TOKEN", "ab" * 32)
    assert Config.do_ambiente().chave_token == bytes.fromhex("ab" * 32)
    monkeypatch.setenv("PAINEL_CHAVE_TOKEN", "x" * 44)  # estilo base64 gerado pelo Render
    assert len(Config.do_ambiente().chave_token) == 32


def test_chave_curta_e_recusada(monkeypatch):
    monkeypatch.setenv("PAINEL_CHAVE_TOKEN", "curta")
    with pytest.raises(ValueError):
        Config.do_ambiente()


def test_smtp_e_cors_do_ambiente(monkeypatch):
    monkeypatch.setenv("PAINEL_CHAVE_TOKEN", "ab" * 32)
    monkeypatch.setenv("PAINEL_SMTP_SENHA", "abcd efgh ijkl mnop")
    monkeypatch.setenv("PAINEL_CORS_ORIGENS", "https://a.pages.dev, https://b.com")
    c = Config.do_ambiente()
    assert c.smtp_senha == "abcdefghijklmnop"
    assert c.origens_cors == ("https://a.pages.dev", "https://b.com")
