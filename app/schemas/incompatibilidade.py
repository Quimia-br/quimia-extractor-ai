"""Termos extraídos da seção 10, sem resolver IDs ou deduzir riscos."""
from typing import Annotated, Literal
from pydantic import Field
from .composto import Cas
from .evidencia import Evidencia, SchemaBase, Texto

class Incompatibilidade(SchemaBase):
    substancia_reagente: Annotated[str, Field(min_length=1, max_length=255)]
    cas_numero: Cas | None
    descricao_risco: Texto | None
    severidade: Literal['baixa', 'media', 'alta', 'critica'] | None
    evidencias: list[Evidencia] = Field(min_length=1)
