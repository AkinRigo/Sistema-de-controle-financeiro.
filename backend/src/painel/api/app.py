"""Fábrica da aplicação FastAPI."""

from collections.abc import Callable
from datetime import date

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from painel.api.rotas import auth, backup, cadastros, relatorios
from painel.config import Config
from painel.domain.erros import ErroDeValidacao
from painel.infra.db import criar_engine, criar_fabrica_sessoes
from painel.infra.email import EnviadorDeEmail, EnviadorSmtp, EnviadorTerminal
from painel.infra.seguranca import EmissorDeTokens


def criar_app(
    config: Config | None = None,
    relogio: Callable[[], date] = date.today,
    enviador: EnviadorDeEmail | None = None,
) -> FastAPI:
    config = config or Config.do_ambiente()
    app = FastAPI(title="Painel Financeiro", version="0.1.0")

    engine = criar_engine(config.database_url)
    app.state.engine = engine
    app.state.fabrica_sessoes = criar_fabrica_sessoes(engine)
    app.state.emissor = EmissorDeTokens(config.chave_token, config.validade_token_segundos)
    app.state.relogio = relogio
    app.state.config = config
    if enviador is None:
        enviador = (
            EnviadorSmtp(
                config.smtp_servidor,
                config.smtp_porta,
                config.smtp_usuario,
                config.smtp_senha,
                f"Painel Financeiro <{config.smtp_usuario}>",
            )
            if config.smtp_usuario and config.smtp_senha
            else EnviadorTerminal()
        )
    app.state.enviador = enviador

    if config.origens_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(config.origens_cors),
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.exception_handler(ErroDeValidacao)
    async def _erro_dominio(_: Request, erro: ErroDeValidacao) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(erro)}
        )

    @app.exception_handler(IntegrityError)
    async def _erro_integridade(_: Request, __: IntegrityError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Conflito com dados existentes."},
        )

    @app.get("/saude", tags=["infra"])
    def saude() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(cadastros.router)
    app.include_router(relatorios.router)
    app.include_router(backup.router)
    return app
