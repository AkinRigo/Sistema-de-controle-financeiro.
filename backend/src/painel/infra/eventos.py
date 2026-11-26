"""Registro de eventos (logs) do sistema para a aba Logs do admin.

Cada evento é gravado numa sessão própria: um erro que desfaz a requisição não apaga o log.
Falhar ao registrar nunca derruba quem chamou.
"""

import logging
from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy.orm import sessionmaker

from painel.infra.modelos import EventoModelo

log = logging.getLogger("painel.eventos")

# Brasília (sem horário de verão desde 2019): usado para agrupar por dia e mostrar horas.
FUSO = timezone(timedelta(hours=-3))


def agora() -> datetime:
    return datetime.now(UTC)


def em_utc(quando: datetime) -> datetime:
    """SQLite devolve datas sem fuso (gravadas em UTC); o Postgres devolve com fuso."""
    return quando.replace(tzinfo=UTC) if quando.tzinfo is None else quando.astimezone(UTC)


def no_fuso(quando: datetime) -> datetime:
    return em_utc(quando).astimezone(FUSO)


def quando_texto(quando: datetime, referencia: datetime | None = None) -> str:
    """ "hoje 10:42", "ontem 22:51" ou "24/11 09:02", no horário de Brasília."""
    local, ref = no_fuso(quando), no_fuso(referencia or agora())
    hora = local.strftime("%H:%M")
    if local.date() == ref.date():
        return f"hoje {hora}"
    if local.date() == (ref - timedelta(days=1)).date():
        return f"ontem {hora}"
    return f"{local:%d/%m} {hora}"


def registrar(
    fabrica: sessionmaker,
    *,
    nivel: str,
    tipo: str,
    acao: str,
    mensagem: str,
    email: str | None = None,
    rota: str | None = None,
    codigo: int | None = None,
    requisicao: str | None = None,
    detalhe: str | None = None,
    quando: datetime | None = None,
) -> None:
    try:
        with fabrica() as sessao:
            sessao.add(
                EventoModelo(
                    nivel=nivel,
                    tipo=tipo,
                    acao=acao,
                    mensagem=mensagem[:300],
                    email=email,
                    rota=rota,
                    codigo=codigo,
                    requisicao=requisicao,
                    detalhe=detalhe,
                    criado_em=quando or agora(),
                )
            )
            sessao.commit()
    except Exception:  # pragma: no cover - log é o melhor esforço
        log.exception("Não deu para registrar o evento %s", acao)
