"""Extração estruturada da seção 4 da FDS."""
from app.clients.llm import LLMClient
from app.prompts.base import INSTRUCOES_BASE, formatar_paginas
from app.prompts.primeiros_socorros import INSTRUCOES_PRIMEIROS_SOCORROS
from app.schemas.entrada import SecaoEntrada
from app.schemas.respostas_llm import RespostaPrimeirosSocorrosLLM
from app.schemas.saida import Pendencia, PrimeirosSocorrosExtraidos


async def extrair_primeiros_socorros(
    cliente: LLMClient,
    secao: SecaoEntrada,
) -> tuple[PrimeirosSocorrosExtraidos, list[Pendencia]]:
    resposta = await cliente.responder_estruturado(
        modelo=RespostaPrimeirosSocorrosLLM,
        instrucoes=f"{INSTRUCOES_BASE}\n\n{INSTRUCOES_PRIMEIROS_SOCORROS}",
        entrada=formatar_paginas(secao),
    )
    return (
        PrimeirosSocorrosExtraidos(
            encontrada=True,
            primeiros_socorros=resposta.primeiros_socorros,
            orientacoes_gerais=resposta.orientacoes_gerais,
            notas_ao_medico=resposta.notas_ao_medico,
        ),
        resposta.pendencias,
    )
