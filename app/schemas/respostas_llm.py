"""Formatos internos exigidos do modelo; não fazem parte da resposta HTTP."""
from typing import Annotated, Literal

from pydantic import ConfigDict, Field

from app.schemas.composto import Cas
from app.schemas.evidencia import Evidencia, SchemaBase, Texto
from app.schemas.incompatibilidade import Incompatibilidade
from app.schemas.primeiro_socorro import OrientacaoGeral, PrimeiroSocorro
from app.schemas.saida import Pendencia


class CompostoLLM(SchemaBase):
    """Composto como a IA o devolve, sem limites de faixa nem a regra min ≤ max.

    A conversão para `Composto` anula as concentrações fora do contrato e
    registra pendências, em vez de recusar a resposta inteira.
    """

    model_config = ConfigDict(allow_inf_nan=True)

    nome: Texto
    cas_numero: Cas | None
    concentracao_min: float | None
    concentracao_max: float | None
    unidade_concentracao: Annotated[str, Field(min_length=1, max_length=20)] | None
    evidencias: list[Evidencia] = Field(min_length=1)


class RespostaComposicaoLLM(SchemaBase):
    compostos: list[CompostoLLM]
    pendencias: list[Pendencia]


class RespostaPrimeirosSocorrosLLM(SchemaBase):
    primeiros_socorros: list[PrimeiroSocorro]
    orientacoes_gerais: list[OrientacaoGeral]
    notas_ao_medico: list[OrientacaoGeral]
    pendencias: list[Pendencia]


class RespostaIncompatibilidadesLLM(SchemaBase):
    situacao: Literal['identificadas', 'ausencia_declarada', 'nao_especificadas']
    incompatibilidades: list[Incompatibilidade]
    evidencias: list[Evidencia]
    pendencias: list[Pendencia]
