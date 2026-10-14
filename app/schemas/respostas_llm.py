"""Formatos internos exigidos do modelo; não fazem parte da resposta HTTP."""
from typing import Literal

from app.schemas.evidencia import Evidencia, SchemaBase
from app.schemas.incompatibilidade import Incompatibilidade
from app.schemas.primeiro_socorro import OrientacaoGeral, PrimeiroSocorro
from app.schemas.saida import Pendencia
from app.schemas.composto import Composto


class RespostaComposicaoLLM(SchemaBase):
    compostos: list[Composto]
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
