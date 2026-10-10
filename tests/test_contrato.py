import pytest
from pydantic import ValidationError

from app.schemas.composto import Composto
from app.schemas.evidencia import Evidencia
from app.schemas.entrada import ExtracaoEntrada, Pagina, SecaoEntrada
from app.schemas.incompatibilidade import Incompatibilidade
from app.schemas.primeiro_socorro import OrientacaoGeral, PrimeiroSocorro


def evidencia(secao: str = "03") -> dict:
    return {"secao": secao, "pagina": 1, "texto_evidencia": "trecho da ficha"}


def test_evidencia_valida_e_rejeita_dados_fora_do_contrato():
    item = Evidencia.model_validate({**evidencia(), "texto_evidencia": "  trecho  "})
    assert item.texto_evidencia == "trecho"

    with pytest.raises(ValidationError):
        Evidencia.model_validate({**evidencia(), "campo_extra": "não permitido"})
    with pytest.raises(ValidationError):
        Evidencia.model_validate({**evidencia(), "pagina": 0})
    with pytest.raises(ValidationError):
        Evidencia.model_validate({**evidencia(), "secao": "13"})
    with pytest.raises(ValidationError):
        Evidencia.model_validate({**evidencia(), "texto_evidencia": "   "})


def test_entrada_valida_secoes_localizadas_e_nao_localizadas():
    entrada = ExtracaoEntrada.model_validate(
        {
            "documento": {
                "id_fds": 1,
                "id_produto": 2,
                "versao": "2026-01",
                "revisao": "rev-1",
            },
            "secoes": {
                "secao_3": {
                    "encontrada": True,
                    "paginas": [{"numero": 1, "texto": "  texto da seção  "}],
                },
                "secao_4": {"encontrada": False, "paginas": []},
                "secao_10": {
                    "encontrada": True,
                    "paginas": [{"numero": 3, "texto": "estabilidade"}],
                },
            },
        }
    )
    assert entrada.secoes.secao_3.paginas[0].texto == "texto da seção"
    assert entrada.secoes.secao_4.paginas == []

    with pytest.raises(ValidationError):
        SecaoEntrada(encontrada=True, paginas=[])
    with pytest.raises(ValidationError):
        SecaoEntrada(encontrada=False, paginas=[Pagina(numero=1, texto="conteúdo")])
    with pytest.raises(ValidationError):
        SecaoEntrada(
            encontrada=True,
            paginas=[Pagina(numero=1, texto="a"), Pagina(numero=1, texto="b")],
        )
    with pytest.raises(ValidationError):
        Pagina(numero=0, texto="conteúdo")


def test_composto_e_demais_contratos_das_secoes():
    composto = Composto.model_validate(
        {
            "nome": "Etanol",
            "cas_numero": "64-17-5",
            "concentracao_min": 10,
            "concentracao_max": 20,
            "unidade_concentracao": "%",
            "evidencias": [evidencia("03")],
        }
    )
    assert composto.nome == "Etanol"

    desconhecido = Composto.model_validate(
        {
            "nome": "Mistura proprietária",
            "cas_numero": None,
            "concentracao_min": None,
            "concentracao_max": None,
            "unidade_concentracao": None,
            "evidencias": [evidencia("03")],
        }
    )
    assert desconhecido.cas_numero is None

    primeiro_socorro = PrimeiroSocorro.model_validate(
        {
            "rota_exposicao": "olhos",
            "descricao": "Lavar com água.",
            "sintomas": None,
            "tratamento_especial": None,
            "atencao_medica_imediata": None,
            "evidencias": [evidencia("04")],
        }
    )
    orientacao = OrientacaoGeral.model_validate(
        {"descricao": "Consultar um médico.", "evidencias": [evidencia("04")]}
    )
    incompatibilidade = Incompatibilidade.model_validate(
        {
            "substancia_reagente": "Agente oxidante",
            "cas_numero": None,
            "descricao_risco": "Pode reagir violentamente.",
            "severidade": "alta",
            "evidencias": [evidencia("10")],
        }
    )
    assert primeiro_socorro.rota_exposicao == "olhos"
    assert orientacao.descricao == "Consultar um médico."
    assert incompatibilidade.severidade == "alta"
