"""Contrato do JSON enviado pelo backend; não recebe PDF ou credenciais do banco."""
from pydantic import Field, model_validator
from app.schemas.evidencia import SchemaBase, Texto

class Documento(SchemaBase):
    id_fds: int = Field(gt=0)
    id_produto: int = Field(gt=0)
    versao: Texto
    revisao: Texto = Field(description='Identificador da revisão do upload, fornecido pelo backend.')

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
    documento: Documento
    secoes: SecoesEntrada
