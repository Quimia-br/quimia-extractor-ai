"""Extração estruturada da seção 3 da FDS."""
import math

from app.clients.llm import LLMClient
from app.prompts.base import INSTRUCOES_BASE, formatar_paginas
from app.prompts.composicao import INSTRUCOES_COMPOSICAO
from app.schemas.composto import Composto
from app.schemas.entrada import SecaoEntrada
from app.schemas.respostas_llm import CompostoLLM, RespostaComposicaoLLM, para_pendencias
from app.schemas.saida import ComposicaoExtraida, Pendencia
from app.validators.extracao import vincular_pendencias_aos_compostos

# NUMERIC(5,2) da quimia-api: até 999.99, com duas casas decimais.
CONCENTRACAO_MINIMA = 0.0
CONCENTRACAO_MAXIMA = 999.99
CASAS_CONCENTRACAO = 2
LIMITE_PERCENTUAL = 100.0
UNIDADE_PERCENTUAL = "%"


async def extrair_composicao(
    cliente: LLMClient,
    secao: SecaoEntrada,
) -> tuple[ComposicaoExtraida, list[Pendencia]]:
    resposta = await cliente.responder_estruturado(
        modelo=RespostaComposicaoLLM,
        instrucoes=f"{INSTRUCOES_BASE}\n\n{INSTRUCOES_COMPOSICAO}",
        entrada=formatar_paginas(secao),
    )
    pendencias = para_pendencias(resposta.pendencias)
    compostos = [_converter_composto(item, pendencias) for item in resposta.compostos]
    vincular_pendencias_aos_compostos(compostos, pendencias)
    return ComposicaoExtraida(encontrada=True, compostos=compostos), pendencias


def _converter_composto(item: CompostoLLM, pendencias: list[Pendencia]) -> Composto:
    """Anula concentrações fora do contrato e registra cada anulação como pendência."""
    limite = LIMITE_PERCENTUAL if item.unidade_concentracao == UNIDADE_PERCENTUAL else CONCENTRACAO_MAXIMA
    concentracoes = {}
    for campo in ("concentracao_min", "concentracao_max"):
        original = getattr(item, campo)
        valido = _concentracao_representavel(original, limite)
        if original is not None and valido is None:
            pendencias.append(
                _pendencia_contraditoria(
                    item,
                    campo,
                    f"A concentração de {item.nome} ({original}) está fora da faixa de "
                    f"0 a {limite:g}{_sufixo_unidade(item)} e foi omitida.",
                )
            )
        concentracoes[campo] = valido

    minimo, maximo = concentracoes["concentracao_min"], concentracoes["concentracao_max"]
    if minimo is not None and maximo is not None and minimo > maximo:
        concentracoes = {"concentracao_min": None, "concentracao_max": None}
        pendencias.append(
            _pendencia_contraditoria(
                item,
                "concentracao",
                f"A concentração mínima de {item.nome} ({minimo}) supera a máxima ({maximo}); "
                "a faixa foi omitida.",
            )
        )

    return Composto.model_validate(
        {**item.model_dump(exclude={"concentracao_min", "concentracao_max"}), **concentracoes}
    )


def _concentracao_representavel(valor: float | None, limite: float) -> float | None:
    if valor is None or not math.isfinite(valor):
        return None
    arredondado = round(valor, CASAS_CONCENTRACAO)
    if not CONCENTRACAO_MINIMA <= arredondado <= limite:
        return None
    return arredondado


def _sufixo_unidade(item: CompostoLLM) -> str:
    return f" {item.unidade_concentracao}" if item.unidade_concentracao else ""


def _pendencia_contraditoria(item: CompostoLLM, campo: str, descricao: str) -> Pendencia:
    return Pendencia(
        secao="03",
        campo=campo,
        motivo="dados_contraditorios",
        descricao=descricao,
        evidencias=item.evidencias,
    )
