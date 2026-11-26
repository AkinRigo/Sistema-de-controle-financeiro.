r"""Marca um usuário como administrador.

Uso (dentro de backend/):
    .venv\Scripts\python scripts\tornar_admin.py               # akinrigo7@gmail.com
    .venv\Scripts\python scripts\tornar_admin.py outro@email.com
    .venv\Scripts\python scripts\tornar_admin.py outro@email.com --remover

Usa o banco do backend/.env (PAINEL_DATABASE_URL, o Neon).
"""

import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select

ADMIN_PADRAO = "akinrigo7@gmail.com"


def main(argv: list[str]) -> int:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    from painel.config import url_do_banco
    from painel.infra.db import criar_engine, criar_fabrica_sessoes
    from painel.infra.modelos import UsuarioModelo

    args = [a for a in argv if not a.startswith("--")]
    email = (args[0] if args else ADMIN_PADRAO).strip().lower()
    tornar = "--remover" not in argv

    sessao = criar_fabrica_sessoes(criar_engine(url_do_banco()))()
    usuario = sessao.scalar(select(UsuarioModelo).where(UsuarioModelo.email == email))
    if usuario is None:
        print(f"Nenhum usuário com o e-mail {email}. Cadastre a conta primeiro.")
        return 1
    usuario.admin = tornar
    sessao.commit()
    print(f"{usuario.nome} <{email}> agora {'é' if tornar else 'não é mais'} administrador.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
