"""Inicia o No Corre das Notas na Vertra Cloud (ou em qualquer hospedagem de um app só).

Não depende de shell: entra em backend/, aplica as migrações do banco e sobe o
FastAPI na porta da plataforma (PORT, padrão 80), entregando também o site montado.
"""

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
BACKEND = RAIZ / "backend"


def main() -> None:
    print(f"[no-corre] Python {sys.version.split()[0]} em {RAIZ}", flush=True)
    os.chdir(BACKEND)
    # Funciona mesmo se o pacote não tiver sido instalado com pip (usa o código da pasta).
    sys.path.insert(0, str(BACKEND / "src"))
    os.environ.setdefault("PAINEL_FRONTEND_DIST", str(RAIZ / "frontend" / "dist"))
    site = Path(os.environ["PAINEL_FRONTEND_DIST"]) / "index.html"
    print(f"[no-corre] site montado: {'sim' if site.is_file() else 'NÃO encontrado'}", flush=True)
    if not os.environ.get("PAINEL_DATABASE_URL"):
        print("[no-corre] ERRO: falta a variável PAINEL_DATABASE_URL (Neon).", flush=True)
        raise SystemExit(1)

    print("[no-corre] aplicando migrações do banco...", flush=True)
    from alembic.config import main as alembic

    alembic(argv=["upgrade", "head"])

    import uvicorn

    porta = int(os.environ.get("PORT", "80"))
    print(f"[no-corre] subindo na porta {porta}...", flush=True)
    uvicorn.run(
        "painel.main:app",
        host="0.0.0.0",
        port=porta,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
