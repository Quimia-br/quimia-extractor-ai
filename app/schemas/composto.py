"""Composição extraída; a resolução de id_substancia pertence ao backend."""
from typing import Annotated
from pydantic import Field, model_validator
from .evidencia import Evidencia, SchemaBase, Texto

Cas = Annotated[str, Field(pattern=r'^\d{2,7}-\d{2}-\d$', max_length=20)]
Concentracao = Annotated[float, Field(ge=0, le=999.99)]

class Composto(SchemaBase):
    nome: Texto
    cas_numero: Cas | None
    concentracao_min: Concentracao | None
    concentracao_max: Concentracao | None
    unidade_concentracao: Annotated[str, Field(min_length=1, max_length=20)] | None
    evidencias: list[Evidencia] = Field(min_length=1)

    @model_validator(mode='after')
    def validar_concentracao(self):
        minimo, maximo = self.concentracao_min, self.concentracao_max
        if minimo is not None and maximo is not None and minimo > maximo:
            raise ValueError('concentracao_min não pode superar concentracao_max.')
        if self.unidade_concentracao == '%' and any(v is not None and v > 100 for v in (minimo, maximo)):
            raise ValueError('Concentração percentual não pode superar 100.')
        return self
