"""Rotas de administração.

Aceitam o login de um usuário administrador (Bearer PASETO de quem tem `admin`) ou a
ADMIN_API_KEY no header X-Admin-Key (útil para scripts).
"""

import hmac
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from painel.api.deps import EmissorDep, HojeDep, SessaoDep
from painel.api.schemas import CadastroEntrada, UsuarioSaida
from painel.infra.modelos import UsuarioModelo
from painel.infra.seguranca import TokenInvalido, gerar_hash_senha

_bearer = HTTPBearer(auto_error=False)


def _usuario_admin(
    sessao: SessaoDep, emissor: EmissorDep, credenciais: HTTPAuthorizationCredentials | None
) -> UsuarioModelo | None:
    if credenciais is None:
        return None
    try:
        usuario = sessao.get(UsuarioModelo, emissor.validar(credenciais.credentials))
    except TokenInvalido:
        return None
    if usuario is not None and not usuario.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Só administradores.")
    return usuario


def exigir_admin(
    request: Request,
    sessao: SessaoDep,
    emissor: EmissorDep,
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    x_admin_key: Annotated[str | None, Header(description="valor da ADMIN_API_KEY")] = None,
) -> None:
    if _usuario_admin(sessao, emissor, credenciais) is not None:
        return
    chave = request.app.state.config.admin_api_key
    if not chave:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rota de admin desligada: configure ADMIN_API_KEY.",
        )
    if not x_admin_key or not hmac.compare_digest(x_admin_key.encode(), chave.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Chave de admin inválida."
        )


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(exigir_admin)])


@router.post("/users", response_model=UsuarioSaida, status_code=status.HTTP_201_CREATED)
def criar_usuario(dados: CadastroEntrada, sessao: SessaoDep, hoje: HojeDep) -> UsuarioSaida:
    """Cadastra um amigo já ativado (sem e-mail de ativação). Ele entra com e-mail e senha."""
    if sessao.scalar(select(UsuarioModelo).where(UsuarioModelo.email == dados.email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado.")
    usuario = UsuarioModelo(
        id=str(uuid.uuid4()),
        nome=dados.nome,
        email=dados.email,
        senha_hash=gerar_hash_senha(dados.senha),
        desde=f"{hoje.year:04d}-{hoje.month:02d}",
        email_confirmado=True,
    )
    sessao.add(usuario)
    sessao.flush()
    return UsuarioSaida(id=usuario.id, nome=usuario.nome, email=usuario.email, desde=usuario.desde)
