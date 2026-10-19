"""Adaptador assíncrono do provedor de IA com saída Pydantic estruturada.

Usa Chat Completions (compatível com a Command Code e outros provedores OpenAI)
em modo JSON; o contrato é garantido pela validação Pydantic, não pelo provedor.
"""
import json
from typing import TypeVar

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, ValidationError

from app.core.config import AppConfig, carregar_config
from app.core.exceptions import ConfiguracaoLLMInvalida, ErroLLM

Modelo = TypeVar("Modelo", bound=BaseModel)

TIMEOUT_PADRAO_SEGUNDOS = 60
TENTATIVAS_PADRAO = 2
MAX_TOKENS_PADRAO = 8000
FIM_POR_LIMITE_DE_TOKENS = "length"
INSTRUCAO_FORMATO_JSON = (
    "Responda somente com um objeto JSON válido que siga exatamente este JSON Schema, "
    "sem texto fora do JSON:\n{schema}"
)


class LLMClient:
    def __init__(self, config: AppConfig | None = None, client=None):
        self._config = config or carregar_config()
        self._owns_client = client is None
        if client is None:
            if not self._config.llm_api_key or not self._config.llm_model:
                raise ConfiguracaoLLMInvalida(
                    "LLM_API_KEY e LLM_MODEL precisam estar configurados."
                )
            client = AsyncOpenAI(
                api_key=self._config.llm_api_key,
                base_url=self._config.llm_base_url,
                timeout=self._config.llm_timeout_seconds or TIMEOUT_PADRAO_SEGUNDOS,
                max_retries=(
                    self._config.llm_max_retries
                    if self._config.llm_max_retries is not None
                    else TENTATIVAS_PADRAO
                ),
            )
        self._client = client

    async def responder_estruturado(
        self,
        *,
        modelo: type[Modelo],
        instrucoes: str,
        entrada: str,
    ) -> Modelo:
        schema = json.dumps(modelo.model_json_schema(), ensure_ascii=False)
        parametros = {
            "model": self._config.llm_model,
            "messages": [
                {
                    "role": "system",
                    "content": f"{instrucoes}\n\n{INSTRUCAO_FORMATO_JSON.format(schema=schema)}",
                },
                {"role": "user", "content": entrada},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": self._config.llm_max_output_tokens or MAX_TOKENS_PADRAO,
        }
        if self._config.llm_reasoning_effort:
            parametros["reasoning_effort"] = self._config.llm_reasoning_effort

        try:
            resposta = await self._client.chat.completions.create(**parametros)
        except OpenAIError as erro:
            raise ErroLLM("O provedor de IA não conseguiu gerar uma resposta válida.") from erro

        conteudo = _extrair_conteudo(resposta)
        try:
            return modelo.model_validate_json(conteudo)
        except ValidationError as erro:
            raise ErroLLM("O provedor de IA não retornou o formato estruturado esperado.") from erro

    async def fechar(self) -> None:
        if self._owns_client:
            await self._client.close()


def _extrair_conteudo(resposta) -> str:
    """Devolve o texto da primeira escolha; resposta vazia ou truncada é erro do provedor."""
    if not resposta.choices:
        raise ErroLLM("O provedor de IA não retornou nenhuma resposta.")
    escolha = resposta.choices[0]
    if escolha.finish_reason == FIM_POR_LIMITE_DE_TOKENS:
        raise ErroLLM("A resposta do provedor de IA foi truncada pelo limite de tokens.")
    if not escolha.message.content:
        raise ErroLLM("O provedor de IA retornou uma resposta vazia.")
    return escolha.message.content
