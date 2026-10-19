"""Localiza as seções 3, 4 e 10 da FDS pelos títulos da ABNT NBR 14725."""
import re
import unicodedata
from dataclasses import dataclass

from app.core.exceptions import DocumentoNaoFds
from app.schemas.entrada import ExtracaoEntrada

# Títulos das 16 seções, já sem acentos e em minúsculas. Todos são reconhecidos
# para que cada seção de interesse termine no título seguinte, qualquer que seja.
TITULOS_NBR_14725 = {
    1: r"identificacao(?! d[aeo]s? perigo)",
    2: r"identificacao d[aeo]s? perigo",
    3: r"composicao",
    4: r"(medidas de )?primeiros[\s-]*socorros",
    5: r"(medidas de )?combate a incendio",
    6: r"(medidas de )?controle para derramamento|medidas .{0,30}(derramamento|vazamento)",
    7: r"manuseio",
    8: r"controle de exposicao|protecao individual",
    9: r"propriedades fisicas",
    10: r"estabilidade",
    11: r"informacoes toxicologicas|toxicologia",
    12: r"informacoes ecologicas|ecologia",
    13: r"consideracoes sobre (a )?(destinacao|disposicao)|destinacao final|descarte",
    14: r"informacoes sobre (o )?transporte|transporte",
    15: r"(informacoes sobre )?regulamentac",
    16: r"outras informacoes",
}
SECOES_EXTRAIDAS = {3: "secao_3", 4: "secao_4", 10: "secao_10"}
# Título precisa aparecer logo após o número, não no meio de uma frase.
JANELA_TITULO = 40

_NUMERO_TITULO = re.compile(
    r"^\s*(?:(?:secao|section)\s*)?0?(\d{1,2})\s*[.:)\-–—]?\s*(?:-\s*)?(.*)$"
)


@dataclass(frozen=True)
class _Linha:
    pagina: int
    texto: str


def montar_entrada(paginas: list[str]) -> ExtracaoEntrada:
    """Monta o ExtracaoEntrada a partir do texto de cada página (índice 0 = página 1)."""
    linhas = [
        _Linha(pagina=numero, texto=linha)
        for numero, texto in enumerate(paginas, start=1)
        for linha in texto.splitlines()
    ]
    titulos = _localizar_titulos(linhas)
    secoes = {
        chave: _paginas_da_secao(linhas, titulos, numero)
        for numero, chave in SECOES_EXTRAIDAS.items()
    }
    if not any(secoes.values()):
        raise DocumentoNaoFds("Nenhuma das seções 3, 4 ou 10 foi localizada.")
    return ExtracaoEntrada.model_validate(
        {
            "secoes": {
                chave: {"encontrada": bool(paginas_secao), "paginas": paginas_secao}
                for chave, paginas_secao in secoes.items()
            }
        }
    )


def _normalizar(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    sem_acentos = "".join(c for c in decomposto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acentos).casefold().strip()


@dataclass(frozen=True)
class _Titulo:
    indice: int
    numero: int
    linhas: int


def _identificar_titulo(linha: str, proxima: str | None) -> tuple[int, int] | None:
    """Devolve (número da seção, linhas ocupadas pelo título) ou None."""
    correspondencia = _NUMERO_TITULO.match(_normalizar(linha))
    if not correspondencia:
        return None
    numero = int(correspondencia.group(1))
    padrao = TITULOS_NBR_14725.get(numero)
    if padrao is None:
        return None
    resto, linhas = correspondencia.group(2), 1
    if not resto and proxima is not None:
        # Título quebrado em duas linhas: "3." e "COMPOSIÇÃO ..." na seguinte.
        resto, linhas = _normalizar(proxima), 2
    if re.search(padrao, resto[:JANELA_TITULO]):
        return numero, linhas
    return None


def _localizar_titulos(linhas: list[_Linha]) -> list[_Titulo]:
    titulos = []
    for indice, linha in enumerate(linhas):
        proxima = linhas[indice + 1].texto if indice + 1 < len(linhas) else None
        identificado = _identificar_titulo(linha.texto, proxima)
        if identificado is not None:
            titulos.append(_Titulo(indice, *identificado))
    return titulos


def _paginas_da_secao(linhas: list[_Linha], titulos: list[_Titulo], numero: int) -> list[dict]:
    melhor: list[_Linha] = []
    for posicao, titulo in enumerate(titulos):
        if titulo.numero != numero:
            continue
        fim = next(
            (outro.indice for outro in titulos[posicao + 1 :] if outro.numero != numero),
            len(linhas),
        )
        trecho = linhas[titulo.indice : fim]
        # Título sem corpo (ex.: sumário) não conta como seção localizada.
        if _tamanho(trecho[titulo.linhas :]) == 0:
            continue
        if _tamanho(trecho) > _tamanho(melhor):
            melhor = trecho
    return _agrupar_por_pagina(melhor)


def _tamanho(trecho: list[_Linha]) -> int:
    return sum(len(linha.texto.strip()) for linha in trecho)


def _agrupar_por_pagina(trecho: list[_Linha]) -> list[dict]:
    por_pagina: dict[int, list[str]] = {}
    for linha in trecho:
        por_pagina.setdefault(linha.pagina, []).append(linha.texto)
    return [
        {"numero": pagina, "texto": "\n".join(textos).strip()}
        for pagina, textos in por_pagina.items()
        if "\n".join(textos).strip()
    ]
