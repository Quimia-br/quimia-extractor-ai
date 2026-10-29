from fastapi.testclient import TestClient

from app.main import app
from app.core.exceptions import ConfiguracaoLLMInvalida, CreditoLLMInsuficiente, ErroLLM
from app.schemas.respostas_llm import RespostaComposicaoLLM
from app.routes import extracao as rota_extracao


def test_health_e_interface_disponiveis():
    with TestClient(app) as cliente:
        resposta = cliente.get("/health")
        pagina = cliente.get("/teste")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}
    assert pagina.status_code == 200
    assert "Processar FDS" in pagina.text
    assert set(app.openapi()["paths"]) == {"/health", "/api/extracoes", "/extracoes"}


def entrada(secao_3=True):
    return {"secoes": {
        "secao_3": {"encontrada": secao_3, "paginas": [{"numero": 2, "texto": "Etanol: 5 a 10%."}] if secao_3 else []},
        "secao_4": {"encontrada": False, "paginas": []},
        "secao_10": {"encontrada": False, "paginas": []},
    }}


class ClienteFake:
    chamadas = 0
    fechamentos = 0

    async def responder_estruturado(self, *, modelo, instrucoes, entrada):
        self.chamadas += 1
        assert modelo is RespostaComposicaoLLM
        return RespostaComposicaoLLM.model_validate({
            "compostos": [{
                "nome": "Etanol", "cas_numero": None, "concentracao_min": 5,
                "concentracao_max": 10, "unidade_concentracao": "%",
                "evidencias": [{"secao": "03", "pagina": 2, "texto_evidencia": "Etanol: 5 a 10%."}],
            }],
            "pendencias": [],
        })

    async def fechar(self):
        self.fechamentos += 1


def test_endpoint_executa_servico_real_e_serializa_contrato(monkeypatch):
    fake = ClienteFake()
    monkeypatch.setattr(rota_extracao, "LLMClient", lambda: fake)
    with TestClient(app) as cliente:
        resposta = cliente.post("/api/extracoes", json=entrada())

    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["status"] == "processado_com_pendencias"
    assert set(dados["secoes"]) == {"03", "04", "10"}
    assert dados["secoes"]["03"]["compostos"][0]["nome"] == "Etanol"
    assert {item["secao"] for item in dados["pendencias"]} == {"04", "10"}
    assert fake.chamadas == 1
    assert fake.fechamentos == 1


def test_json_invalido_e_schema_invalido_tem_erros_distintos():
    with TestClient(app) as cliente:
        json_invalido = cliente.post("/api/extracoes", content="{", headers={"content-type": "application/json"})
        schema_invalido = cliente.post("/api/extracoes", json={"secoes": {}})

    assert json_invalido.status_code == 422
    assert json_invalido.json()["erro"]["tipo"] == "json_invalido"
    assert schema_invalido.status_code == 422
    assert schema_invalido.json()["erro"]["tipo"] == "validacao"
    assert schema_invalido.json()["erro"]["detalhes"]


def test_limite_de_texto_retorna_erro_de_validacao(monkeypatch):
    fake = ClienteFake()
    monkeypatch.setattr(rota_extracao, "LLMClient", lambda: fake)
    dados = entrada()
    dados["secoes"]["secao_3"]["paginas"][0]["texto"] = "x" * 30_001
    with TestClient(app) as cliente:
        resposta = cliente.post("/api/extracoes", json=dados)

    assert resposta.status_code == 422
    assert resposta.json()["erro"]["tipo"] == "validacao"
    assert fake.chamadas == 0
    assert fake.fechamentos == 1


def test_falhas_de_configuracao_e_processamento_sao_exibidas(monkeypatch):
    def sem_configuracao():
        raise ConfiguracaoLLMInvalida("OPENAI_API_KEY ausente.")

    monkeypatch.setattr(rota_extracao, "LLMClient", sem_configuracao)
    with TestClient(app) as cliente:
        configuracao = cliente.post("/api/extracoes", json=entrada())
    assert configuracao.status_code == 503
    assert configuracao.json()["erro"]["tipo"] == "configuracao"

    class ClienteComFalha(ClienteFake):
        async def responder_estruturado(self, **kwargs):
            raise ErroLLM("O provedor de IA não conseguiu gerar uma resposta válida.")

    fake = ClienteComFalha()
    monkeypatch.setattr(rota_extracao, "LLMClient", lambda: fake)
    with TestClient(app) as cliente:
        processamento = cliente.post("/api/extracoes", json=entrada())
    assert processamento.status_code == 502
    assert processamento.json()["erro"]["tipo"] == "processamento"
    assert fake.fechamentos == 1

    class ClienteSemCredito(ClienteFake):
        async def responder_estruturado(self, **kwargs):
            raise CreditoLLMInsuficiente("A conta da API OpenAI está sem créditos.")

    monkeypatch.setattr(rota_extracao, "LLMClient", ClienteSemCredito)
    with TestClient(app) as cliente:
        credito = cliente.post("/api/extracoes", json=entrada())
    assert credito.status_code == 503
    assert credito.json()["erro"]["tipo"] == "configuracao"
    assert "sem créditos" in credito.json()["erro"]["mensagem"]


def test_acesso_remoto_exige_liberacao_explicita(monkeypatch):
    monkeypatch.delenv("EXTRACTION_ALLOW_REMOTE", raising=False)
    with TestClient(app, base_url="http://example.com") as cliente:
        resposta = cliente.post("/api/extracoes", json=entrada())
    assert resposta.status_code == 403
    assert resposta.json()["erro"]["tipo"] == "acesso"
