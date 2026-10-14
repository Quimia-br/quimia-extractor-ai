"""Texto das páginas das seções que serão analisadas."""
from pydantic import Field, model_validator

from app.schemas.evidencia import SchemaBase, Texto

class Pagina(SchemaBase):
    numero: int = Field(gt=0)
    texto: Texto


class SecaoEntrada(SchemaBase):
    encontrada: bool
    paginas: list[Pagina]

    @model_validator(mode='after')
    def validar_paginas(self):
        if self.encontrada != bool(self.paginas):
            raise ValueError('Seção encontrada exige páginas; seção não localizada exige lista vazia.')
        numeros = [pagina.numero for pagina in self.paginas]
        if len(numeros) != len(set(numeros)):
            raise ValueError('Uma seção não pode conter números de página duplicados.')
        return self


class SecoesEntrada(SchemaBase):
    secao_3: SecaoEntrada
    secao_4: SecaoEntrada
    secao_10: SecaoEntrada


class ExtracaoEntrada(SchemaBase):
    secoes: SecoesEntrada
