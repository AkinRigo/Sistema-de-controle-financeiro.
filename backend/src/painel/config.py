"""Configuração da aplicação lida de variáveis de ambiente."""

import hashlib
import os
import secrets
import warnings
from dataclasses import dataclass


def _chave_de(segredo: str) -> bytes:
    """64 caracteres hex viram a chave direto; qualquer outro segredo longo passa por SHA-256
    (assim serve a chave gerada pelo Render, que vem em base64)."""
    try:
        chave = bytes.fromhex(segredo)
        if len(chave) == 32:
            return chave
    except ValueError:
        pass
    if len(segredo) < 32:
        raise ValueError("PAINEL_CHAVE_TOKEN muito curta: use pelo menos 32 caracteres.")
    return hashlib.sha256(segredo.encode()).digest()


SEM_BANCO = (
    "PAINEL_DATABASE_URL não configurada. O banco do painel é o Neon: coloque a "
    "connection string (postgresql://...neon.tech/...) no .env da raiz do projeto."
)


def url_do_banco() -> str:
    """Só existe um banco (Neon). Sem a variável, para com erro em vez de criar um SQLite."""
    url = os.environ.get("PAINEL_DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(SEM_BANCO)
    return url


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
    # Chave do POST /admin/users (header X-Admin-Key). Vazia = rota de admin desligada.
    admin_api_key: str = ""
    # Pasta do site montado (frontend/dist) para o backend entregar em "/". Vazia = só API.
    frontend_dist: str = ""
    # Comando de voz: chave do Google AI Studio (Gemini). Vazia = comando de voz desligado.
    gemini_api_key: str = ""
    voz_modelo: str = "gemini-3.5-flash-lite"

    @classmethod
    def do_ambiente(cls) -> "Config":
        segredo = os.environ.get("PAINEL_CHAVE_TOKEN", "").strip()
        if segredo:
            chave = _chave_de(segredo)
        else:
            warnings.warn(
                "PAINEL_CHAVE_TOKEN não definida: usando chave aleatória; "
                "os logins serão invalidados ao reiniciar.",
                stacklevel=2,
            )
            chave = secrets.token_bytes(32)
        origens = os.environ.get("PAINEL_CORS_ORIGENS", "http://localhost:5173")
        return cls(
            database_url=url_do_banco(),
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
            admin_api_key=os.environ.get("ADMIN_API_KEY", "").strip(),
            frontend_dist=os.environ.get("PAINEL_FRONTEND_DIST", "").strip(),
            gemini_api_key=os.environ.get("GEMINI_API_KEY", "").strip(),
            voz_modelo=os.environ.get("PAINEL_VOZ_MODELO", "gemini-3.5-flash-lite").strip(),
        )
