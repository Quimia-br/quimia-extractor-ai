"""Extração estruturada da seção 10 da FDS."""
import logging

from app.clients.llm import LLMClient
from app.prompts.base import INSTRUCOES_BASE, formatar_paginas
from app.prompts.incompatibilidades import INSTRUCOES_INCOMPATIBILIDADES
from app.schemas.entrada import SecaoEntrada
from app.schemas.respostas_llm import RespostaIncompatibilidadesLLM, para_pendencias
from app.schemas.saida import IncompatibilidadesExtraidas, Pendencia

logger = logging.getLogger(__name__)


async def extrair_incompatibilidades(
    cliente: LLMClient,
    secao: SecaoEntrada,
) -> tuple[IncompatibilidadesExtraidas, list[Pendencia]]:
    resposta = await cliente.responder_estruturado(
        modelo=RespostaIncompatibilidadesLLM,
        instrucoes=f"{INSTRUCOES_BASE}\n\n{INSTRUCOES_INCOMPATIBILIDADES}",
        entrada=formatar_paginas(secao),
    )
    return (
        IncompatibilidadesExtraidas(
            encontrada=True,
            situacao=_situacao_coerente(resposta),
            incompatibilidades=resposta.incompatibilidades,
            evidencias=resposta.evidencias,
        ),
        para_pendencias(resposta.pendencias),
    )


def _situacao_coerente(resposta: RespostaIncompatibilidadesLLM) -> str:
    """Alinha a situação ao que a IA de fato devolveu, em vez de recusar a seção por um rótulo incoerente.

    Itens extraídos só existem em `identificadas`; sem itens, `identificadas` vira `nao_especificadas`, e uma
    `ausencia_declarada` sem a evidência da declaração também (a ausência não pode ser afirmada sem citação).
    """
    if resposta.incompatibilidades:
        situacao = "identificadas"
    elif resposta.situacao == "identificadas":
        situacao = "nao_especificadas"
    elif resposta.situacao == "ausencia_declarada" and not resposta.evidencias:
        situacao = "nao_especificadas"
    else:
        situacao = resposta.situacao
    if situacao != resposta.situacao:
        logger.warning("Situação da seção 10 corrigida de %s para %s.", resposta.situacao, situacao)
    return situacao
