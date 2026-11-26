"""Envio de e-mail. Em produção usa SMTP (Gmail); sem configuração, mostra o link no terminal."""

import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

log = logging.getLogger("painel.email")


class EnviadorDeEmail(Protocol):
    def enviar(self, para: str, assunto: str, texto: str, html: str) -> None: ...


class EnviadorSmtp:
    def __init__(self, servidor: str, porta: int, usuario: str, senha: str, remetente: str) -> None:
        self._servidor, self._porta = servidor, porta
        self._usuario, self._senha, self._remetente = usuario, senha, remetente

    def enviar(self, para: str, assunto: str, texto: str, html: str) -> None:
        msg = EmailMessage()
        msg["From"] = self._remetente
        msg["To"] = para
        msg["Subject"] = assunto
        msg.set_content(texto)
        msg.add_alternative(html, subtype="html")
        with smtplib.SMTP_SSL(
            self._servidor, self._porta, context=ssl.create_default_context()
        ) as s:
            s.login(self._usuario, self._senha)
            s.send_message(msg)


class EnviadorTerminal:
    """Usado quando o SMTP não está configurado: só registra no log do servidor."""

    def enviar(self, para: str, assunto: str, texto: str, html: str) -> None:
        log.warning(
            "E-mail NÃO enviado (SMTP não configurado). Para: %s | %s\n%s", para, assunto, texto
        )


def enviar_com_seguranca(enviador: EnviadorDeEmail, para: str, assunto: str, texto: str, html: str):
    """Roda em segundo plano: uma falha de envio não pode derrubar a requisição."""
    try:
        enviador.enviar(para, assunto, texto, html)
    except Exception:
        log.exception("Falha ao enviar e-mail para %s", para)
