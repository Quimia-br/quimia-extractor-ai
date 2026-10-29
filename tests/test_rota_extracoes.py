import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ErroLLM
from app.main import app
from app.routes.extracoes import LIMITE_ARQUIVO_BYTES, obter_cliente_llm
from app.schemas.respostas_llm import (
    RespostaComposicaoLLM,
    RespostaIncompatibilidadesLLM,
    RespostaPrimeirosSocorrosLLM,
)
from tests.contrato_api import validar_contrato
from tests.pdf_fixtures import (
    FDS_ALCOOL_70,
    RELATORIO_SEM_SECOES,
    gerar_pdf_imagem,
    gerar_pdf_texto,
)

TOKEN = "token-de-teste-extrator"
AUTORIZADO = {"Authorization": f"Bearer {TOKEN}"}


def respostas_alcool_70():
    return {
        RespostaComposicaoLLM: RespostaComposicaoLLM.model_validate(
            {
                "compostos": [
                    {
                        "nome": "Etanol",
                        "cas_numero": "64-17-5",
                        "concentracao_min": 65,
                        "concentracao_max": 70,
                        "unidade_concentracao": "%",
                        "evidencias": [
                            {"secao": "03", "pagina": 1, "texto_evidencia": "Etanol CAS 64-17-5 Concentração: 65 - 70%"}
                        ],
                    },
                    {
                        "nome": "Água",
                        "cas_numero": "7732-18-5",
                        "concentracao_min": 30,
                        "concentracao_max": 35,
                        "unidade_concentracao": "%",
                        "evidencias": [
                            {"secao": "03", "pagina": 2, "texto_evidencia": "Água CAS 7732-18-5 Concentração: 30 - 35%"}
                        ],
                    },
                ],
                "pendencias": [],
            }
        ),
        RespostaPrimeirosSocorrosLLM: RespostaPrimeirosSocorrosLLM.model_validate(
            {
                "primeiros_socorros": [
                    {
                        "rota_exposicao": "inalacao",
                        "descricao": "Remova a vítima para local ventilado.",
                        "sintomas": None,
                        "tratamento_especial": None,
                        "atencao_medica_imediata": None,
                        "evidencias": [
                            {"secao": "04", "pagina": 2, "texto_evidencia": "Inalação: Remova a vítima para local ventilado."}
                        ],
                    }
                ],
                "orientacoes_gerais": [],
                "notas_ao_medico": [],
                "pendencias": [],
            }
        ),
        RespostaIncompatibilidadesLLM: RespostaIncompatibilidadesLLM.model_validate(
            {
                "situacao": "identificadas",
                "incompatibilidades": [
                    {
                        "substancia_reagente": "Agentes oxidantes fortes",
                        "cas_numero": None,
                        "descricao_risco": None,
                        "severidade": None,
                        "evidencias": [
                            {
                                "secao": "10",
                                "pagina": 3,
                                "texto_evidencia": "Materiais incompatíveis: Agentes oxidantes fortes, ácidos e metais alcalinos.",
                            }
                        ],
                    }
                ],
                "evidencias": [],
                "pendencias": [],
            }
        ),
    }


class FakeLLM:
    def __init__(self, respostas=None, erro=None, atraso=0.0):
        self.respostas = respostas or {}
        self.erro = erro
        self.atraso = atraso
        self.entradas = {}

    async def responder_estruturado(self, *, modelo, instrucoes, entrada):
        self.entradas[modelo] = json.loads(entrada)
        if self.atraso:
            await asyncio.sleep(self.atraso)
        if self.erro:
            raise self.erro
        return self.respostas[modelo]


@pytest.fixture
def cliente_http(monkeypatch):
    monkeypatch.setenv("EXTRATOR_API_TOKEN", TOKEN)
    monkeypatch.delenv("EXTRATOR_TIMEOUT_SECONDS", raising=False)
    fake = FakeLLM(respostas_alcool_70())
    app.dependency_overrides[obter_cliente_llm] = lambda: fake
    with TestClient(app) as cliente:
        cliente.fake = fake
        yield cliente
    app.dependency_overrides.clear()


def enviar(cliente, conteudo: bytes, headers=AUTORIZADO, nome="fds.pdf"):
    return cliente.post(
        "/extracoes",
        headers=headers,
        files={"arquivo": (nome, conteudo, "application/pdf")},
    )


def test_fds_real_devolve_200_com_compostos_e_contrato_valido(cliente_http):
    resposta = enviar(cliente_http, gerar_pdf_texto(FDS_ALCOOL_70))

    assert resposta.status_code == 200, resposta.text
    assert validar_contrato(resposta.text) == []
    corpo = resposta.json()
    assert corpo["status"] == "processado"
    etanol, agua = corpo["secoes"]["03"]["compostos"]
    assert etanol["nome"] == "Etanol"
    assert etanol["cas_numero"] == "64-17-5"
    assert (etanol["concentracao_min"], etanol["concentracao_max"]) == (65, 70)
    assert (agua["cas_numero"], agua["concentracao_min"], agua["concentracao_max"]) == ("7732-18-5", 30, 35)
    assert corpo["secoes"]["10"]["incompatibilidades"][0]["substancia_reagente"] == "Agentes oxidantes fortes"


def test_cada_secao_recebe_somente_o_proprio_texto(cliente_http):
    enviar(cliente_http, gerar_pdf_texto(FDS_ALCOOL_70))

    composicao = cliente_http.fake.entradas[RespostaComposicaoLLM]
    assert [pagina["pagina"] for pagina in composicao] == [1, 2]
    texto_03 = " ".join(pagina["texto"] for pagina in composicao)
    assert "Etanol CAS 64-17-5" in texto_03 and "Água CAS 7732-18-5" in texto_03
    assert "Remova a vítima" not in texto_03 and "Líquidos inflamáveis" not in texto_03

    texto_10 = cliente_http.fake.entradas[RespostaIncompatibilidadesLLM][0]["texto"]
    assert "Agentes oxidantes fortes" in texto_10
    assert "Toxicidade aguda" not in texto_10


def test_health_continua_sem_autenticacao(cliente_http):
    assert cliente_http.get("/health").status_code == 200


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer token-errado"}, {"Authorization": TOKEN}],
    ids=["sem-token", "token-errado", "sem-bearer"],
)
def test_token_ausente_ou_errado_devolve_401(cliente_http, headers):
    resposta = enviar(cliente_http, gerar_pdf_texto(FDS_ALCOOL_70), headers=headers)
    assert resposta.status_code == 401
    assert cliente_http.fake.entradas == {}


def test_arquivo_que_nao_e_pdf_devolve_400(cliente_http):
    resposta = enviar(cliente_http, b"nome;cas\netanol;64-17-5\n", nome="fds.csv")
    assert resposta.status_code == 400


def test_pdf_corrompido_devolve_400(cliente_http):
    assert enviar(cliente_http, b"%PDF-1.4\nlixo sem estrutura").status_code == 400


def test_pdf_sem_secoes_da_fds_devolve_400(cliente_http):
    resposta = enviar(cliente_http, gerar_pdf_texto(RELATORIO_SEM_SECOES))
    assert resposta.status_code == 400
    assert cliente_http.fake.entradas == {}


def test_requisicao_sem_campo_arquivo_devolve_400(cliente_http):
    resposta = cliente_http.post(
        "/extracoes", headers=AUTORIZADO, files={"outro": ("fds.pdf", b"%PDF-1.4", "application/pdf")}
    )
    assert resposta.status_code == 400


def test_arquivo_acima_de_10_mb_devolve_413(cliente_http):
    conteudo = b"%PDF-1.4\n" + b"0" * LIMITE_ARQUIVO_BYTES
    assert enviar(cliente_http, conteudo).status_code == 413


def test_corpo_muito_maior_e_recusado_pelo_content_length(cliente_http):
    conteudo = b"%PDF-1.4\n" + b"0" * (LIMITE_ARQUIVO_BYTES * 2)
    assert enviar(cliente_http, conteudo).status_code == 413


def test_corpo_sem_content_length_e_interrompido_ao_passar_do_limite(cliente_http):
    def partes():
        for _ in range(12):
            yield b"0" * (1024 * 1024)

    resposta = cliente_http.post(
        "/extracoes",
        headers={**AUTORIZADO, "Content-Type": "multipart/form-data; boundary=xyz"},
        content=partes(),
    )
    assert resposta.status_code == 413


def test_pdf_somente_imagem_devolve_422(cliente_http):
    resposta = enviar(cliente_http, gerar_pdf_imagem())
    assert resposta.status_code == 422
    assert cliente_http.fake.entradas == {}


def test_falha_da_ia_devolve_502_sem_json_de_extracao(cliente_http):
    cliente_http.fake.erro = ErroLLM("falha simulada")
    resposta = enviar(cliente_http, gerar_pdf_texto(FDS_ALCOOL_70))
    assert resposta.status_code == 502
    assert "secoes" not in resposta.json()


def _ia_devolve_concentracoes_do_etanol(cliente_http, minimo, maximo):
    resposta = cliente_http.fake.respostas[RespostaComposicaoLLM].model_dump()
    resposta["compostos"][0].update(concentracao_min=minimo, concentracao_max=maximo)
    cliente_http.fake.respostas[RespostaComposicaoLLM] = RespostaComposicaoLLM.model_validate(resposta)


def _pendencias_da_composicao(corpo):
    return [(p["secao"], p["campo"], p["motivo"]) for p in corpo["pendencias"] if p["secao"] == "03"]


def test_concentracao_1500_da_ia_vira_null_com_pendencia_e_resposta_200(cliente_http):
    _ia_devolve_concentracoes_do_etanol(cliente_http, 65, 1500)

    resposta = enviar(cliente_http, gerar_pdf_texto(FDS_ALCOOL_70))

    assert resposta.status_code == 200, resposta.text
    assert validar_contrato(resposta.text) == []
    corpo = resposta.json()
    assert corpo["status"] == "processado_com_pendencias"
    assert corpo["mensagem"]
    etanol = corpo["secoes"]["03"]["compostos"][0]
    assert (etanol["concentracao_min"], etanol["concentracao_max"]) == (65, None)
    assert _pendencias_da_composicao(corpo) == [("03", "concentracao_max", "dados_contraditorios")]


def test_minimo_acima_do_maximo_da_ia_anula_faixa_com_pendencia_e_resposta_200(cliente_http):
    _ia_devolve_concentracoes_do_etanol(cliente_http, 70, 65)

    resposta = enviar(cliente_http, gerar_pdf_texto(FDS_ALCOOL_70))

    assert resposta.status_code == 200, resposta.text
    assert validar_contrato(resposta.text) == []
    corpo = resposta.json()
    assert corpo["status"] == "processado_com_pendencias"
    etanol, agua = corpo["secoes"]["03"]["compostos"]
    assert (etanol["concentracao_min"], etanol["concentracao_max"]) == (None, None)
    assert (agua["concentracao_min"], agua["concentracao_max"]) == (30, 35)
    assert _pendencias_da_composicao(corpo) == [("03", "concentracao", "dados_contraditorios")]


def test_extracao_acima_do_prazo_devolve_504(cliente_http, monkeypatch):
    monkeypatch.setenv("EXTRATOR_TIMEOUT_SECONDS", "0.05")
    cliente_http.fake.atraso = 1.0
    assert enviar(cliente_http, gerar_pdf_texto(FDS_ALCOOL_70)).status_code == 504


def test_servico_sem_token_configurado_recusa_extracoes(cliente_http, monkeypatch):
    monkeypatch.delenv("EXTRATOR_API_TOKEN")
    assert enviar(cliente_http, gerar_pdf_texto(FDS_ALCOOL_70)).status_code == 503


def test_ia_sem_chave_configurada_devolve_503(cliente_http, monkeypatch):
    app.dependency_overrides.clear()
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr(app.state, "cliente_llm", None, raising=False)
    assert enviar(cliente_http, gerar_pdf_texto(FDS_ALCOOL_70)).status_code == 503
