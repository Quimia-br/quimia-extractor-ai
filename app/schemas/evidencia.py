"""Tipos comuns e evidências documentais. Requer Pydantic 2."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

Texto = Annotated[str, Field(min_length=1)]
NumeroSecao = Literal['03', '04', '10']

class SchemaBase(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False)

class Evidencia(SchemaBase):
    secao: NumeroSecao
    pagina: int = Field(gt=0)
    texto_evidencia: Texto
