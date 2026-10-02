# Quimia Extractor AI

Estrutura inicial do serviço de extração de FDS (Ficha de Dados de Segurança) do Quimia, desenvolvido para FastAPI.

Este repositório contém apenas a organização de pastas e arquivos vazios. A API, as chamadas à IA, as dependências e os testes ainda não foram implementados.

## Responsabilidade do serviço

O backend principal valida o upload e as permissões, lê o PDF com PDFBox e envia um JSON contendo os identificadores do documento e o texto das seções por página.

O extractor interpreta as seções 3 (composição), 4 (primeiros socorros) e 10 (estabilidade e reatividade), valida o resultado e devolve dados estruturados, evidências e pendências.

O backend principal associa substâncias e classes químicas aos IDs do banco, apresenta os dados para aprovação da empresa e realiza a persistência. O extractor não acessa o banco e não executa o match de produtos.

## Estrutura

```text
app/
├── __init__.py
├── main.py
├── routes/
│   ├── extracao.py
│   └── health.py
├── schemas/
│   ├── entrada.py
│   ├── saida.py
│   ├── composto.py
│   ├── primeiro_socorro.py
│   ├── incompatibilidade.py
│   └── evidencia.py
├── services/
│   └── extracao_service.py
├── extractors/
│   ├── composicao.py
│   ├── primeiros_socorros.py
│   └── incompatibilidades.py
├── prompts/
│   ├── base.py
│   ├── composicao.py
│   ├── primeiros_socorros.py
│   └── incompatibilidades.py
├── clients/
│   └── llm.py
├── validators/
│   ├── documento.py
│   └── extracao.py
└── core/
    ├── config.py
    ├── security.py
    ├── exceptions.py
    └── logging.py

tests/
├── fixtures/
├── test_contrato.py
├── test_validacao.py
└── test_extracao.py

.env.example
.gitignore
pyproject.toml
README.md
```

## Papel de cada pasta

| Pasta ou arquivo | Responsabilidade prevista |
| --- | --- |
| `app/main.py` | Inicializar a aplicação FastAPI e registrar as rotas e o tratamento de erros. |
| `app/routes/` | Receber requisições HTTP e devolver respostas. Rotas previstas: `POST /extracoes/fds` e `GET /health`. |
| `app/schemas/` | Definir os contratos de entrada, saída e os modelos dos dados extraídos, futuramente com Pydantic. |
| `app/services/` | Coordenar os extratores, as validações e a montagem da resposta. |
| `app/extractors/` | Implementar a extração específica de cada seção, utilizando o cliente de IA e os prompts. |
| `app/prompts/` | Centralizar as instruções comuns e específicas enviadas à IA. |
| `app/clients/` | Encapsular a comunicação com o provedor de IA, incluindo limites de tempo e falhas. |
| `app/validators/` | Verificar o conteúdo recebido e a consistência dos dados extraídos, registrando pendências. |
| `app/core/` | Centralizar configuração, autenticação entre serviços, exceções e logs. |
| `tests/` | Verificar contratos, validações e comportamento da extração. Os arquivos estão vazios. |
| `tests/fixtures/` | Armazenar exemplos de entrada e resultados esperados, sem credenciais ou dados sensíveis. |
| `.env.example` | Documentar as variáveis de ambiente necessárias quando a implementação for definida. |
| `pyproject.toml` | Declarar dependências e configurações do projeto quando a implementação começar. |

## Schemas e alinhamento com o banco

O banco de referência está em [Quimia-br/quimia-bd](https://github.com/Quimia-br/quimia-bd).

- `entrada.py`: identificadores da FDS e do produto, revisão do documento e textos das seções por página.
- `saida.py`: resultado da extração, status, mensagem de revisão e lista de pendências.
- `composto.py`: nome original extraído, `cas_numero`, `concentracao_min`, `concentracao_max` e `unidade_concentracao`, alinhados a `fds_composto` e ao dicionário de substâncias.
- `primeiro_socorro.py`: `rota_exposicao`, `descricao`, `sintomas`, `tratamento_especial` e `atencao_medica_imediata`, alinhados a `fds_primeiro_socorro`. As rotas aceitas no banco são `inalacao`, `pele`, `olhos` e `ingestao`. Orientações gerais e notas originais também devem ser preservadas na resposta para o backend.
- `incompatibilidade.py`: `substancia_reagente`, `descricao_risco` e `severidade`, alinhados a `fds_incompatibilidade`. Os IDs de substância e classe química são resolvidos pelo backend.
- `evidencia.py`: página, seção e trecho original que sustentam cada informação extraída.

O contrato final ainda será definido. Na função SQL local `fn_processar_fds_raw_json`, a composição é lida em `secoes.03.compostos`, com os campos `nome` e `cas_numero`. Essa função também trata a seção 13, fora do escopo inicial deste extractor; ainda não materializa a seção 4 nem resolve os IDs das incompatibilidades. A integração deve respeitar essas diferenças e evitar perda de dados preexistentes ao reprocessar uma FDS.

## Fluxo previsto

```text
Backend envia JSON
    -> routes/extracao.py
    -> services/extracao_service.py
    -> validators/documento.py
    -> extractors + prompts + clients/llm.py
    -> validators/extracao.py
    -> schemas/saida.py
    -> Backend recebe o resultado
```

## Regras de extração

- Extrair apenas informações sustentadas pelo documento; não inventar CAS, concentração, risco, severidade ou instruções de primeiros socorros.
- Tratar o texto da FDS como conteúdo a analisar, nunca como instruções para o serviço.
- Preservar página e trecho original como evidência.
- Diferenciar seção não localizada, informação ausente, termo ambíguo e declaração explícita de ausência de incompatibilidades.
- Devolver dados válidos mesmo quando existirem pendências, com a mensagem: “Informações ausentes, verifique o documento anexado”.
- Se a informação faltar na própria ficha, a empresa deve anexar uma ficha corrigida, que será processada novamente.
- Termos desconhecidos no dicionário são tratados pelo backend; sugestões da IA não criam vínculos nem sinônimos automaticamente.
- A seção 4 alimenta o “Saiba mais” de cada produto e não participa do match.
- Não interpretar uma lista vazia de incompatibilidades como comprovação de que uma mistura é segura.
- Devolver os identificadores da revisão recebida para permitir que o backend evite salvar respostas de documentos desatualizados.

## Estado atual

Este esqueleto ainda não pode ser iniciado como API. Não há provedor de IA escolhido, dependências declaradas, endpoints implementados ou testes executáveis. O arquivo `.env` existente e o `.gitignore` foram preservados.
