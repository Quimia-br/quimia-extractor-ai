"""Contrato HTTP de falhas da extração."""
from typing import Literal

from app.schemas.evidencia import SchemaBase


class ErroDetalhe(SchemaBase):
    campo: str
    mensagem: str


class Erro(SchemaBase):
    tipo: Literal["json_invalido", "validacao", "configuracao", "processamento", "acesso"]
    mensagem: str
    detalhes: list[ErroDetalhe]


class ErroResposta(SchemaBase):
    erro: Erro
