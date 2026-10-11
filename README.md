# Quimia Extractor AI

Serviço Python para extrair dados das seções 3 (composição), 4 (primeiros socorros) e 10 (estabilidade e reatividade) de uma Ficha de Dados de Segurança (FDS). A extração usa saídas estruturadas, evidências vinculadas às páginas de origem e pendências quando a informação não está clara ou não foi informada.

O texto da FDS é tratado como conteúdo não confiável. Instruções que apareçam no documento não são seguidas pelo extrator. Cada informação extraída precisa de uma citação literal presente no texto recebido; evidências que não correspondam à fonte são rejeitadas.

## Estado atual

- O serviço recebe o texto das páginas; não recebe nem processa PDFs.
- O núcleo de extração é implementado em Python e usa a API da OpenAI.
- A aplicação HTTP expõe somente `GET /health` para verificar disponibilidade.
- Ainda não há endpoint HTTP para solicitar extrações, autenticação por token ou integração com banco de dados.
- A saída completa é montada pelo serviço Python a partir das respostas estruturadas de cada seção.

## Requisitos e configuração local

O CI usa Python 3.12. Instale as dependências de desenvolvimento no interpretador Python que você utiliza:

```powershell
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Edite `.env` e informe `OPENAI_API_KEY` e `OPENAI_MODEL`. Os demais valores podem ser mantidos ou ajustados:

| Variável | Finalidade |
|---|---|
| `OPENAI_API_KEY` | Chave usada pelo cliente da OpenAI |
| `OPENAI_MODEL` | Modelo usado nas extrações |
| `LLM_TIMEOUT_SECONDS` | Tempo limite de cada chamada à IA |
| `LLM_MAX_RETRIES` | Tentativas para falhas temporárias |
| `LLM_MAX_OUTPUT_TOKENS` | Limite de tokens da resposta |
| `LLM_REASONING_EFFORT` | Nível de raciocínio solicitado ao modelo |

Para iniciar a aplicação HTTP localmente:

```powershell
uvicorn app.main:app --reload
```

A rota `http://127.0.0.1:8000/health` retorna `{"status":"ok"}`. Ela não executa extrações.

## Contrato do serviço de extração

O serviço recebe as páginas das três seções. Quando uma seção não foi localizada, informe `encontrada: false` e `paginas: []`.

```json
{
  "secoes": {
    "secao_3": {
      "encontrada": true,
      "paginas": [
        {"numero": 2, "texto": "Etanol: concentração entre 5 e 10%."}
      ]
    },
    "secao_4": {
      "encontrada": true,
      "paginas": [
        {"numero": 3, "texto": "Levar para local ventilado."}
      ]
    },
    "secao_10": {
      "encontrada": false,
      "paginas": []
    }
  }
}
```

Cada página pode conter até 30.000 caracteres; o texto total das seções, até 120.000 caracteres. Se uma seção não foi localizada, o serviço cria uma pendência para ela e não chama o modelo para essa seção.

O resultado contém `status`, `mensagem`, `secoes` e `pendencias`. As seções são representadas pelas chaves JSON `03`, `04` e `10`. Os schemas e exemplos de resposta por seção ficam em `app/schemas/` e `app/prompts/`.

## Chamar o serviço pelo código Python

Com `.env` configurado, o núcleo pode ser usado diretamente pelo serviço Python:

```python
import asyncio

from app.clients.llm import LLMClient
from app.schemas.entrada import ExtracaoEntrada
from app.services.extracao_service import ExtracaoService


entrada = ExtracaoEntrada.model_validate({
    "secoes": {
        "secao_3": {
            "encontrada": True,
            "paginas": [
                {"numero": 2, "texto": "Etanol (CAS 64-17-5): 5 a 10%."}
            ],
        },
        "secao_4": {"encontrada": False, "paginas": []},
        "secao_10": {"encontrada": False, "paginas": []},
    }
})


async def main():
    cliente = LLMClient()
    try:
        resultado = await ExtracaoService(cliente).extrair(entrada)
        print(resultado.model_dump_json(indent=2, by_alias=True))
    finally:
        await cliente.fechar()


asyncio.run(main())
```

## Testes e CI

Instale `requirements-dev.txt` para executar os testes:

```powershell
python -m pytest -q
python -m pytest -q --cov=app --cov-report=term-missing --cov-fail-under=80
```

Os testes usam respostas simuladas e não fazem chamadas pagas à OpenAI. Em pull requests, o workflow verifica a instalação e importação da aplicação, executa os testes, exige cobertura mínima de 80% e valida o pacote ZIP da Discloud. A publicação de uma Release executa o deploy e verifica a rota `/health`.
