"""Valida limites de tamanho antes de enviar texto do documento ao provedor."""
from app.core.exceptions import EntradaInvalida
from app.schemas.entrada import ExtracaoEntrada

MAX_CARACTERES_POR_PAGINA = 30_000
MAX_CARACTERES_POR_REQUISICAO = 120_000


def validar_documento(entrada: ExtracaoEntrada) -> None:
    paginas = [
        pagina
        for secao in (
            entrada.secoes.secao_3,
            entrada.secoes.secao_4,
            entrada.secoes.secao_10,
        )
        for pagina in secao.paginas
    ]
    if any(len(pagina.texto) > MAX_CARACTERES_POR_PAGINA for pagina in paginas):
        raise EntradaInvalida(
            f"Cada página deve ter no máximo {MAX_CARACTERES_POR_PAGINA} caracteres."
        )
    total = sum(len(pagina.texto) for pagina in paginas)
    if total > MAX_CARACTERES_POR_REQUISICAO:
        raise EntradaInvalida(
            f"O texto total deve ter no máximo {MAX_CARACTERES_POR_REQUISICAO} caracteres."
        )
