"""Cadastro com confirmação por e-mail, login, convites, dados do usuário e troca de senha.

Acessos e falhas de e-mail são gravados no log (aba Logs do admin).
"""

import html
import uuid
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from painel.api.deps import (
    CONTA_DESATIVADA,
    EmissorDep,
    HojeDep,
    SessaoDep,
    UsuarioDep,
    registrar_evento,
)
from painel.api.schemas import (
    AceitarConviteEntrada,
    CadastroEntrada,
    ConfirmarEmailEntrada,
    ConviteSaida,
    EsqueciSenhaEntrada,
    LoginEntrada,
    RedefinirSenhaEntrada,
    TokenSaida,
    UsuarioSaida,
)
from painel.infra.email import enviar_com_seguranca
from painel.infra.eventos import agora, em_utc, registrar
from painel.infra.modelos import ConviteModelo, EventoModelo, UsuarioModelo
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
TENTATIVAS_ALERTA = 5


def _saida(usuario: UsuarioModelo) -> UsuarioSaida:
    return UsuarioSaida(
        id=usuario.id,
        nome=usuario.nome,
        email=usuario.email,
        desde=usuario.desde,
        admin=bool(usuario.admin),
    )


def _por_email(sessao: Session, email: str) -> UsuarioModelo | None:
    return sessao.scalar(select(UsuarioModelo).where(UsuarioModelo.email == email))


def _email(saudacao: str, intro: str, link: str, botao: str, validade: str) -> tuple[str, str]:
    """`intro` pode ter vários parágrafos separados por linha em branco."""
    paragrafos = [p.strip() for p in intro.split("\n\n") if p.strip()]
    texto = (
        f"{saudacao}\n\n" + "\n\n".join(paragrafos) + "\n\n"
        f"Abra este link ({validade}):\n\n{link}\n\n"
        "Se não foi você, é só ignorar este e-mail.\n\n— No Corre das Notas"
    )
    corpo_html = (
        '<div style="font-family:Arial,sans-serif;max-width:520px;color:#141414">'
        '<p style="font-size:22px;font-weight:700;color:#6d28d9;margin:0 0 16px">'
        "No Corre das Notas</p>"
        f'<p style="font-size:18px;font-weight:700">{html.escape(saudacao)}</p>'
        + "".join(f"<p>{html.escape(p)}</p>" for p in paragrafos)
        + f'<p><a href="{html.escape(link)}" style="display:inline-block;background:#6d28d9;'
        "color:#fff;padding:14px 22px;border:3px solid #141414;border-radius:12px;"
        f'text-decoration:none;font-weight:700">{html.escape(botao)}</a></p>'
        f'<p style="color:#4a4458">O link {html.escape(validade)}. '
        "Se não foi você, é só ignorar este e-mail.</p></div>"
    )
    return texto, corpo_html


def _agendar_envio(
    request: Request, tarefas: BackgroundTasks, para: str, assunto: str, corpo: tuple[str, str]
) -> None:
    fabrica, rid = request.app.state.fabrica_sessoes, getattr(request.state, "rid", None)
    rota = f"{request.method} {request.url.path}"

    def ao_falhar(erro: Exception) -> None:
        registrar(
            fabrica,
            nivel="erro",
            tipo="email",
            acao="email_falhou",
            mensagem=f"E-mail não enviado: {assunto}",
            email=para,
            rota=rota,
            requisicao=rid,
            detalhe=f"{type(erro).__name__}: {erro}"[:2000],
        )

    tarefas.add_task(
        enviar_com_seguranca,
        request.app.state.enviador,
        para,
        assunto,
        corpo[0],
        corpo[1],
        ao_falhar,
    )


def _link(request: Request, parametro: str, token: str) -> str:
    return f"{request.app.state.config.url_frontend.rstrip('/')}/?{parametro}={token}"


def enviar_confirmacao(
    usuario: UsuarioModelo, emissor: EmissorDeTokens, request: Request, tarefas: BackgroundTasks
) -> None:
    link = _link(request, "confirmar", emissor.emitir_confirmacao(usuario.id))
    corpo = _email(
        f"Seja bem-vindo(a) ao No Corre das Notas, {usuario.nome}!",
        "Sua conta foi criada. Clique no botão abaixo para ativar e depois é só "
        "entrar com seu e-mail e senha.",
        link,
        "Ativar minha conta",
        "vale por 24 horas",
    )
    _agendar_envio(
        request, tarefas, usuario.email, "Bem-vindo ao No Corre das Notas! Ative sua conta", corpo
    )


def enviar_nova_senha(
    usuario: UsuarioModelo, emissor: EmissorDeTokens, request: Request, tarefas: BackgroundTasks
) -> None:
    token = emissor.emitir_redefinicao(usuario.id, usuario.senha_hash)
    corpo = _email(
        f"Oi, {usuario.nome}!",
        "Recebemos um pedido para trocar a senha da sua conta no No Corre das Notas.",
        _link(request, "redefinir", token),
        "Criar senha nova",
        "vale por 30 minutos",
    )
    _agendar_envio(request, tarefas, usuario.email, "Trocar a senha do No Corre das Notas", corpo)


def enviar_convite(
    convite: ConviteModelo, emissor: EmissorDeTokens, request: Request, tarefas: BackgroundTasks
) -> None:
    corpo = _email(
        f"Seja bem-vindo(a) ao No Corre das Notas, {convite.nome}!",
        "Pra gente, o que importa é como você lida com o seu dinheiro, e queremos estar "
        "junto nisso.\n\n"
        "Por isso te enviamos este convite especial para criar sua conta no nosso site e no "
        "aplicativo e organizar sua vida financeira, sem custo nenhum.",
        _link(request, "convite", emissor.emitir_convite(convite.id)),
        "Aceitar convite e criar minha senha",
        "vale por 7 dias",
    )
    _agendar_envio(
        request,
        tarefas,
        convite.email,
        "Você recebeu um convite especial para o No Corre das Notas",
        corpo,
    )


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
    enviar_confirmacao(usuario, emissor, request, tarefas)
    registrar_evento(
        request,
        nivel="info",
        tipo="acesso",
        acao="cadastro",
        mensagem="Novo cadastro pelo site",
        email=usuario.email,
        codigo=201,
    )
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
        enviar_confirmacao(usuario, emissor, request, tarefas)
    return {"detail": "Se essa conta ainda não foi ativada, enviamos um novo link."}


# ---------------- convite ----------------


def _convite_pelo_token(sessao: Session, emissor: EmissorDeTokens, token: str) -> ConviteModelo:
    invalido = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Esse convite expirou ou não vale mais. Peça um novo para quem te convidou.",
    )
    try:
        convite = sessao.get(ConviteModelo, emissor.validar_convite(token))
    except TokenInvalido:
        raise invalido from None
    if convite is None or convite.status != "pendente":
        raise invalido
    return convite


@router.get("/convite/{token}", response_model=ConviteSaida)
def ver_convite(token: str, sessao: SessaoDep, emissor: EmissorDep) -> ConviteSaida:
    """Dados do convite para a tela "criar sua senha"."""
    convite = _convite_pelo_token(sessao, emissor, token)
    return ConviteSaida(nome=convite.nome, email=convite.email)


@router.post("/aceitar-convite", response_model=TokenSaida, status_code=status.HTTP_201_CREATED)
def aceitar_convite(
    dados: AceitarConviteEntrada,
    sessao: SessaoDep,
    emissor: EmissorDep,
    hoje: HojeDep,
    request: Request,
) -> TokenSaida:
    convite = _convite_pelo_token(sessao, emissor, dados.token)
    if _por_email(sessao, convite.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esse e-mail já tem conta. Entre com ele ou use “Esqueci minha senha”.",
        )
    usuario = UsuarioModelo(
        id=str(uuid.uuid4()),
        nome=convite.nome,
        email=convite.email,
        senha_hash=gerar_hash_senha(dados.senha),
        desde=f"{hoje.year:04d}-{hoje.month:02d}",
        email_confirmado=True,  # o link chegou no e-mail dela
        ultimo_acesso=agora(),
    )
    sessao.add(usuario)
    convite.status = "aceito"
    convite.aceito_em = agora()
    sessao.flush()
    registrar_evento(
        request,
        nivel="info",
        tipo="acesso",
        acao="convite_aceito",
        mensagem="Convite aceito: conta criada",
        email=usuario.email,
        codigo=201,
    )
    return TokenSaida(token=emissor.emitir(usuario.id), usuario=_saida(usuario))


# ---------------- login ----------------


def falhas_recentes(sessao: Session, email: str) -> int:
    """Senhas erradas nas últimas 24 h (datas comparadas em Python: igual no SQLite e Postgres)."""
    desde = agora() - timedelta(hours=24)
    quandos = sessao.scalars(
        select(EventoModelo.criado_em).where(
            EventoModelo.acao == "login_falhou", EventoModelo.email == email
        )
    )
    return sum(1 for q in quandos if em_utc(q) >= desde)


@router.post("/login", response_model=TokenSaida)
def entrar(
    dados: LoginEntrada, sessao: SessaoDep, emissor: EmissorDep, request: Request
) -> TokenSaida:
    usuario = _por_email(sessao, dados.email)
    senha_ok = verificar_senha(usuario.senha_hash if usuario else _HASH_FALSO, dados.senha)
    if usuario is None or not senha_ok:
        if usuario is not None:
            registrar_evento(
                request,
                nivel="aviso",
                tipo="acesso",
                acao="login_falhou",
                mensagem="Login com senha errada",
                email=usuario.email,
                codigo=401,
            )
            falhas = falhas_recentes(sessao, usuario.email)
            if falhas == TENTATIVAS_ALERTA:
                registrar_evento(
                    request,
                    nivel="erro",
                    tipo="acesso",
                    acao="muitas_tentativas",
                    mensagem=f"{falhas} tentativas de login com senha errada em 24 h",
                    email=usuario.email,
                    codigo=401,
                    detalhe="Conta não bloqueada. Se for a pessoa, mande o link de nova senha.",
                )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha incorretos."
        )
    if not usuario.ativo:
        registrar_evento(
            request,
            nivel="erro",
            tipo="acesso",
            acao="login_desativado",
            mensagem="Tentativa de login de conta desativada",
            email=usuario.email,
            codigo=403,
        )
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=CONTA_DESATIVADA)
    if not usuario.email_confirmado:
        registrar_evento(
            request,
            nivel="aviso",
            tipo="acesso",
            acao="login_nao_ativado",
            mensagem="Login antes de ativar o e-mail",
            email=usuario.email,
            codigo=403,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_NAO_CONFIRMADO)
    usuario.ultimo_acesso = agora()
    registrar_evento(
        request,
        nivel="info",
        tipo="acesso",
        acao="login_ok",
        mensagem="Login",
        email=usuario.email,
        codigo=200,
    )
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
        enviar_nova_senha(usuario, emissor, request, tarefas)
    return {"detail": "Se esse e-mail tiver cadastro, enviamos um link para trocar a senha."}


@router.post("/redefinir-senha", response_model=TokenSaida)
def redefinir_senha(
    dados: RedefinirSenhaEntrada, sessao: SessaoDep, emissor: EmissorDep, request: Request
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
    if not usuario.ativo:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=CONTA_DESATIVADA)
    usuario.senha_hash = gerar_hash_senha(dados.senha)
    usuario.email_confirmado = True  # o link chegou no e-mail: ele é dele
    usuario.ultimo_acesso = agora()
    registrar_evento(
        request,
        nivel="info",
        tipo="acesso",
        acao="senha_trocada",
        mensagem="Senha trocada pelo link do e-mail",
        email=usuario.email,
        codigo=200,
    )
    return TokenSaida(token=emissor.emitir(usuario.id), usuario=_saida(usuario))
