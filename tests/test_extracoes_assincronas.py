import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ErroLLM
from app.main import app
from app.routes.extracoes import obter_cliente_llm, obter_registro
from app.services.extracoes_assincronas import RegistroDeExtracoes
from tests.contrato_api import validar_contrato
from tests.pdf_fixtures import FDS_ALCOOL_70, RELATORIO_SEM_SECOES, gerar_pdf_imagem, gerar_pdf_texto
from tests.test_rota_extracoes import AUTORIZADO, TOKEN, FakeLLM, respostas_alcool_70

ESPERA_MAXIMA_SEGUNDOS = 5.0


@pytest.fixture
def cliente_http(monkeypatch):
    monkeypatch.setenv("EXTRATOR_API_TOKEN", TOKEN)
    monkeypatch.delenv("EXTRATOR_TIMEOUT_SECONDS", raising=False)
    fake = FakeLLM(respostas_alcool_70())
    app.dependency_overrides[obter_cliente_llm] = lambda: fake
    registro = RegistroDeExtracoes()
    app.dependency_overrides[obter_registro] = lambda: registro
    with TestClient(app) as cliente:
        cliente.fake = fake
        yield cliente
    app.dependency_overrides.clear()


def enviar(cliente, conteudo: bytes, headers=AUTORIZADO):
    return cliente.post(
        "/extracoes/assincronas",
        headers=headers,
        files={"arquivo": ("fds.pdf", conteudo, "application/pdf")},
    )


def aguardar_fim(cliente, id_extracao: str) -> dict:
    limite = time.monotonic() + ESPERA_MAXIMA_SEGUNDOS
    while time.monotonic() < limite:
        corpo = cliente.get(f"/extracoes/assincronas/{id_extracao}", headers=AUTORIZADO).json()
        if corpo["status"] != "processando":
            return corpo
        time.sleep(0.02)
    raise AssertionError("a extração não terminou a tempo")


def test_envio_devolve_202_com_id_e_a_extracao_termina_com_o_mesmo_json_da_rota_sincrona(cliente_http):
    resposta = enviar(cliente_http, gerar_pdf_texto(FDS_ALCOOL_70))

    assert resposta.status_code == 202, resposta.text
    corpo = resposta.json()
    assert corpo["status"] == "processando"
    assert resposta.headers["location"] == f"/extracoes/assincronas/{corpo['id']}"

    final = aguardar_fim(cliente_http, corpo["id"])
    assert final["status"] == "concluida"
    assert validar_contrato(json.dumps(final["resultado"])) == []
    assert final["resultado"]["status"] == "processado"
    assert final["resultado"]["secoes"]["03"]["compostos"][0]["nome"] == "Etanol"


def test_consulta_durante_a_extracao_devolve_processando(cliente_http):
    cliente_http.fake.atraso = 0.4

    id_extracao = enviar(cliente_http, gerar_pdf_texto(FDS_ALCOOL_70)).json()["id"]

    resposta = cliente_http.get(f"/extracoes/assincronas/{id_extracao}", headers=AUTORIZADO)
    assert resposta.status_code == 200
    assert resposta.json() == {"id": id_extracao, "status": "processando"}
    assert aguardar_fim(cliente_http, id_extracao)["status"] == "concluida"


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer token-errado"}], ids=["sem-token", "token-errado"])
def test_sem_token_valido_envio_e_consulta_devolvem_401(cliente_http, headers):
    assert enviar(cliente_http, gerar_pdf_texto(FDS_ALCOOL_70), headers=headers).status_code == 401
    assert cliente_http.get("/extracoes/assincronas/qualquer", headers=headers).status_code == 401
    assert cliente_http.fake.entradas == {}


def test_id_desconhecido_devolve_404_em_json(cliente_http):
    resposta = cliente_http.get("/extracoes/assincronas/nao-existe", headers=AUTORIZADO)
    assert resposta.status_code == 404
    assert resposta.json() == {"detail": "Extração não encontrada ou expirada."}


def test_arquivo_que_nao_e_pdf_e_recusado_na_hora_sem_criar_extracao(cliente_http):
    resposta = enviar(cliente_http, b"nome;cas\netanol;64-17-5\n")
    assert resposta.status_code == 400
    assert "id" not in resposta.json()


def test_pdf_sem_secoes_da_fds_termina_falhou_com_codigo_400(cliente_http):
    id_extracao = enviar(cliente_http, gerar_pdf_texto(RELATORIO_SEM_SECOES)).json()["id"]

    final = aguardar_fim(cliente_http, id_extracao)

    assert final["status"] == "falhou"
    assert final["codigo"] == 400
    assert final["detail"]
    assert cliente_http.fake.entradas == {}


def test_pdf_somente_imagem_termina_falhou_com_codigo_422(cliente_http):
    id_extracao = enviar(cliente_http, gerar_pdf_imagem()).json()["id"]

    final = aguardar_fim(cliente_http, id_extracao)

    assert (final["status"], final["codigo"]) == ("falhou", 422)


def test_falha_da_ia_termina_falhou_com_codigo_502_sem_resultado(cliente_http):
    cliente_http.fake.erro = ErroLLM("falha simulada")

    id_extracao = enviar(cliente_http, gerar_pdf_texto(FDS_ALCOOL_70)).json()["id"]

    final = aguardar_fim(cliente_http, id_extracao)
    assert (final["status"], final["codigo"]) == ("falhou", 502)
    assert "resultado" not in final


def test_extracao_acima_do_prazo_termina_falhou_com_codigo_504(cliente_http, monkeypatch):
    monkeypatch.setenv("EXTRATOR_TIMEOUT_SECONDS", "0.05")
    cliente_http.fake.atraso = 1.0

    id_extracao = enviar(cliente_http, gerar_pdf_texto(FDS_ALCOOL_70)).json()["id"]

    final = aguardar_fim(cliente_http, id_extracao)
    assert (final["status"], final["codigo"]) == ("falhou", 504)


def test_acima_do_limite_em_andamento_devolve_429_com_retry_after(monkeypatch):
    monkeypatch.setenv("EXTRATOR_API_TOKEN", TOKEN)
    fake = FakeLLM(respostas_alcool_70(), atraso=0.5)
    registro = RegistroDeExtracoes(limite_em_andamento=1)
    app.dependency_overrides[obter_cliente_llm] = lambda: fake
    app.dependency_overrides[obter_registro] = lambda: registro
    try:
        with TestClient(app) as cliente:
            pdf = gerar_pdf_texto(FDS_ALCOOL_70)
            primeira = enviar(cliente, pdf)
            segunda = enviar(cliente, pdf)
            assert primeira.status_code == 202
            assert segunda.status_code == 429
            assert segunda.headers["retry-after"] == "10"
            assert aguardar_fim(cliente, primeira.json()["id"])["status"] == "concluida"
            assert enviar(cliente, pdf).status_code == 202
    finally:
        app.dependency_overrides.clear()


def test_registro_descarta_a_extracao_finalizada_depois_da_validade():
    agora = [0.0]
    registro = RegistroDeExtracoes(validade_segundos=60, relogio=lambda: agora[0])

    async def cenario():
        async def trabalho():
            return {"ok": True}

        extracao = registro.iniciar(trabalho)
        await asyncio.sleep(0.05)
        assert registro.consultar(extracao.id).resultado == {"ok": True}
        agora[0] = 61.0
        assert registro.consultar(extracao.id) is None

    asyncio.run(cenario())


def test_falha_inesperada_do_trabalho_vira_falhou_500_sem_vazar_a_mensagem():
    registro = RegistroDeExtracoes()

    async def cenario():
        async def trabalho():
            raise RuntimeError("segredo interno")

        extracao = registro.iniciar(trabalho)
        await asyncio.sleep(0.05)
        return registro.consultar(extracao.id).como_resposta()

    resposta = asyncio.run(cenario())

    assert resposta["status"] == "falhou"
    assert resposta["codigo"] == 500
    assert "segredo" not in json.dumps(resposta)
