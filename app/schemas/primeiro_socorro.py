"""Seção 4 para o Saiba mais; não participa do match."""
from typing import Literal
from pydantic import Field
from .evidencia import Evidencia, SchemaBase, Texto

class PrimeiroSocorro(SchemaBase):
    rota_exposicao: Literal['inalacao', 'pele', 'olhos', 'ingestao']
    descricao: Texto | None
    sintomas: Texto | None
    tratamento_especial: Texto | None
    atencao_medica_imediata: bool | None = Field(description='Null quando o documento não permite determinar; ausência não significa false.')
    evidencias: list[Evidencia] = Field(min_length=1)

class OrientacaoGeral(SchemaBase):
    descricao: Texto
    evidencias: list[Evidencia] = Field(min_length=1)
