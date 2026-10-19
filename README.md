# Quimia Extractor AI

Serviço Python para extrair dados das seções 3 (composição), 4 (primeiros socorros) e 10 (estabilidade e reatividade) de uma Ficha de Dados de Segurança (FDS). A extração usa saídas estruturadas, evidências vinculadas às páginas de origem e pendências quando a informação não está clara ou não foi informada.

O texto da FDS é tratado como conteúdo não confiável. Instruções que apareçam no documento não são seguidas pelo extrator. Cada informação extraída precisa de uma citação literal presente no texto recebido; evidências que não correspondam à fonte são rejeitadas.

## Estado atual

- `POST /extracoes` recebe o PDF da FDS, extrai o texto, localiza as seções 3, 4 e 10 e devolve o `ExtracaoSaida` saneado.
- `GET /health` verifica a disponibilidade, sem autenticação.
- O núcleo de extração é implementado em Python e usa a API da OpenAI.
- O serviço não grava nada em banco nem guarda o PDF após responder; quem persiste o resultado é a quimia-api.

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
| `EXTRATOR_API_TOKEN` | Token exigido em `POST /extracoes`; sem ele, a rota responde 503 |
| `EXTRATOR_TIMEOUT_SECONDS` | Prazo total de uma extração (padrão 55 s; a quimia-api espera até 60 s) |

Gere o token com um valor aleatório longo, por exemplo:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

O mesmo valor deve ser configurado na quimia-api como `QUIMIA_EXTRATOR_TOKEN`, e a URL pública do serviço como `QUIMIA_EXTRATOR_URL`.

Para iniciar a aplicação HTTP localmente:

```powershell
uvicorn app.main:app --reload
```

A rota `http://127.0.0.1:8000/health` retorna `{"status":"ok"}`.

## Rota `POST /extracoes`

```
POST /extracoes
Authorization: Bearer <EXTRATOR_API_TOKEN>
Content-Type: multipart/form-data
  arquivo: PDF da FDS (até 10 MB)
Accept: application/json
```

```powershell
curl.exe -X POST http://127.0.0.1:8000/extracoes -H "Authorization: Bearer $env:EXTRATOR_API_TOKEN" -F "arquivo=@fds.pdf;type=application/pdf"
```

Fluxo: autenticação (comparação em tempo constante) → limite de tamanho, verificado pelo `Content-Length` e durante a leitura → assinatura `%PDF-` → texto página a página → localização das seções 3, 4 e 10 pelos títulos da ABNT NBR 14725 → extração pela IA → sanitização → 200 com o `ExtracaoSaida`.

| Status | Quando |
|---|---|
| 200 | Extração concluída; corpo é o `ExtracaoSaida` saneado |
| 400 | Arquivo não é PDF, PDF corrompido, campo `arquivo` ausente ou documento sem nenhuma das seções 3, 4 ou 10 |
| 401 | Token ausente ou errado |
| 413 | Arquivo acima de 10 MB |
| 422 | PDF sem texto legível (ex.: escaneado) ou protegido por senha; seções acima dos limites de texto |
| 502 | A IA falhou ou devolveu uma extração inválida |
| 503 | `EXTRATOR_API_TOKEN` ou credenciais da IA não configurados |
| 504 | A extração excedeu `EXTRATOR_TIMEOUT_SECONDS` |

O corpo dos erros é `{"detail": "..."}` e não é repassado ao usuário pela quimia-api.

### Sanitização da resposta 200

A quimia-api grava o JSON em `fds.raw_json` (jsonb) e um trigger materializa as tabelas. Antes de responder, `app/validators/saida_http.py`:

- troca o caractere NUL por espaço em qualquer texto;
- corta `compostos[].nome` e `incompatibilidades[].substancia_reagente` em 255 caracteres;
- anula `cas_numero` acima de 20 caracteres (cortar geraria um CAS inexistente);
- anula concentrações fora de 0 a 999.99 (NUMERIC(5,2)), NaN ou Infinity, e a faixa inteira quando min > max;
- anula `severidade` e `tipo_residuo` fora das listas.

Cada valor anulado gera uma pendência e a resposta passa a `processado_com_pendencias`. O teste `tests/contrato_api.py` reproduz as regras combinadas com a API e valida a resposta do caminho feliz.

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

Os testes usam respostas simuladas e não fazem chamadas pagas à OpenAI. Os PDFs de teste (FDS em texto e PDF só com imagem) são gerados em memória por `tests/pdf_fixtures.py`. Em pull requests, o workflow verifica a instalação e importação da aplicação, executa os testes, exige cobertura mínima de 80% e valida o pacote ZIP da Discloud. A publicação de uma Release executa o deploy e verifica a rota `/health`.
