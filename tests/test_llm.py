import asyncio
from types import SimpleNamespace

import pytest
import httpx
from openai import APIConnectionError

from app.core.config import AppConfig
from app.core.exceptions import ConfiguracaoLLMInvalida, ErroLLM
from app.schemas.respostas_llm import RespostaComposicaoLLM
from app.clients.llm import LLMClient


class ResponsesFake:
    def __init__(self, resposta):
        self.resposta = resposta
        self.parametros = None

    async def parse(self, **parametros):
        self.parametros = parametros
        return SimpleNamespace(output_parsed=self.resposta)


class ResponsesComErro:
    async def parse(self, **parametros):
        raise APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))


class SDKFake:
    def __init__(self, resposta):
        self.responses = ResponsesFake(resposta)


def config_llm(**alteracoes):
    return AppConfig(
        openai_api_key="chave-falsa",
        openai_model="modelo-falso",
        **alteracoes,
    )


def test_cliente_llm_chama_responses_parse_com_schema_pydantic():
    resposta_esperada = RespostaComposicaoLLM(compostos=[], pendencias=[])
    sdk = SDKFake(resposta_esperada)
    cliente = LLMClient(config=config_llm(), client=sdk)

    resultado = asyncio.run(
        cliente.responder_estruturado(
        modelo=RespostaComposicaoLLM,
        instrucoes="Extraia.",
        entrada="Texto da ficha.",
        )
    )

    assert resultado == resposta_esperada
    assert sdk.responses.parametros["text_format"] is RespostaComposicaoLLM
    assert sdk.responses.parametros["input"] == "Texto da ficha."
    assert sdk.responses.parametros["store"] is False


def test_cliente_llm_rejeita_configuracao_sem_chave():
    with pytest.raises(ConfiguracaoLLMInvalida):
        LLMClient(config=AppConfig(openai_model="modelo"))


def test_cliente_llm_rejeita_resposta_sem_schema_parseado():
    sdk = SDKFake(None)
    cliente = LLMClient(config=config_llm(), client=sdk)

    with pytest.raises(ErroLLM):
        asyncio.run(
            cliente.responder_estruturado(
            modelo=RespostaComposicaoLLM,
            instrucoes="Extraia.",
            entrada="Texto da ficha.",
            )
        )


def test_cliente_llm_traduz_falha_do_provedor():
    sdk = SDKFake(None)
    sdk.responses = ResponsesComErro()
    cliente = LLMClient(config=config_llm(), client=sdk)

    with pytest.raises(ErroLLM):
        asyncio.run(
            cliente.responder_estruturado(
                modelo=RespostaComposicaoLLM,
                instrucoes="Extraia.",
                entrada="Texto da ficha.",
            )
        )


def test_cliente_llm_cria_e_fecha_sdk_quando_nao_e_injetado():
    cliente = LLMClient(config=config_llm())

    asyncio.run(cliente.fechar())
