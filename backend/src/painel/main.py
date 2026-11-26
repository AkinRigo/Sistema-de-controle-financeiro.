"""Ponto de entrada para o servidor: `uvicorn painel.main:app`."""

from painel.api.app import criar_app

app = criar_app()
