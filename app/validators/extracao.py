"""Regras compartilhadas para pendências e citações de evidência."""
import re
import unicodedata

from pydantic import BaseModel

from app.core.exceptions import EvidenciaInvalida
from app.schemas.entrada import SecaoEntrada
from app.schemas.composto import Composto
from app.schemas.saida import Pendencia, ReferenciaComposto

MENSAGEM_PENDENCIA = "Informações ausentes, verifique o documento anexado"
CAMPOS_DO_COMPOSTO = {
    "nome",
    "cas_numero",
    "concentracao",
    "concentracao_min",
    "concentracao_max",
    "unidade_concentracao",
}


def criar_pendencia_secao_nao_localizada(secao: str) -> Pendencia:
    return Pendencia(
        secao=secao,
        campo="secao",
        motivo="secao_nao_localizada",
        descricao=f"A seção {secao} não foi localizada na ficha.",
        evidencias=[],
    )


def criar_pendencia_informacao_ausente(secao: str, campo: str, descricao: str) -> Pendencia:
    return Pendencia(
        secao=secao,
        campo=campo,
        motivo="informacao_ausente",
        descricao=descricao,
        evidencias=[],
    )


def validar_secao_das_pendencias(pendencias: list[Pendencia], secao: str) -> None:
    if any(pendencia.secao != secao for pendencia in pendencias):
        raise EvidenciaInvalida("Uma pendência foi associada à seção errada.")


def _normalizar_citacao(texto: str) -> str:
    texto = unicodedata.normalize("NFKC", texto).casefold()
    return re.sub(r"\s+", " ", texto).strip()


def _iterar_evidencias(valor):
    if isinstance(valor, BaseModel):
        valor = valor.model_dump(mode="python")
    if isinstance(valor, dict):
        if {"secao", "pagina", "texto_evidencia"} <= valor.keys():
            yield valor
        for item in valor.values():
            yield from _iterar_evidencias(item)
    elif isinstance(valor, (list, tuple)):
        for item in valor:
            yield from _iterar_evidencias(item)


def validar_evidencias(
    resultado: BaseModel,
    *,
    numero_secao: str,
    entrada: SecaoEntrada,
) -> None:
    paginas = {pagina.numero: pagina.texto for pagina in entrada.paginas}
    for evidencia in _iterar_evidencias(resultado):
        if evidencia["secao"] != numero_secao:
            raise EvidenciaInvalida("Uma evidência foi associada à seção errada.")
        texto_fonte = paginas.get(evidencia["pagina"])
        citacao = evidencia["texto_evidencia"]
        if texto_fonte is None or _normalizar_citacao(citacao) not in _normalizar_citacao(texto_fonte):
            raise EvidenciaInvalida(
                "Uma evidência gerada não corresponde ao texto recebido do documento."
            )


def vincular_pendencias_aos_compostos(compostos: list[Composto], pendencias: list[Pendencia]) -> None:
    """Aponta, em cada pendência de um campo do composto, qual composto ela descreve.

    O vínculo vem das citações: a pendência aponta o composto cuja evidência ela repete. Sem correspondência única,
    só um composto na seção resolve; do contrário a pendência segue sem referência, nunca com um palpite.
    """
    citacoes = [
        {_normalizar_citacao(evidencia.texto_evidencia) for evidencia in composto.evidencias}
        for composto in compostos
    ]
    for pendencia in pendencias:
        if pendencia.secao != "03" or pendencia.campo not in CAMPOS_DO_COMPOSTO:
            continue
        citadas = {_normalizar_citacao(evidencia.texto_evidencia) for evidencia in pendencia.evidencias}
        candidatos = [indice for indice, doComposto in enumerate(citacoes) if citadas & doComposto]
        if len(candidatos) == 1:
            indice = candidatos[0]
        elif not candidatos and len(compostos) == 1:
            indice = 0
        else:
            continue
        pendencia.composto = ReferenciaComposto(
            indice=indice, nome=compostos[indice].nome, cas_numero=compostos[indice].cas_numero
        )
