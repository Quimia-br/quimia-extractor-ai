"""Adaptador assíncrono do provedor de IA com saída Pydantic estruturada."""
from typing import TypeVar

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, ValidationError

from app.core.config import AppConfig, carregar_config
from app.core.exceptions import ConfiguracaoLLMInvalida, ErroLLM

Modelo = TypeVar("Modelo", bound=BaseModel)


class LLMClient:
    def __init__(self, config: AppConfig | None = None, client=None):
        self._config = config or carregar_config()
        self._owns_client = client is None
        if client is None:
            if not self._config.openai_api_key or not self._config.openai_model:
                raise ConfiguracaoLLMInvalida(
                    "OPENAI_API_KEY e OPENAI_MODEL precisam estar configurados."
                )
            client = AsyncOpenAI(
                api_key=self._config.openai_api_key,
                timeout=self._config.llm_timeout_seconds or 60,
                max_retries=(
                    self._config.llm_max_retries
                    if self._config.llm_max_retries is not None
                    else 2
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
        parametros = {
            "model": self._config.openai_model,
            "instructions": instrucoes,
            "input": entrada,
            "text_format": modelo,
            "max_output_tokens": self._config.llm_max_output_tokens or 8000,
            "store": False,
        }
        if self._config.llm_reasoning_effort:
            parametros["reasoning"] = {"effort": self._config.llm_reasoning_effort}

        try:
            resposta = await self._client.responses.parse(**parametros)
        except (OpenAIError, ValidationError) as erro:
            raise ErroLLM("O provedor de IA não conseguiu gerar uma resposta válida.") from erro

        resultado = resposta.output_parsed
        if not isinstance(resultado, modelo):
            raise ErroLLM("O provedor de IA não retornou o formato estruturado esperado.")
        return resultado

    async def fechar(self) -> None:
        if self._owns_client:
            await self._client.close()
