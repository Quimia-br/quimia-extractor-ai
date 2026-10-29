"""Aplicação FastAPI para extração e testes locais."""
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import ConfiguracaoLLMInvalida
from app.routes.extracao import router as extracao_router
from app.routes.health import router as health_router


app = FastAPI(
    title="Quimia Extractor AI",
    description="Núcleo de extração de dados das seções 3, 4 e 10 de FDS.",
    version="0.1.0",
)
app.include_router(health_router)
app.include_router(extracao_router)


@app.exception_handler(HTTPException)
async def tratar_erro_http(request: Request, erro: HTTPException) -> JSONResponse:
    if erro.status_code == 403:
        return JSONResponse(status_code=403, content={"erro": {"tipo": "acesso", "mensagem": str(erro.detail), "detalhes": []}})
    return JSONResponse(status_code=erro.status_code, content={"detail": erro.detail})


@app.exception_handler(ConfiguracaoLLMInvalida)
async def tratar_configuracao_llm(request: Request, erro: ConfiguracaoLLMInvalida) -> JSONResponse:
    return JSONResponse(status_code=503, content={"erro": {"tipo": "configuracao", "mensagem": str(erro), "detalhes": []}})


@app.exception_handler(RequestValidationError)
async def tratar_entrada_invalida(request: Request, erro: RequestValidationError) -> JSONResponse:
    """Distingue JSON malformado de dados fora do contrato de entrada."""
    detalhes = erro.errors()
    tipo = "json_invalido" if any(item["type"] == "json_invalid" for item in detalhes) else "validacao"
    return JSONResponse(
        status_code=422,
        content={
            "erro": {
                "tipo": tipo,
                "mensagem": "JSON inválido." if tipo == "json_invalido" else "Entrada fora do contrato.",
                "detalhes": [
                    {"campo": ".".join(str(parte) for parte in item["loc"]), "mensagem": item["msg"]}
                    for item in detalhes
                ],
            }
        },
    )
