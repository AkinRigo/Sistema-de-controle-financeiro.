from alembic import context
from sqlalchemy import engine_from_config, pool

from painel.config import url_do_banco
from painel.infra.db import normalizar_url
from painel.infra.modelos import Base

config = context.config
# Sem PAINEL_DATABASE_URL, para com erro claro (nunca cria um SQLite local).
config.set_main_option("sqlalchemy.url", normalizar_url(url_do_banco()).replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    conectavel = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with conectavel.connect() as conexao:
        context.configure(connection=conexao, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
