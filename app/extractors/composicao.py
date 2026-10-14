"""Extração estruturada da seção 3 da FDS."""
from app.clients.llm import LLMClient
from app.prompts.base import INSTRUCOES_BASE, formatar_paginas
from app.prompts.composicao import INSTRUCOES_COMPOSICAO
from app.schemas.entrada import SecaoEntrada
from app.schemas.respostas_llm import RespostaComposicaoLLM
from app.schemas.saida import ComposicaoExtraida, Pendencia


async def extrair_composicao(
    cliente: LLMClient,
    secao: SecaoEntrada,
) -> tuple[ComposicaoExtraida, list[Pendencia]]:
    resposta = await cliente.responder_estruturado(
        modelo=RespostaComposicaoLLM,
        instrucoes=f"{INSTRUCOES_BASE}\n\n{INSTRUCOES_COMPOSICAO}",
        entrada=formatar_paginas(secao),
    )
    return (
        ComposicaoExtraida(encontrada=True, compostos=resposta.compostos),
        resposta.pendencias,
    )
