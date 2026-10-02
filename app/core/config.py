import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel

load_dotenv(find_dotenv())

OBRIGATORIAS = (
    "OPENAI_API_KEY"
)


class AppConfig(BaseModel):
    openai_api_key: str | None
    openai_model: str | None
    llm_timeout_seconds: float | None
    llm_max_retries: int | None
    llm_max_output_tokens: int | None
    llm_reasoning_effort: str | None


def carregar_config() -> AppConfig:
    """Carrega e valida a configuração atual do ambiente."""
    return AppConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL"),
        llm_timeout_seconds=os.getenv("LLM_TIMEOUT_SECONDS"),
        llm_max_retries=os.getenv("LLM_MAX_RETRIES"),
        llm_max_output_tokens=os.getenv("LLM_MAX_OUTPUT_TOKENS"),
        llm_reasoning_effort=os.getenv("LLM_REASONING_EFFORT"),
        
    )


CONFIG = carregar_config()

OPENAI_API_KEY = CONFIG.openai_api_key
OPENAI_MODEL = CONFIG.openai_model
LLM_TIMEOUT_SECONDS = CONFIG.llm_timeout_seconds
LLM_MAX_RETRIES = CONFIG.llm_max_retries
LLM_MAX_OUTPUT_TOKENS = CONFIG.llm_max_output_tokens
LLM_REASONING_EFFORT = CONFIG.llm_reasoning_effort
