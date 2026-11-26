"""Hash de senha (argon2id) e tokens de acesso (PASETO v4.local)."""

import hashlib
import hmac
import json

import pyseto
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from pyseto import Key

_hasher = PasswordHasher()


class TokenInvalido(Exception):
    pass


def gerar_hash_senha(senha: str) -> str:
    return _hasher.hash(senha)


def verificar_senha(senha_hash: str, senha: str) -> bool:
    try:
        return _hasher.verify(senha_hash, senha)
    except (VerificationError, InvalidHashError):
        return False


def _impressao(senha_hash: str) -> str:
    """Resumo do hash atual: trocar a senha invalida links de redefinição já enviados."""
    return hashlib.sha256(senha_hash.encode()).hexdigest()[:16]


class EmissorDeTokens:
    """Tokens PASETO v4.local. O campo "p" separa acesso de redefinição de senha."""

    VALIDADE_REDEFINICAO = 30 * 60
    VALIDADE_CONFIRMACAO = 24 * 60 * 60

    def __init__(self, chave: bytes, validade_segundos: int) -> None:
        self._chave = Key.new(version=4, purpose="local", key=chave)
        self._validade = validade_segundos

    def _emitir(self, payload: dict, validade: int) -> str:
        return pyseto.encode(self._chave, payload=payload, serializer=json, exp=validade).decode()

    def _ler(self, token: str, proposito: str) -> dict:
        try:
            decodificado = pyseto.decode(self._chave, token, deserializer=json)
        except Exception as erro:  # pyseto levanta tipos variados
            raise TokenInvalido from erro
        payload = decodificado.payload
        if (
            not isinstance(payload, dict)
            or payload.get("p") != proposito
            or not isinstance(payload.get("sub"), str)
        ):
            raise TokenInvalido
        return payload

    def emitir(self, usuario_id: str) -> str:
        return self._emitir({"sub": usuario_id, "p": "acesso"}, self._validade)

    def validar(self, token: str) -> str:
        return self._ler(token, "acesso")["sub"]

    def emitir_redefinicao(self, usuario_id: str, senha_hash: str) -> str:
        return self._emitir(
            {"sub": usuario_id, "p": "redefinir", "h": _impressao(senha_hash)},
            self.VALIDADE_REDEFINICAO,
        )

    def validar_redefinicao(self, token: str) -> tuple[str, str]:
        """Devolve (usuario_id, impressão do hash); quem chama confere a impressão."""
        payload = self._ler(token, "redefinir")
        return payload["sub"], str(payload.get("h", ""))

    def emitir_confirmacao(self, usuario_id: str) -> str:
        return self._emitir({"sub": usuario_id, "p": "confirmar"}, self.VALIDADE_CONFIRMACAO)

    def validar_confirmacao(self, token: str) -> str:
        return self._ler(token, "confirmar")["sub"]

    VALIDADE_CONVITE = 7 * 24 * 60 * 60

    def emitir_convite(self, convite_id: str) -> str:
        return self._emitir({"sub": convite_id, "p": "convite"}, self.VALIDADE_CONVITE)

    def validar_convite(self, token: str) -> str:
        return self._ler(token, "convite")["sub"]


def link_ainda_valido(impressao: str, senha_hash: str) -> bool:
    return hmac.compare_digest(impressao, _impressao(senha_hash))
