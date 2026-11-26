"""Engine e fábrica de sessões SQLAlchemy."""

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def normalizar_url(url: str) -> str:
    """Neon/Render entregam "postgres://" ou "postgresql://"; usamos o driver psycopg 3."""
    for prefixo in ("postgres://", "postgresql://"):
        if url.startswith(prefixo):
            return "postgresql+psycopg://" + url[len(prefixo) :]
    return url


def criar_engine(url: str) -> Engine:
    url = normalizar_url(url)
    argumentos: dict = {}
    if url.startswith("sqlite"):
        argumentos["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url or url in {"sqlite://", "sqlite:///"}:
            argumentos["poolclass"] = StaticPool
    if url.startswith("postgresql"):
        argumentos["pool_pre_ping"] = True  # Neon fecha conexões ociosas
    engine = create_engine(url, **argumentos)

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _ativar_chaves_estrangeiras(conexao, _registro) -> None:  # pragma: no cover
            cursor = conexao.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def criar_fabrica_sessoes(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
