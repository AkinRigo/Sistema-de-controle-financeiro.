"""Quem "entende" o texto do comando de voz. Hoje é o Gemini; nos testes, um falso.

A IA só sugere uma ação em JSON. Quem confere e decide é o backend (domain/regras/voz.py).
"""

import json
import logging
import urllib.error
import urllib.request
from typing import Protocol

from painel.domain.erros import ErroDeValidacao

log = logging.getLogger(__name__)

URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"


class Interpretador(Protocol):
    def interpretar(self, pedido: str, esquema: dict) -> dict:
        """Manda o pedido e devolve o JSON que a IA respondeu, já como dict."""
        ...


class InterpretadorDesligado:
    def interpretar(self, pedido: str, esquema: dict) -> dict:
        raise ErroDeValidacao("O comando de voz está desligado neste servidor.")


class InterpretadorGemini:
    def __init__(self, chave: str, modelo: str, tempo_limite: float = 20) -> None:
        self._chave = chave
        self._modelo = modelo
        self._tempo_limite = tempo_limite

    def interpretar(self, pedido: str, esquema: dict) -> dict:
        corpo = {
            "contents": [{"role": "user", "parts": [{"text": pedido}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": esquema,
                "temperature": 0,
            },
        }
        requisicao = urllib.request.Request(
            URL_GEMINI.format(modelo=self._modelo),
            data=json.dumps(corpo).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": self._chave},
            method="POST",
        )
        try:
            with urllib.request.urlopen(requisicao, timeout=self._tempo_limite) as resposta:
                dados = json.load(resposta)
            texto = dados["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(texto)
        except urllib.error.HTTPError as erro:
            log.warning("Gemini respondeu %s: %s", erro.code, erro.read()[:300])
            raise ErroDeValidacao("O serviço de voz não respondeu agora. Tenta de novo.") from erro
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError) as erro:
            log.warning("Falha ao falar com o Gemini: %r", erro)
            raise ErroDeValidacao("O serviço de voz não respondeu agora. Tenta de novo.") from erro
