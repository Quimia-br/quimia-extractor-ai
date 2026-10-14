"""Configuração lida do ambiente, sem exigir credenciais durante imports."""
import os

from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel, Field

load_dotenv(find_dotenv())


class AppConfig(BaseModel):
    openai_api_key: str | None = None
    openai_model: str | None = None
    llm_timeout_seconds: float | None = Field(default=None, gt=0)
    llm_max_retries: int | None = Field(default=None, ge=0)
    llm_max_output_tokens: int | None = Field(default=None, gt=0)
    llm_reasoning_effort: str | None = None


def carregar_config() -> AppConfig:
    """Carrega e converte as variáveis; chaves podem faltar no ambiente de testes."""
    return AppConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL"),
        llm_timeout_seconds=os.getenv("LLM_TIMEOUT_SECONDS"),
        llm_max_retries=os.getenv("LLM_MAX_RETRIES"),
        llm_max_output_tokens=os.getenv("LLM_MAX_OUTPUT_TOKENS"),
        llm_reasoning_effort=os.getenv("LLM_REASONING_EFFORT"),
    )
