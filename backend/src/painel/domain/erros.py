"""Exceções pertencentes ao domínio."""


class ErroDeDominio(Exception):
    """Erro base para violações das regras de negócio."""


class ErroDeValidacao(ErroDeDominio, ValueError):
    """Valor ou combinação de dados inválida para o domínio."""
