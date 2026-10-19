"""Falhas controladas do serviço de extração."""


class ConfiguracaoLLMInvalida(Exception):
    """Credenciais ou modelo de IA não foram configurados."""


class ErroLLM(Exception):
    """O provedor não retornou uma resposta estruturada utilizável."""


class EntradaInvalida(Exception):
    """Entrada excede os limites operacionais do extractor."""


class EvidenciaInvalida(Exception):
    """Citação gerada não corresponde ao texto recebido do documento."""


class ArquivoNaoPdf(Exception):
    """Arquivo enviado não é um PDF que possa ser aberto."""


class PdfSemTexto(Exception):
    """PDF não contém texto legível (ex.: documento escaneado)."""


class DocumentoNaoFds(Exception):
    """Nenhuma das seções 3, 4 ou 10 da NBR 14725 foi localizada."""
