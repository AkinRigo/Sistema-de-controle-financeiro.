"""Central de emergência do admin: indicadores, usuários, convites e logs.

Aceita o login de um usuário administrador (Bearer PASETO de quem tem `admin`) ou a
ADMIN_API_KEY no header X-Admin-Key (útil para scripts).
"""

import hmac
import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request
from fastapi import status as http
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from painel.api.deps import EmissorDep, HojeDep, SessaoDep, registrar_evento
from painel.api.rotas.auth import (
    TENTATIVAS_ALERTA,
    enviar_confirmacao,
    enviar_convite,
    enviar_nova_senha,
    falhas_recentes,
)
from painel.api.schemas import (
    AdminUsuarioSaida,
    AdminUsuariosSaida,
    CadastroEntrada,
    ConviteEntrada,
    EventoSaida,
    IndicadoresSaida,
    LogsSaida,
    PendenciaSaida,
    UsuarioSaida,
)
from painel.infra.eventos import agora, em_utc, no_fuso, quando_texto
from painel.infra.modelos import ConviteModelo, EventoModelo, UsuarioModelo
from painel.infra.seguranca import TokenInvalido, gerar_hash_senha

_bearer = HTTPBearer(auto_error=False)


def _usuario_admin(
    sessao: Session, emissor, credenciais: HTTPAuthorizationCredentials | None
) -> UsuarioModelo | None:
    if credenciais is None:
        return None
    try:
        usuario = sessao.get(UsuarioModelo, emissor.validar(credenciais.credentials))
    except TokenInvalido:
        return None
    if usuario is not None and not (usuario.admin and usuario.ativo):
        raise HTTPException(status_code=http.HTTP_403_FORBIDDEN, detail="Só administradores.")
    return usuario


def exigir_admin(
    request: Request,
    sessao: SessaoDep,
    emissor: EmissorDep,
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    x_admin_key: Annotated[str | None, Header(description="valor da ADMIN_API_KEY")] = None,
) -> str:
    """Devolve quem está agindo (e-mail do admin ou "chave de admin"), para o log."""
    admin = _usuario_admin(sessao, emissor, credenciais)
    if admin is not None:
        return admin.email
    chave = request.app.state.config.admin_api_key
    if not chave:
        raise HTTPException(
            status_code=http.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rota de admin desligada: configure ADMIN_API_KEY.",
        )
    if not x_admin_key or not hmac.compare_digest(x_admin_key.encode(), chave.encode()):
        raise HTTPException(
            status_code=http.HTTP_401_UNAUTHORIZED, detail="Chave de admin inválida."
        )
    return "chave de admin"


AtorDep = Annotated[str, Depends(exigir_admin)]
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(exigir_admin)])


# ---------------- regras de exibição do admin ----------------

ORDEM_STATUS = {"master": 0, "nao_ativou": 1, "ativo": 2, "convidado": 3, "desativado": 4}
GRUPOS = {
    "todos": set(ORDEM_STATUS),
    "ativo": {"master", "ativo"},
    "nao_ativou": {"nao_ativou"},
    "convidado": {"convidado"},
    "desativado": {"desativado"},
}


def status_do_usuario(u: UsuarioModelo) -> str:
    if u.admin:
        return "master"
    if not u.ativo:
        return "desativado"
    if not u.email_confirmado:
        return "nao_ativou"
    return "ativo"


def _detalhe(u: UsuarioModelo, situacao: str, falhas: int) -> str:
    if situacao == "nao_ativou":
        return f"cadastrou {quando_texto(u.criado_em)}, não ativou o e-mail"
    if situacao == "desativado":
        return "conta desativada"
    texto = (
        f"último acesso {quando_texto(u.ultimo_acesso)}" if u.ultimo_acesso else "ainda não entrou"
    )
    if falhas >= 3:
        texto += f" · {falhas} senhas erradas em 24 h"
    return texto


def _evento_saida(e: EventoModelo) -> EventoSaida:
    return EventoSaida(
        id=e.id,
        quando=quando_texto(e.criado_em),
        nivel=e.nivel,
        tipo=e.tipo,
        acao=e.acao,
        mensagem=e.mensagem,
        email=e.email,
        rota=e.rota,
        codigo=e.codigo,
        requisicao=e.requisicao,
        detalhe=e.detalhe,
    )


def _usuario(sessao: Session, usuario_id: str) -> UsuarioModelo:
    u = sessao.get(UsuarioModelo, usuario_id)
    if u is None:
        raise HTTPException(status_code=http.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")
    return u


def _log_admin(request: Request, ator: str, acao: str, mensagem: str, email: str) -> None:
    registrar_evento(
        request,
        nivel="info",
        tipo="acesso",
        acao=acao,
        mensagem=mensagem,
        email=email,
        codigo=200,
        detalhe=f"Feito por {ator}.",
    )


# ---------------- usuários ----------------


@router.post("/users", response_model=UsuarioSaida, status_code=http.HTTP_201_CREATED)
def criar_usuario(dados: CadastroEntrada, sessao: SessaoDep, hoje: HojeDep) -> UsuarioSaida:
    """Cadastra um amigo já ativado (sem e-mail de ativação). Ele entra com e-mail e senha."""
    if sessao.scalar(select(UsuarioModelo).where(UsuarioModelo.email == dados.email)):
        raise HTTPException(status_code=http.HTTP_409_CONFLICT, detail="E-mail já cadastrado.")
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


@router.get("/usuarios", response_model=AdminUsuariosSaida)
def listar_usuarios(
    sessao: SessaoDep,
    status: Annotated[
        str, Query(pattern="^(todos|ativo|nao_ativou|convidado|desativado)$")
    ] = "todos",
    busca: str = "",
) -> AdminUsuariosSaida:
    itens: list[AdminUsuarioSaida] = []
    for u in sessao.scalars(select(UsuarioModelo)):
        situacao = status_do_usuario(u)
        itens.append(
            AdminUsuarioSaida(
                id=u.id,
                tipo="usuario",
                nome=u.nome,
                email=u.email,
                status=situacao,
                detalhe=_detalhe(u, situacao, falhas_recentes(sessao, u.email)),
            )
        )
    for c in sessao.scalars(select(ConviteModelo).where(ConviteModelo.status == "pendente")):
        itens.append(
            AdminUsuarioSaida(
                id=c.id,
                tipo="convite",
                nome=c.nome,
                email=c.email,
                status="convidado",
                detalhe=f"convite enviado {quando_texto(c.enviado_em)}",
            )
        )
    termo = busca.strip().lower()
    if termo:
        itens = [i for i in itens if termo in f"{i.nome} {i.email}".lower()]
    contagem = {k: sum(1 for i in itens if i.status in grupo) for k, grupo in GRUPOS.items()}
    visiveis = [i for i in itens if i.status in GRUPOS[status]]
    visiveis.sort(key=lambda i: (ORDEM_STATUS[i.status], i.nome.lower()))
    return AdminUsuariosSaida(usuarios=visiveis, contagem=contagem)


@router.post("/usuarios/{usuario_id}/ativar")
def ativar(usuario_id: str, sessao: SessaoDep, ator: AtorDep, request: Request) -> dict[str, str]:
    """Para quem não consegue entrar porque não ativou o e-mail."""
    u = _usuario(sessao, usuario_id)
    u.email_confirmado = True
    _log_admin(request, ator, "admin_ativou", "Conta ativada pelo admin", u.email)
    return {"detail": f"{u.nome} ativada: já consegue entrar com e-mail e senha."}


@router.post("/usuarios/{usuario_id}/desativar")
def desativar(
    usuario_id: str, sessao: SessaoDep, ator: AtorDep, request: Request
) -> dict[str, str]:
    u = _usuario(sessao, usuario_id)
    if u.admin:
        raise HTTPException(
            status_code=http.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Não dá para desativar um administrador.",
        )
    u.ativo = False
    _log_admin(request, ator, "admin_desativou", "Conta desativada pelo admin", u.email)
    return {"detail": f"{u.nome} desativado: não consegue mais entrar. Os dados ficam guardados."}


@router.post("/usuarios/{usuario_id}/reativar")
def reativar(usuario_id: str, sessao: SessaoDep, ator: AtorDep, request: Request) -> dict[str, str]:
    u = _usuario(sessao, usuario_id)
    u.ativo = True
    _log_admin(request, ator, "admin_reativou", "Conta reativada pelo admin", u.email)
    return {"detail": f"{u.nome} reativado."}


@router.post("/usuarios/{usuario_id}/nova-senha")
def mandar_nova_senha(
    usuario_id: str,
    sessao: SessaoDep,
    emissor: EmissorDep,
    ator: AtorDep,
    request: Request,
    tarefas: BackgroundTasks,
) -> dict[str, str]:
    u = _usuario(sessao, usuario_id)
    enviar_nova_senha(u, emissor, request, tarefas)
    _log_admin(request, ator, "admin_nova_senha", "Link de nova senha enviado pelo admin", u.email)
    return {"detail": f"Link de nova senha enviado para {u.email}."}


@router.post("/usuarios/{usuario_id}/reenviar-ativacao")
def reenviar_ativacao(
    usuario_id: str,
    sessao: SessaoDep,
    emissor: EmissorDep,
    ator: AtorDep,
    request: Request,
    tarefas: BackgroundTasks,
) -> dict[str, str]:
    u = _usuario(sessao, usuario_id)
    if u.email_confirmado:
        return {"detail": f"{u.nome} já está ativada."}
    enviar_confirmacao(u, emissor, request, tarefas)
    _log_admin(request, ator, "admin_reenviou_ativacao", "E-mail de ativação reenviado", u.email)
    return {"detail": f"E-mail de ativação reenviado para {u.email}."}


# ---------------- convites ----------------


@router.post("/convites", status_code=http.HTTP_201_CREATED)
def convidar(
    dados: ConviteEntrada,
    sessao: SessaoDep,
    emissor: EmissorDep,
    ator: AtorDep,
    request: Request,
    tarefas: BackgroundTasks,
) -> dict[str, str]:
    if sessao.scalar(select(UsuarioModelo).where(UsuarioModelo.email == dados.email)):
        raise HTTPException(
            status_code=http.HTTP_409_CONFLICT, detail="Esse e-mail já tem conta no No Corre."
        )
    convite = sessao.scalar(
        select(ConviteModelo).where(
            ConviteModelo.email == dados.email, ConviteModelo.status == "pendente"
        )
    )
    admin = sessao.scalar(select(UsuarioModelo).where(UsuarioModelo.email == ator))
    if convite is None:
        convite = ConviteModelo(
            id=str(uuid.uuid4()),
            nome=dados.nome,
            email=dados.email,
            status="pendente",
            convidado_por=admin.id if admin else None,
            enviado_em=agora(),
        )
        sessao.add(convite)
    else:
        convite.nome, convite.enviado_em = dados.nome, agora()
    sessao.flush()
    enviar_convite(convite, emissor, request, tarefas)
    _log_admin(request, ator, "convite_enviado", "Convite enviado", convite.email)
    return {"detail": f"Convite enviado para {convite.email}."}


def _convite(sessao: Session, convite_id: str) -> ConviteModelo:
    c = sessao.get(ConviteModelo, convite_id)
    if c is None or c.status != "pendente":
        raise HTTPException(status_code=http.HTTP_404_NOT_FOUND, detail="Convite não encontrado.")
    return c


@router.post("/convites/{convite_id}/reenviar")
def reenviar_convite(
    convite_id: str,
    sessao: SessaoDep,
    emissor: EmissorDep,
    ator: AtorDep,
    request: Request,
    tarefas: BackgroundTasks,
) -> dict[str, str]:
    c = _convite(sessao, convite_id)
    c.enviado_em = agora()
    enviar_convite(c, emissor, request, tarefas)
    _log_admin(request, ator, "convite_reenviado", "Convite reenviado", c.email)
    return {"detail": f"Convite reenviado para {c.email}."}


@router.delete("/convites/{convite_id}")
def cancelar_convite(
    convite_id: str, sessao: SessaoDep, ator: AtorDep, request: Request
) -> dict[str, str]:
    c = _convite(sessao, convite_id)
    c.status = "cancelado"
    _log_admin(request, ator, "convite_cancelado", "Convite cancelado", c.email)
    return {"detail": f"Convite de {c.nome} cancelado; o link dele não vale mais."}


# ---------------- logs ----------------


@router.get("/logs", response_model=LogsSaida)
def logs(
    sessao: SessaoDep,
    nivel: Annotated[str, Query(pattern="^(todos|erro|aviso|info)$")] = "todos",
    tipo: Annotated[str, Query(pattern="^(todos|acesso|sistema|email)$")] = "todos",
    busca: str = "",
    limite: Annotated[int, Query(ge=1, le=500)] = 200,
) -> LogsSaida:
    consulta = select(EventoModelo).order_by(EventoModelo.id.desc())
    if tipo != "todos":
        consulta = consulta.where(EventoModelo.tipo == tipo)
    eventos = list(sessao.scalars(consulta.limit(2000)))
    termo = busca.strip().lower()
    if termo:
        eventos = [
            e
            for e in eventos
            if termo in f"{e.mensagem} {e.email or ''} {e.rota or ''} {e.acao}".lower()
        ]
    contagem = {
        "todos": len(eventos),
        **{n: sum(1 for e in eventos if e.nivel == n) for n in ("erro", "aviso", "info")},
    }
    if nivel != "todos":
        eventos = [e for e in eventos if e.nivel == nivel]
    return LogsSaida(logs=[_evento_saida(e) for e in eventos[:limite]], contagem=contagem)


# ---------------- indicadores ----------------


@router.get("/indicadores", response_model=IndicadoresSaida)
def indicadores(
    sessao: SessaoDep, dias: Annotated[int, Query(ge=7, le=90)] = 14
) -> IndicadoresSaida:
    hoje = no_fuso(agora()).date()
    janela = max(dias, 14)  # os 14 dias também servem à comparação semanal
    primeiro = hoje - timedelta(days=janela - 1)
    datas = [primeiro + timedelta(days=i) for i in range(janela)]
    posicao = {d: i for i, d in enumerate(datas)}
    logins, cadastros, erros = [0] * janela, [0] * janela, [0] * janela

    eventos = list(sessao.scalars(select(EventoModelo)))
    for e in eventos:
        i = posicao.get(no_fuso(e.criado_em).date())
        if i is None:
            continue
        if e.acao == "login_ok":
            logins[i] += 1
        if e.nivel == "erro":
            erros[i] += 1
    usuarios = list(sessao.scalars(select(UsuarioModelo)))
    for u in usuarios:
        i = posicao.get(no_fuso(u.criado_em).date())
        if i is not None:
            cadastros[i] += 1

    semana, anterior = sum(logins[-7:]), sum(logins[-14:-7])
    variacao = round((semana - anterior) / anterior * 100) if anterior else None
    limite_24h = agora() - timedelta(hours=24)
    situacoes = {u.id: status_do_usuario(u) for u in usuarios}

    pendencias: list[PendenciaSaida] = []
    for u in sorted(usuarios, key=lambda x: x.nome.lower()):
        if situacoes[u.id] == "desativado":
            continue
        if situacoes[u.id] == "nao_ativou":
            motivo = "não consegue entrar: não ativou o e-mail"
        else:
            falhas = falhas_recentes(sessao, u.email)
            if falhas < TENTATIVAS_ALERTA:
                continue
            motivo = f"{falhas} senhas erradas em 24 h"
        pendencias.append(
            PendenciaSaida(usuario_id=u.id, nome=u.nome, email=u.email, motivo=motivo)
        )

    erros_recentes = sorted(
        (e for e in eventos if e.nivel == "erro"), key=lambda e: e.id, reverse=True
    )
    return IndicadoresSaida(
        usuarios_ativos=sum(1 for s in situacoes.values() if s in ("master", "ativo")),
        logins_7d=semana,
        logins_7d_variacao=variacao,
        erros_24h=sum(
            1 for e in eventos if e.nivel == "erro" and em_utc(e.criado_em) >= limite_24h
        ),
        nao_ativaram=sum(1 for s in situacoes.values() if s == "nao_ativou"),
        dias=[d.isoformat() for d in datas[-dias:]],
        logins=logins[-dias:],
        cadastros=cadastros[-dias:],
        erros=erros[-dias:],
        ultimos_erros=[_evento_saida(e) for e in erros_recentes[:3]],
        pendencias=pendencias,
    )
