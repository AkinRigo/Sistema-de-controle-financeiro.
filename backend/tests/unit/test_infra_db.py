import pytest

from painel.infra.db import normalizar_url


@pytest.mark.parametrize(
    ("entrada", "saida"),
    [
        ("postgres://u:s@h/db", "postgresql+psycopg://u:s@h/db"),
        ("postgresql://u:s@h/db?sslmode=require", "postgresql+psycopg://u:s@h/db?sslmode=require"),
        ("postgresql+psycopg://u@h/db", "postgresql+psycopg://u@h/db"),
        ("sqlite:///./painel.db", "sqlite:///./painel.db"),
        # erros comuns de copiar e colar
        ("  postgresql://u:s@h/db  ", "postgresql+psycopg://u:s@h/db"),
        ("'postgresql://u:s@h/db'", "postgresql+psycopg://u:s@h/db"),
        ("PAINEL_DATABASE_URL=postgresql://u:s@h/db", "postgresql+psycopg://u:s@h/db"),
        (
            "psql 'postgresql://u:s@h/db?sslmode=require'",
            "postgresql+psycopg://u:s@h/db?sslmode=require",
        ),
    ],
)
def test_normalizar_url(entrada, saida):
    assert normalizar_url(entrada) == saida


def test_url_invalida_nao_vaza_o_valor():
    with pytest.raises(ValueError) as erro:
        normalizar_url("https://console.neon.tech/app/projects/x?senha=segredo")
    assert "segredo" not in str(erro.value)
