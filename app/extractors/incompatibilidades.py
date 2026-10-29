"""Extração estruturada da seção 10 da FDS."""
from app.clients.llm import LLMClient
from app.prompts.base import INSTRUCOES_BASE, formatar_paginas
from app.prompts.incompatibilidades import INSTRUCOES_INCOMPATIBILIDADES
from app.schemas.entrada import SecaoEntrada
from app.schemas.respostas_llm import RespostaIncompatibilidadesLLM, para_pendencias
from app.schemas.saida import IncompatibilidadesExtraidas, Pendencia


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
            situacao=resposta.situacao,
            incompatibilidades=resposta.incompatibilidades,
            evidencias=resposta.evidencias,
        ),
        para_pendencias(resposta.pendencias),
    )
