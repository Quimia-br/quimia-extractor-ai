import asyncio
from types import SimpleNamespace

import pytest
import httpx
from openai import APIConnectionError

from app.core.config import AppConfig
from app.core.exceptions import ConfiguracaoLLMInvalida, CreditoLLMInsuficiente, ErroLLM
from app.schemas.respostas_llm import RespostaComposicaoLLM
from app.clients.llm import LLMClient

JSON_VALIDO = '{"compostos": [], "pendencias": []}'


def resposta_chat(conteudo, finish_reason="stop"):
    escolha = SimpleNamespace(
        finish_reason=finish_reason,
        message=SimpleNamespace(content=conteudo),
    )
    return SimpleNamespace(choices=[escolha])


class CompletionsFake:
    def __init__(self, resposta):
        self.resposta = resposta
        self.parametros = None

    async def create(self, **parametros):
        self.parametros = parametros
        return self.resposta


class CompletionsComErro:
    async def create(self, **parametros):
        raise APIConnectionError(
            request=httpx.Request("POST", "https://api.commandcode.ai/provider/v1/chat/completions")
        )


class SDKFake:
    def __init__(self, resposta):
        self.chat = SimpleNamespace(completions=CompletionsFake(resposta))


def config_llm(**alteracoes):
    return AppConfig(
        llm_api_key="chave-falsa",
        llm_model="modelo-falso",
        **alteracoes,
    )


def responder(cliente):
    return asyncio.run(
        cliente.responder_estruturado(
            modelo=RespostaComposicaoLLM,
            instrucoes="Extraia.",
            entrada="Texto da ficha.",
        )
    )


def test_cliente_llm_chama_chat_completions_em_modo_json_com_schema_no_prompt():
    sdk = SDKFake(resposta_chat(JSON_VALIDO))
    cliente = LLMClient(config=config_llm(), client=sdk)

    resultado = responder(cliente)

    assert resultado == RespostaComposicaoLLM(compostos=[], pendencias=[])
    parametros = sdk.chat.completions.parametros
    assert parametros["model"] == "modelo-falso"
    assert parametros["response_format"] == {"type": "json_object"}
    assert parametros["max_tokens"] == 8000
    assert "reasoning_effort" not in parametros
    sistema, usuario = parametros["messages"]
    assert sistema["role"] == "system"
    assert sistema["content"].startswith("Extraia.")
    assert '"compostos"' in sistema["content"]
    assert usuario == {"role": "user", "content": "Texto da ficha."}


def test_cliente_llm_repassa_limite_de_tokens_e_raciocinio_configurados():
    sdk = SDKFake(resposta_chat(JSON_VALIDO))
    cliente = LLMClient(
        config=config_llm(llm_max_output_tokens=2048, llm_reasoning_effort="low"),
        client=sdk,
    )

    responder(cliente)

    assert sdk.chat.completions.parametros["max_tokens"] == 2048
    assert sdk.chat.completions.parametros["reasoning_effort"] == "low"


def test_cliente_llm_rejeita_configuracao_sem_chave():
    with pytest.raises(ConfiguracaoLLMInvalida):
        LLMClient(config=AppConfig(llm_model="modelo"))


@pytest.mark.parametrize(
    "resposta",
    [
        resposta_chat("isto não é JSON"),
        resposta_chat('{"compostos": "deveria ser lista", "pendencias": []}'),
        resposta_chat(JSON_VALIDO, finish_reason="length"),
        resposta_chat(None),
        SimpleNamespace(choices=[]),
    ],
    ids=["json-malformado", "fora-do-schema", "truncada", "vazia", "sem-escolhas"],
)
def test_cliente_llm_rejeita_resposta_fora_do_contrato(resposta):
    cliente = LLMClient(config=config_llm(), client=SDKFake(resposta))

    with pytest.raises(ErroLLM):
        responder(cliente)


def test_cliente_llm_traduz_falha_do_provedor():
    sdk = SDKFake(None)
    sdk.chat.completions = CompletionsComErro()
    cliente = LLMClient(config=config_llm(), client=sdk)

    with pytest.raises(ErroLLM):
        responder(cliente)


def test_cliente_llm_usa_base_url_configurada():
    cliente = LLMClient(
        config=config_llm(llm_base_url="https://api.commandcode.ai/provider/v1")
    )

    assert str(cliente._client.base_url).startswith("https://api.commandcode.ai/provider/v1")
    asyncio.run(cliente.fechar())


def test_cliente_llm_identifica_creditos_esgotados(monkeypatch):
    class ErroLimiteFake(Exception):
        code = "credit_balance_exhausted"

    class ResponsesSemCredito:
        async def parse(self, **parametros):
            raise ErroLimiteFake()

    monkeypatch.setattr("app.clients.llm.RateLimitError", ErroLimiteFake)
    sdk = SDKFake(None)
    sdk.responses = ResponsesSemCredito()
    cliente = LLMClient(config=config_llm(), client=sdk)

    with pytest.raises(CreditoLLMInsuficiente, match="sem créditos"):
        asyncio.run(cliente.responder_estruturado(
            modelo=RespostaComposicaoLLM,
            instrucoes="Extraia.",
            entrada="Texto da ficha.",
        ))


def test_cliente_llm_cria_e_fecha_sdk_quando_nao_e_injetado():
    cliente = LLMClient(config=config_llm())

    asyncio.run(cliente.fechar())
