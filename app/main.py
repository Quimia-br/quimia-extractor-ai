"""Aplicação FastAPI com rotas de disponibilidade e de extração."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routes.extracoes import router as extracoes_router
from app.routes.health import router as health_router


@asynccontextmanager
async def ciclo_de_vida(aplicacao: FastAPI):
    yield
    cliente = getattr(aplicacao.state, "cliente_llm", None)
    if cliente is not None:
        await cliente.fechar()


app = FastAPI(
    title="Quimia Extractor AI",
    description="Extração de dados das seções 3, 4 e 10 de FDS.",
    version="0.1.0",
    lifespan=ciclo_de_vida,
)
app.include_router(health_router)
app.include_router(extracoes_router)
