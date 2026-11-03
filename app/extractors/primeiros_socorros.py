"""Extração estruturada da seção 4 da FDS."""
import logging
import re
import unicodedata

from app.clients.llm import LLMClient
from app.prompts.base import INSTRUCOES_BASE, formatar_paginas
from app.prompts.primeiros_socorros import INSTRUCOES_PRIMEIROS_SOCORROS
from app.schemas.entrada import SecaoEntrada
from app.schemas.primeiro_socorro import PrimeiroSocorro
from app.schemas.respostas_llm import RespostaPrimeirosSocorrosLLM, para_pendencias
from app.schemas.saida import Pendencia, PrimeirosSocorrosExtraidos

logger = logging.getLogger(__name__)

# "Não é necessário atendimento médico", "dispensa", "sem necessidade": a ficha precisa negar a urgência por escrito.
NEGACAO_DE_URGENCIA = re.compile(
    r"\bnao\s+(?:e\s+|ha\s+|sera\s+)?(?:necessari|necessita|requer|precisa|exige|ha\s+necessidade)"
    r"|\bdispensa|\bsem\s+necessidade"
)


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
            primeiros_socorros=[_urgencia_so_se_declarada(item) for item in resposta.primeiros_socorros],
            orientacoes_gerais=resposta.orientacoes_gerais,
            notas_ao_medico=resposta.notas_ao_medico,
        ),
        para_pendencias(resposta.pendencias),
    )


def _urgencia_so_se_declarada(item: PrimeiroSocorro) -> PrimeiroSocorro:
    """`false` em atencao_medica_imediata afirma que não precisa de médico; sem a negação escrita, volta a `null`."""
    if item.atencao_medica_imediata is not False:
        return item
    citado = " ".join(
        [*(e.texto_evidencia for e in item.evidencias), item.descricao or "", item.tratamento_especial or ""]
    )
    if NEGACAO_DE_URGENCIA.search(_sem_acento(citado)):
        return item
    logger.warning("atencao_medica_imediata=false sem negação no texto (%s); mantido como null.", item.rota_exposicao)
    return item.model_copy(update={"atencao_medica_imediata": None})


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto).casefold()
    return "".join(c for c in decomposto if not unicodedata.combining(c))
