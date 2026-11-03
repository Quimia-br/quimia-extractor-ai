# Quimia Extractor AI

Serviço Python (FastAPI) que extrai dados das seções 3 (composição), 4 (primeiros socorros) e 10 (estabilidade e reatividade) de uma Ficha de Dados de Segurança (FDS). A extração usa saídas estruturadas, evidências vinculadas às páginas de origem e pendências quando a informação não está clara ou não foi informada.

O texto da FDS é tratado como conteúdo não confiável. Instruções que apareçam no documento não são seguidas pelo extrator. Cada informação extraída precisa de uma citação literal presente no texto recebido (a comparação ignora espaços, porque a extração de texto do PDF costuma abrir palavras); evidências que não correspondam à fonte são rejeitadas.

A quimia-api consome este serviço (`QUIMIA_EXTRATOR_URL` e `QUIMIA_EXTRATOR_TOKEN`). A saída completa é montada pelo serviço a partir das respostas estruturadas de cada seção, e ele não grava dados.

## Requisitos

- Python 3.12 (a versão usada pelo CI)
- Uma chave de um provedor de IA compatível com a API da OpenAI

## Comandos

```powershell
python -m pip install -r requirements-dev.txt         # dependências de desenvolvimento
Copy-Item .env.example .env                           # primeira vez; se o .env já existe, preserve-o
python -m uvicorn app.main:app --reload               # sobe em http://127.0.0.1:8000
python -m pytest -q                                   # testes
python -m pytest -q --cov=app --cov-report=term-missing --cov-fail-under=80
```

No Windows, se o comando `python` não apontar para uma instalação funcional, use um ambiente virtual:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## Configuração

Edite `.env` e informe `LLM_API_KEY` e `LLM_MODEL`. Os demais valores podem ser mantidos ou ajustados:

| Variável | Finalidade |
|---|---|
| `LLM_API_KEY` | Chave do provedor de IA |
| `LLM_MODEL` | Modelo usado nas extrações |
| `LLM_BASE_URL` | URL base OpenAI-compatível do provedor; sem ela, usa a API da OpenAI |
| `LLM_TIMEOUT_SECONDS` | Tempo limite de cada chamada à IA; deve caber em `EXTRATOR_TIMEOUT_SECONDS` |
| `LLM_MAX_RETRIES` | Tentativas para falhas temporárias |
| `LLM_MAX_OUTPUT_TOKENS` | Limite de tokens da resposta |
| `LLM_REASONING_EFFORT` | Nível de raciocínio solicitado ao modelo (enviado só quando definido) |
| `EXTRATOR_API_TOKEN` | Token exigido nas rotas de PDF; sem ele, elas respondem 503 |
| `EXTRATOR_TIMEOUT_SECONDS` | Prazo total de uma extração (padrão 25 s); acima dele a rota responde 504 em JSON |
| `EXTRACTION_ALLOW_REMOTE` | Libera `/teste` e `/api/extracoes` para clientes remotos (padrão `false`) |

Exemplo com a Command Code (o Provider API exige o plano Pro ou superior):

```dotenv
LLM_API_KEY=<chave criada no Command Code Studio>
LLM_MODEL=gpt-6-luna
LLM_BASE_URL=https://api.commandcode.ai/provider/v1
LLM_REASONING_EFFORT=low
```

Com `gpt-6-luna` e esforço `low`, a mediana das FDS de teste foi de 10 s. Sem o `low` o modelo passa de 30 s por FDS, e `minimal` e `none` são recusados pelo provedor. O modelo anterior (`xiaomi/mimo-v2.6-flash`) levava de 35 a 150 s.

Para conferir os IDs de modelo disponíveis:

```powershell
Invoke-RestMethod -Uri https://api.commandcode.ai/provider/v1/models -Headers @{ Authorization = "Bearer $env:LLM_API_KEY" }
```

Gere o token com um valor aleatório longo, por exemplo:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

O mesmo valor deve ser configurado na quimia-api como `QUIMIA_EXTRATOR_TOKEN`, e a URL pública do serviço como `QUIMIA_EXTRATOR_URL`.

## Rotas e documentação da API

Com o serviço no ar, a documentação interativa fica em `/docs` e o documento OpenAPI em `/openapi.json`.

| Rota | Acesso | Finalidade |
|---|---|---|
| `GET /health` | público | `{"status":"ok"}`, usado no smoke check do deploy |
| `POST /extracoes` | token | recebe o PDF (campo `arquivo`) e devolve a extração na mesma resposta |
| `POST /extracoes/assincronas` | token | mesma entrada; devolve `202` com um `id` |
| `GET /extracoes/assincronas/{id}` | token | estado da extração iniciada acima |
| `POST /api/extracoes` | só local | recebe o texto das páginas (`ExtracaoEntrada`) |
| `GET /teste` | só local | interface para editar um exemplo de JSON, executar a extração e inspecionar erros |

As rotas `/teste` e `/api/extracoes` só aceitam clientes de `127.0.0.1` ou `::1` por padrão. Para liberar clientes remotos, configure `EXTRACTION_ALLOW_REMOTE=true` **somente depois de implantar autenticação e controles de uso nessa rota**; a variável não implementa esses controles. Se alguma seção estiver marcada como `encontrada: true`, o serviço chama o provedor de IA e requer credenciais válidas.

### Extração assíncrona

O host da Discloud corta qualquer resposta após cerca de 30 s e entrega uma página HTML com status 200, e uma extração real pode passar disso. Por isso `POST /extracoes/assincronas` responde na hora e o chamador consulta o resultado:

- `POST /extracoes/assincronas` devolve `202` com `{"id": "...", "status": "processando"}` e o cabeçalho `Location`. Erros do arquivo (`400`, `413`) saem aqui, antes de criar a extração.
- `GET /extracoes/assincronas/{id}` informa `processando`, `concluida` (com o `resultado`, igual à resposta de `POST /extracoes`) ou `falhou` (com `codigo` e `detail`, os mesmos da rota síncrona). Id desconhecido ou vencido é `404`.
- Os registros ficam em memória por 15 min, com no máximo 6 em andamento (acima disso, `429` com `Retry-After`). Um reinício da aplicação perde as extrações em andamento, e o chamador refaz o envio.

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

As rotas de PDF respondem `{"detail": "..."}`: `400` para arquivo que não é PDF ou sem as seções 3, 4 e 10 localizadas, `413` acima de 10 MB, `422` para PDF sem texto legível (por exemplo, só imagem), `502` quando a IA não devolve uma extração válida e `504` quando a extração passa do prazo.

### Rede de proteção da extração

- Cada seção rejeitada por formato ou por citação inexistente ganha mais uma tentativa; falta de crédito não é repetida.
- A situação da seção 10 acompanha o que a IA devolveu: itens só existem em `identificadas`, e `ausencia_declarada` sem a citação da declaração vira `nao_especificadas`.
- `atencao_medica_imediata: false` só vale quando o texto nega a urgência por escrito; sem isso o valor volta a `null`.
- Uma concentração que difere do número presente na citação é omitida, com pendência `dados_contraditorios`.

Antes da integração, alinhar com o backend e o banco: autenticação e política de uso; se a entrada terá identificador da FDS ou metadados adicionais; como persistir campos nulos, evidências e pendências; e se erros devem usar esse envelope HTTP ou o padrão da API principal.

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

## CI, checks e deploy

O GitHub Actions executa `.github/workflows/ci.yml` em PRs para `main`, pushes em `main` e Releases publicadas. O workflow também pode ser iniciado manualmente para validar os gates sem fazer deploy. Cada check publica um resumo com seu objetivo, critério de aprovação, resultado e onde investigar uma falha; o check `CI summary` consolida a execução. É o mesmo workflow do quimia-agent.

- **Build** — instala as dependências e verifica que a aplicação importa.
- **Unit tests** — executa o `pytest`. Os testes usam respostas simuladas e não fazem chamadas pagas ao provedor de IA; os PDFs de teste (FDS em texto e PDF só com imagem) são gerados em memória por `tests/pdf_fixtures.py`.
- **Coverage gate** — exige cobertura de pelo menos 80% em `app/`.
- **Discloud artifact** — gera o ZIP do deploy com `scripts/package_discloud_release.py`.
- **Deploy to Discloud** — só roda ao publicar uma Release, usa o Environment `discloud`, envia o ZIP e verifica que `/health` responde HTTP 200.
- **PR title** — `.github/workflows/pr-title.yml` exige título Conventional Commits (`tipo(escopo): descrição`).

O deploy não é um check exigido para PR, pois só roda em Release publicada. A configuração do app na Discloud está em `discloud.config`.

### Variáveis na Discloud

Defina no app `quimia-extractor` (além de `LLM_API_KEY` e `LLM_BASE_URL`):

```dotenv
LLM_MODEL=gpt-6-luna
LLM_REASONING_EFFORT=low
EXTRATOR_API_TOKEN=<o mesmo valor de QUIMIA_EXTRATOR_TOKEN na quimia-api>
EXTRATOR_TIMEOUT_SECONDS=25
```

A ordem de publicação quando a quimia-api usa as rotas assíncronas é este serviço primeiro, depois a quimia-api e depois o portal.
