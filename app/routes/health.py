"""Rota pública de disponibilidade usada pelo smoke check da hospedagem."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
