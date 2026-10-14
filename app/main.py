"""Aplicação FastAPI com rota de disponibilidade."""
from fastapi import FastAPI

from app.routes.health import router as health_router


app = FastAPI(
    title="Quimia Extractor AI",
    description="Núcleo de extração de dados das seções 3, 4 e 10 de FDS.",
    version="0.1.0",
)
app.include_router(health_router)
