"""Extração do texto de um PDF, página a página, sem gravar o arquivo em disco."""
import io
import logging

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.core.exceptions import ArquivoNaoPdf, PdfSemTexto

ASSINATURA_PDF = b"%PDF-"
# Abaixo disso o PDF é tratado como imagem escaneada ou sem conteúdo útil.
MIN_CARACTERES_LEGIVEIS = 20

logger = logging.getLogger(__name__)


def possui_assinatura_pdf(inicio: bytes) -> bool:
    return inicio.startswith(ASSINATURA_PDF)


def extrair_paginas(conteudo: bytes) -> list[str]:
    """Devolve o texto de cada página, na ordem do documento (índice 0 = página 1)."""
    if not possui_assinatura_pdf(conteudo):
        raise ArquivoNaoPdf("O arquivo não começa com %PDF-.")
    leitor = _abrir(conteudo)
    paginas = _ler_paginas(leitor)
    legiveis = sum(1 for caractere in "".join(paginas) if caractere.isalnum())
    if legiveis < MIN_CARACTERES_LEGIVEIS:
        raise PdfSemTexto("O PDF não contém texto legível.")
    return paginas


def _abrir(conteudo: bytes) -> PdfReader:
    try:
        leitor = PdfReader(io.BytesIO(conteudo))
    except (PyPdfError, ValueError, OSError) as erro:
        logger.warning("PDF não pôde ser aberto: %s", type(erro).__name__)
        raise ArquivoNaoPdf("O PDF está corrompido ou não pôde ser lido.") from erro
    if leitor.is_encrypted:
        try:
            decifrado = leitor.decrypt("")
        except PyPdfError as erro:
            raise PdfSemTexto("O PDF é protegido e não pôde ser lido.") from erro
        if not decifrado:
            raise PdfSemTexto("O PDF é protegido por senha.")
    return leitor


def _ler_paginas(leitor: PdfReader) -> list[str]:
    try:
        return [(pagina.extract_text() or "").replace("\x00", " ") for pagina in leitor.pages]
    except Exception as erro:
        # PDFs malformados levantam erros variados dentro do pypdf.
        logger.warning("Falha ao extrair texto do PDF: %s", type(erro).__name__)
        raise ArquivoNaoPdf("O PDF está corrompido ou não pôde ser lido.") from erro
