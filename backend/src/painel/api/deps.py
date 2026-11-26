"""Dependências compartilhadas das rotas."""

from collections.abc import Iterator
from datetime import date
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from painel.infra.modelos import UsuarioModelo
from painel.infra.seguranca import EmissorDeTokens, TokenInvalido

_bearer = HTTPBearer(auto_error=False)


def obter_sessao(request: Request) -> Iterator[Session]:
    sessao: Session = request.app.state.fabrica_sessoes()
    try:
        yield sessao
        sessao.commit()
    except Exception:
        sessao.rollback()
        raise
    finally:
        sessao.close()


def obter_emissor(request: Request) -> EmissorDeTokens:
    return request.app.state.emissor


def obter_hoje(request: Request) -> date:
    return request.app.state.relogio()


SessaoDep = Annotated[Session, Depends(obter_sessao)]
EmissorDep = Annotated[EmissorDeTokens, Depends(obter_emissor)]
HojeDep = Annotated[date, Depends(obter_hoje)]


def obter_usuario_atual(
    sessao: SessaoDep,
    emissor: EmissorDep,
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> UsuarioModelo:
    nao_autorizado = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não autenticado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credenciais is None:
        raise nao_autorizado
    try:
        usuario_id = emissor.validar(credenciais.credentials)
    except TokenInvalido:
        raise nao_autorizado from None
    usuario = sessao.get(UsuarioModelo, usuario_id)
    if usuario is None:
        raise nao_autorizado
    return usuario


# Nome em inglês, como no padrão da documentação do FastAPI: mesma função.
get_current_user = obter_usuario_atual

UsuarioDep = Annotated[UsuarioModelo, Depends(get_current_user)]


def nao_encontrado(recurso: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{recurso} não encontrado.")
