"""Fábrica da aplicação FastAPI."""

import re
import uuid
from collections.abc import Callable
from datetime import date

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from painel.api.erros import mensagens
from painel.api.rotas import admin, auth, backup, cadastros, relatorios, rendas
from painel.config import Config
from painel.domain.erros import ErroDeValidacao
from painel.infra.db import criar_engine, criar_fabrica_sessoes
from painel.infra.email import EnviadorDeEmail, EnviadorSmtp, EnviadorTerminal
from painel.infra.eventos import registrar
from painel.infra.seguranca import EmissorDeTokens


def _origens(origens: tuple[str, ...]) -> tuple[list[str], str | None]:
    """Separa origens exatas de curingas como "https://*.meusite.pages.dev" (prévias do
    Cloudflare Pages). O curinga vale para um único nível de subdomínio."""
    exatas = [o for o in origens if "*" not in o]
    curingas = [re.escape(o).replace(r"\*", r"[a-z0-9-]+") for o in origens if "*" in o]
    return exatas, ("^(" + "|".join(curingas) + ")$") if curingas else None


def criar_app(
    config: Config | None = None,
    relogio: Callable[[], date] = date.today,
    enviador: EnviadorDeEmail | None = None,
) -> FastAPI:
    config = config or Config.do_ambiente()
    app = FastAPI(title="No Corre das Notas", version="0.1.0")

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
                f"No Corre das Notas <{config.smtp_usuario}>",
            )
            if config.smtp_usuario and config.smtp_senha
            else EnviadorTerminal()
        )
    app.state.enviador = enviador

    # Registrado antes do CORS para a resposta de erro também levar os cabeçalhos de CORS.
    @app.middleware("http")
    async def _requisicao(request: Request, chamar_proximo):
        request.state.rid = "req_" + uuid.uuid4().hex[:8]
        try:
            resposta = await chamar_proximo(request)
        except Exception as erro:
            registrar(
                app.state.fabrica_sessoes,
                nivel="erro",
                tipo="sistema",
                acao="erro_inesperado",
                mensagem=f"Erro inesperado em {request.method} {request.url.path}",
                rota=f"{request.method} {request.url.path}",
                codigo=500,
                requisicao=request.state.rid,
                detalhe=f"{type(erro).__name__}: {erro}"[:2000],
            )
            resposta = JSONResponse(
                status_code=500,
                content={
                    "detail": f"Algo deu errado do nosso lado. Código: {request.state.rid}.",
                },
            )
        resposta.headers["X-Request-Id"] = request.state.rid
        return resposta

    if config.origens_cors:
        exatas, padrao = _origens(config.origens_cors)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=exatas,
            allow_origin_regex=padrao,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.exception_handler(ErroDeValidacao)
    async def _erro_dominio(_: Request, erro: ErroDeValidacao) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(erro)}
        )

    @app.exception_handler(RequestValidationError)
    async def _erro_entrada(_: Request, erro: RequestValidationError) -> JSONResponse:
        # Texto em português pronto para a tela; os detalhes técnicos vão em "erros".
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "detail": mensagens(list(erro.errors())),
                "erros": jsonable_encoder(erro.errors()),
            },
        )

    @app.exception_handler(IntegrityError)
    async def _erro_integridade(_: Request, __: IntegrityError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Conflito com dados existentes."},
        )

    @app.get("/", tags=["infra"])
    def inicio() -> dict[str, str]:
        return {"app": "No Corre das Notas", "status": "ok", "docs": "/docs"}

    @app.get("/saude", tags=["infra"])
    def saude() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(cadastros.router)
    app.include_router(relatorios.router)
    app.include_router(backup.router)
    app.include_router(rendas.router)
    app.include_router(admin.router)
    return app
