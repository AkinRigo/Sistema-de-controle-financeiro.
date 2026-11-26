"""Configuração da aplicação lida de variáveis de ambiente."""

import os
import secrets
import warnings
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Config:
    database_url: str
    chave_token: bytes
    validade_token_segundos: int = 60 * 60 * 24 * 7
    origens_cors: tuple[str, ...] = ()
    url_frontend: str = "http://localhost:5173"
    smtp_usuario: str = ""
    smtp_senha: str = ""
    smtp_servidor: str = "smtp.gmail.com"
    smtp_porta: int = 465

    @classmethod
    def do_ambiente(cls) -> "Config":
        chave_hex = os.environ.get("PAINEL_CHAVE_TOKEN", "")
        if chave_hex:
            chave = bytes.fromhex(chave_hex)
            if len(chave) != 32:
                raise ValueError("PAINEL_CHAVE_TOKEN deve ter 32 bytes em hexadecimal (64 chars).")
        else:
            warnings.warn(
                "PAINEL_CHAVE_TOKEN não definida: usando chave aleatória; "
                "os logins serão invalidados ao reiniciar.",
                stacklevel=2,
            )
            chave = secrets.token_bytes(32)
        origens = os.environ.get("PAINEL_CORS_ORIGENS", "http://localhost:5173")
        return cls(
            database_url=os.environ.get("PAINEL_DATABASE_URL", "sqlite:///./painel.db"),
            chave_token=chave,
            validade_token_segundos=int(
                os.environ.get("PAINEL_VALIDADE_TOKEN", str(60 * 60 * 24 * 7))
            ),
            origens_cors=tuple(o.strip() for o in origens.split(",") if o.strip()),
            url_frontend=os.environ.get("PAINEL_URL_FRONTEND", "http://localhost:5173"),
            smtp_usuario=os.environ.get("PAINEL_SMTP_USUARIO", ""),
            # senha de app do Google vem com espaços ("abcd efgh ..."); tiramos
            smtp_senha=os.environ.get("PAINEL_SMTP_SENHA", "").replace(" ", ""),
            smtp_servidor=os.environ.get("PAINEL_SMTP_SERVIDOR", "smtp.gmail.com"),
            smtp_porta=int(os.environ.get("PAINEL_SMTP_PORTA", "465")),
        )
