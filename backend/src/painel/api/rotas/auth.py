"""Cadastro com confirmação por e-mail, login, dados do usuário e redefinição de senha."""

import html
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from painel.api.deps import EmissorDep, HojeDep, SessaoDep, UsuarioDep
from painel.api.schemas import (
    CadastroEntrada,
    ConfirmarEmailEntrada,
    EsqueciSenhaEntrada,
    LoginEntrada,
    RedefinirSenhaEntrada,
    TokenSaida,
    UsuarioSaida,
)
from painel.infra.email import enviar_com_seguranca
from painel.infra.modelos import UsuarioModelo
from painel.infra.seguranca import (
    EmissorDeTokens,
    TokenInvalido,
    gerar_hash_senha,
    link_ainda_valido,
    verificar_senha,
)

router = APIRouter(prefix="/auth", tags=["autenticação"])

# Hash válido usado quando o e-mail não existe, para o tempo de resposta não revelar contas.
_HASH_FALSO = gerar_hash_senha("senha-inexistente-para-tempo-constante")
_NAO_CONFIRMADO = "Confirme seu e-mail antes de entrar. Procure o link que enviamos (veja o spam)."


def _saida(usuario: UsuarioModelo) -> UsuarioSaida:
    return UsuarioSaida(id=usuario.id, nome=usuario.nome, email=usuario.email, desde=usuario.desde)


def _por_email(sessao: Session, email: str) -> UsuarioModelo | None:
    return sessao.scalar(select(UsuarioModelo).where(UsuarioModelo.email == email))


def _email(nome: str, intro: str, link: str, botao: str, validade: str) -> tuple[str, str]:
    texto = (
        f"Oi, {nome}!\n\n{intro}\n"
        f"Abra este link ({validade}):\n\n{link}\n\n"
        "Se não foi você, é só ignorar este e-mail."
    )
    corpo_html = (
        f"<p>Oi, {html.escape(nome)}!</p><p>{html.escape(intro)}</p>"
        f'<p><a href="{html.escape(link)}" style="display:inline-block;background:#1240e0;'
        "color:#fff;padding:12px 20px;border-radius:10px;text-decoration:none;"
        f'font-weight:600">{html.escape(botao)}</a></p>'
        f"<p>O link {html.escape(validade)}. Se não foi você, é só ignorar este e-mail.</p>"
    )
    return texto, corpo_html


def _agendar_envio(
    request: Request, tarefas: BackgroundTasks, para: str, assunto: str, corpo: tuple[str, str]
) -> None:
    tarefas.add_task(
        enviar_com_seguranca, request.app.state.enviador, para, assunto, corpo[0], corpo[1]
    )


def _link(request: Request, parametro: str, token: str) -> str:
    return f"{request.app.state.config.url_frontend.rstrip('/')}/?{parametro}={token}"


def _enviar_confirmacao(
    usuario: UsuarioModelo, emissor: EmissorDeTokens, request: Request, tarefas: BackgroundTasks
) -> None:
    link = _link(request, "confirmar", emissor.emitir_confirmacao(usuario.id))
    corpo = _email(
        usuario.nome,
        "Sua conta no Painel Financeiro foi criada. Falta só confirmar este e-mail.",
        link,
        "Ativar minha conta",
        "vale por 24 horas",
    )
    _agendar_envio(request, tarefas, usuario.email, "Ative sua conta no Painel Financeiro", corpo)


# ---------------- cadastro e confirmação ----------------


@router.post("/cadastro", status_code=status.HTTP_201_CREATED)
def cadastrar(
    dados: CadastroEntrada,
    sessao: SessaoDep,
    emissor: EmissorDep,
    hoje: HojeDep,
    request: Request,
    tarefas: BackgroundTasks,
) -> dict[str, str]:
    if _por_email(sessao, dados.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado.")
    usuario = UsuarioModelo(
        id=str(uuid.uuid4()),
        nome=dados.nome,
        email=dados.email,
        senha_hash=gerar_hash_senha(dados.senha),
        desde=f"{hoje.year:04d}-{hoje.month:02d}",
        email_confirmado=False,
    )
    sessao.add(usuario)
    sessao.flush()
    _enviar_confirmacao(usuario, emissor, request, tarefas)
    return {"detail": f"Enviamos um link para {usuario.email}. Abra o e-mail para ativar."}


@router.post("/confirmar-email", response_model=TokenSaida)
def confirmar_email(
    dados: ConfirmarEmailEntrada, sessao: SessaoDep, emissor: EmissorDep
) -> TokenSaida:
    invalido = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Esse link de ativação expirou ou é inválido. Peça um novo.",
    )
    try:
        usuario_id = emissor.validar_confirmacao(dados.token)
    except TokenInvalido:
        raise invalido from None
    usuario = sessao.get(UsuarioModelo, usuario_id)
    if usuario is None:
        raise invalido
    usuario.email_confirmado = True
    return TokenSaida(token=emissor.emitir(usuario.id), usuario=_saida(usuario))


@router.post("/reenviar-confirmacao", status_code=status.HTTP_202_ACCEPTED)
def reenviar_confirmacao(
    dados: EsqueciSenhaEntrada,
    sessao: SessaoDep,
    emissor: EmissorDep,
    request: Request,
    tarefas: BackgroundTasks,
) -> dict[str, str]:
    """Responde sempre igual, para não revelar quem tem cadastro."""
    usuario = _por_email(sessao, dados.email)
    if usuario is not None and not usuario.email_confirmado:
        _enviar_confirmacao(usuario, emissor, request, tarefas)
    return {"detail": "Se essa conta ainda não foi ativada, enviamos um novo link."}


# ---------------- login ----------------


@router.post("/login", response_model=TokenSaida)
def entrar(dados: LoginEntrada, sessao: SessaoDep, emissor: EmissorDep) -> TokenSaida:
    usuario = _por_email(sessao, dados.email)
    senha_ok = verificar_senha(usuario.senha_hash if usuario else _HASH_FALSO, dados.senha)
    if usuario is None or not senha_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha incorretos."
        )
    if not usuario.email_confirmado:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_NAO_CONFIRMADO)
    return TokenSaida(token=emissor.emitir(usuario.id), usuario=_saida(usuario))


@router.get("/eu", response_model=UsuarioSaida)
def eu(usuario: UsuarioDep) -> UsuarioSaida:
    return _saida(usuario)


# ---------------- senha ----------------


@router.post("/esqueci-senha", status_code=status.HTTP_202_ACCEPTED)
def esqueci_senha(
    dados: EsqueciSenhaEntrada,
    sessao: SessaoDep,
    emissor: EmissorDep,
    request: Request,
    tarefas: BackgroundTasks,
) -> dict[str, str]:
    """Sempre responde igual, exista ou não a conta, para não revelar quem tem cadastro."""
    usuario = _por_email(sessao, dados.email)
    if usuario is not None:
        token = emissor.emitir_redefinicao(usuario.id, usuario.senha_hash)
        corpo = _email(
            usuario.nome,
            "Recebemos um pedido para trocar a senha do seu Painel Financeiro.",
            _link(request, "redefinir", token),
            "Criar senha nova",
            "vale por 30 minutos",
        )
        _agendar_envio(
            request, tarefas, usuario.email, "Trocar a senha do Painel Financeiro", corpo
        )
    return {"detail": "Se esse e-mail tiver cadastro, enviamos um link para trocar a senha."}


@router.post("/redefinir-senha", response_model=TokenSaida)
def redefinir_senha(
    dados: RedefinirSenhaEntrada, sessao: SessaoDep, emissor: EmissorDep
) -> TokenSaida:
    invalido = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Esse link expirou ou já foi usado. Peça um novo.",
    )
    try:
        usuario_id, impressao = emissor.validar_redefinicao(dados.token)
    except TokenInvalido:
        raise invalido from None
    usuario = sessao.get(UsuarioModelo, usuario_id)
    if usuario is None or not link_ainda_valido(impressao, usuario.senha_hash):
        raise invalido
    usuario.senha_hash = gerar_hash_senha(dados.senha)
    usuario.email_confirmado = True  # o link chegou no e-mail: ele é dele
    return TokenSaida(token=emissor.emitir(usuario.id), usuario=_saida(usuario))
