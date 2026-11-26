import pytest

from painel.infra.db import normalizar_url


@pytest.mark.parametrize(
    ("entrada", "saida"),
    [
        ("postgres://u:s@h/db", "postgresql+psycopg://u:s@h/db"),
        ("postgresql://u:s@h/db?sslmode=require", "postgresql+psycopg://u:s@h/db?sslmode=require"),
        ("postgresql+psycopg://u@h/db", "postgresql+psycopg://u@h/db"),
        ("sqlite:///./painel.db", "sqlite:///./painel.db"),
    ],
)
def test_normalizar_url(entrada, saida):
    assert normalizar_url(entrada) == saida
