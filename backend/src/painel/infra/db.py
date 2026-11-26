"""Engine e fábrica de sessões SQLAlchemy."""

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def criar_engine(url: str) -> Engine:
    argumentos: dict = {}
    if url.startswith("sqlite"):
        argumentos["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url or url in {"sqlite://", "sqlite:///"}:
            argumentos["poolclass"] = StaticPool
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
