"""Falhas controladas do serviço de extração."""


class ConfiguracaoLLMInvalida(Exception):
    """Credenciais ou modelo de IA não foram configurados."""


class ErroLLM(Exception):
    """O provedor não retornou uma resposta estruturada utilizável."""


class EntradaInvalida(Exception):
    """Entrada excede os limites operacionais do extractor."""


class EvidenciaInvalida(Exception):
    """Citação gerada não corresponde ao texto recebido do documento."""
