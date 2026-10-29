# Quimia Extractor AI

Serviço Python para extrair dados das seções 3 (composição), 4 (primeiros socorros) e 10 (estabilidade e reatividade) de uma Ficha de Dados de Segurança (FDS). A extração usa saídas estruturadas, evidências vinculadas às páginas de origem e pendências quando a informação não está clara ou não foi informada.

O texto da FDS é tratado como conteúdo não confiável. Instruções que apareçam no documento não são seguidas pelo extrator. Cada informação extraída precisa de uma citação literal presente no texto recebido; evidências que não correspondam à fonte são rejeitadas.

## Estado atual

- O serviço recebe o texto das páginas; não recebe nem processa PDFs.
- O núcleo de extração é implementado em Python e usa a API da OpenAI.
- A aplicação HTTP expõe `GET /health`, `POST /api/extracoes` e a interface local `GET /teste`.
- A extração HTTP e a interface aceitam apenas conexões locais por padrão. Ainda não há autenticação nem integração com banco de dados.
- A saída completa é montada pelo serviço Python a partir das respostas estruturadas de cada seção.

## Requisitos e configuração local

O CI usa Python 3.12. Instale as dependências de desenvolvimento no interpretador Python que você utiliza:

```powershell
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

No Windows, se o comando `python` não apontar para uma instalação funcional, use um ambiente virtual com o Python disponível:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Se o `.env` já estiver configurado, preserve-o em vez de repetir o `Copy-Item`.

Edite `.env` e informe `OPENAI_API_KEY` e `OPENAI_MODEL`. Os demais valores podem ser mantidos ou ajustados:

| Variável | Finalidade |
|---|---|
| `LLM_API_KEY` | Chave do provedor de IA |
| `LLM_MODEL` | Modelo usado nas extrações |
| `LLM_BASE_URL` | URL base OpenAI-compatível do provedor; sem ela, usa a API da OpenAI |
| `LLM_TIMEOUT_SECONDS` | Tempo limite de cada chamada à IA |
| `LLM_MAX_RETRIES` | Tentativas para falhas temporárias |
| `LLM_MAX_OUTPUT_TOKENS` | Limite de tokens da resposta |
| `LLM_REASONING_EFFORT` | Nível de raciocínio solicitado ao modelo (enviado só quando definido) |
| `EXTRATOR_API_TOKEN` | Token exigido em `POST /extracoes`; sem ele, a rota responde 503 |
| `EXTRATOR_TIMEOUT_SECONDS` | Prazo total de uma extração (padrão 55 s; a quimia-api espera até 60 s) |

Exemplo com a Command Code (o Provider API exige o plano Pro ou superior):

```dotenv
LLM_API_KEY=<chave criada no Command Code Studio>
LLM_MODEL=deepseek/deepseek-v4-1-flash
LLM_BASE_URL=https://api.commandcode.ai/provider/v1
```

Para conferir os IDs de modelo disponíveis:

```powershell
Invoke-RestMethod -Uri https://api.commandcode.ai/provider/v1/models -Headers @{ Authorization = "Bearer $env:LLM_API_KEY" }
```

Gere o token com um valor aleatório longo, por exemplo:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

O mesmo valor deve ser configurado na quimia-api como `QUIMIA_EXTRATOR_TOKEN`, e a URL pública do serviço como `QUIMIA_EXTRATOR_URL`.

Para iniciar a aplicação HTTP localmente:

```powershell
uvicorn app.main:app --reload
```

A rota `http://127.0.0.1:8000/health` retorna `{"status":"ok"}`. Abra `http://127.0.0.1:8000/teste` para editar um exemplo de JSON, executar a extração real, inspecionar erros e copiar a resposta formatada. A interface faz `POST /api/extracoes`, a mesma rota que poderá ser usada pelo backend. Se alguma seção estiver marcada como `encontrada: true`, o serviço chama a API da OpenAI e requer credenciais válidas.

As rotas de teste e extração só aceitam clientes de `127.0.0.1` ou `::1` por padrão. Para liberar clientes remotos, configure `EXTRACTION_ALLOW_REMOTE=true` no ambiente **somente depois de implantar autenticação e controles de uso**; a variável não implementa esses controles.

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

`POST /api/extracoes` recebe exatamente `ExtracaoEntrada` e devolve `ExtracaoSaida` com aliases JSON `03`, `04` e `10`. Não há envelope adicional em caso de sucesso. Exemplo da estrutura de resposta, quando todas as seções estão ausentes:

```json
{
  "status": "processado_com_pendencias",
  "mensagem": "Informações ausentes, verifique o documento anexado",
  "secoes": {
    "03": {"encontrada": false, "compostos": []},
    "04": {"encontrada": false, "primeiros_socorros": [], "orientacoes_gerais": [], "notas_ao_medico": []},
    "10": {"encontrada": false, "situacao": "secao_nao_localizada", "incompatibilidades": [], "evidencias": []}
  },
  "pendencias": [
    {"secao": "03", "campo": "secao", "motivo": "secao_nao_localizada", "descricao": "A seção 03 não foi localizada na ficha.", "evidencias": []},
    {"secao": "04", "campo": "secao", "motivo": "secao_nao_localizada", "descricao": "A seção 04 não foi localizada na ficha.", "evidencias": []},
    {"secao": "10", "campo": "secao", "motivo": "secao_nao_localizada", "descricao": "A seção 10 não foi localizada na ficha.", "evidencias": []}
  ]
}
```

Falhas usam `{"erro":{"tipo":"...","mensagem":"...","detalhes":[]}}`. JSON malformado e entrada fora do schema retornam HTTP 422 com tipos `json_invalido` e `validacao`; texto acima dos limites também retorna `validacao`. Falta de configuração ou de créditos da API retorna 503 com a causa explícita; outras falhas do provedor ou da validação da extração retornam 502, e falha inesperada retorna 500. Em `detalhes`, cada item identifica `campo` e `mensagem`. A interface mostra esses erros e só habilita a cópia de respostas bem sucedidas.

Antes da integração, alinhar com o backend e o banco: autenticação e política de uso; se a entrada terá identificador da FDS ou metadados adicionais; como persistir campos nulos, evidências e pendências; e se erros devem usar esse envelope HTTP ou o padrão da API principal. A rota não grava dados.

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

Os testes usam respostas simuladas e não fazem chamadas pagas ao provedor de IA. Os PDFs de teste (FDS em texto e PDF só com imagem) são gerados em memória por `tests/pdf_fixtures.py`. Em pull requests, o workflow verifica a instalação e importação da aplicação, executa os testes, exige cobertura mínima de 80% e valida o pacote ZIP da Discloud. A publicação de uma Release executa o deploy e verifica a rota `/health`.
