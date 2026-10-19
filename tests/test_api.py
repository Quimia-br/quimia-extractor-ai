from fastapi.testclient import TestClient

from app.main import app


def test_health_disponivel_e_rotas_publicadas():
    with TestClient(app) as cliente:
        resposta = cliente.get("/health")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}
    assert set(app.openapi()["paths"]) == {"/health", "/extracoes"}
