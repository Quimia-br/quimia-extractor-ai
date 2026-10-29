from app.core import config


VARIAVEIS = (
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_BASE_URL",
    "LLM_TIMEOUT_SECONDS",
    "LLM_MAX_RETRIES",
    "LLM_MAX_OUTPUT_TOKENS",
    "LLM_REASONING_EFFORT",
)


def test_carregar_config_aceita_variaveis_ausentes(monkeypatch):
    for nome in VARIAVEIS:
        monkeypatch.delenv(nome, raising=False)

    carregada = config.carregar_config()
    assert carregada.llm_api_key is None
    assert carregada.llm_model is None
    assert carregada.llm_base_url is None
    assert carregada.llm_timeout_seconds is None
    assert carregada.llm_max_retries is None
    assert carregada.llm_max_output_tokens is None
    assert carregada.llm_reasoning_effort is None


def test_carregar_config_converte_valores_do_ambiente(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "chave-de-teste")
    monkeypatch.setenv("LLM_MODEL", "modelo-de-teste")
    monkeypatch.setenv("LLM_BASE_URL", "https://provedor.exemplo/v1")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("LLM_MAX_RETRIES", "3")
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", "4096")
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")

    carregada = config.carregar_config()
    assert carregada.llm_api_key == "chave-de-teste"
    assert carregada.llm_model == "modelo-de-teste"
    assert carregada.llm_base_url == "https://provedor.exemplo/v1"
    assert carregada.llm_timeout_seconds == 30
    assert carregada.llm_max_retries == 3
    assert carregada.llm_max_output_tokens == 4096
    assert carregada.llm_reasoning_effort == "low"
