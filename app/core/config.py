"""Configuração lida do ambiente, sem exigir credenciais durante imports."""
import os

from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel, Field

load_dotenv(find_dotenv())


class AppConfig(BaseModel):
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    llm_timeout_seconds: float | None = Field(default=None, gt=0)
    llm_max_retries: int | None = Field(default=None, ge=0)
    llm_max_output_tokens: int | None = Field(default=None, gt=0)
    llm_reasoning_effort: str | None = None
    extrator_api_token: str | None = None
    extrator_timeout_seconds: float | None = Field(default=None, gt=0)


def carregar_config() -> AppConfig:
    """Carrega e converte as variáveis; chaves podem faltar no ambiente de testes."""
    return AppConfig(
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_model=os.getenv("LLM_MODEL"),
        llm_base_url=os.getenv("LLM_BASE_URL") or None,
        llm_timeout_seconds=os.getenv("LLM_TIMEOUT_SECONDS"),
        llm_max_retries=os.getenv("LLM_MAX_RETRIES"),
        llm_max_output_tokens=os.getenv("LLM_MAX_OUTPUT_TOKENS"),
        llm_reasoning_effort=os.getenv("LLM_REASONING_EFFORT"),
        extrator_api_token=os.getenv("EXTRATOR_API_TOKEN") or None,
        extrator_timeout_seconds=os.getenv("EXTRATOR_TIMEOUT_SECONDS") or None,
    )
