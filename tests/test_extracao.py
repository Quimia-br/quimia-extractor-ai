import pytest
from pydantic import ValidationError

from app.schemas.saida import ExtracaoSaida


def evidencia(secao: str) -> dict:
    return {"secao": secao, "pagina": 1, "texto_evidencia": "trecho da FDS"}


def resposta_valida() -> dict:
    return {
        "documento": {
            "id_fds": 12,
            "id_produto": 34,
            "versao": "2026-01",
            "revisao": "rev-2",
        },
        "status": "processado",
        "mensagem": None,
        "secoes": {
            "03": {
                "encontrada": True,
                "compostos": [
                    {
                        "nome": "Etanol",
                        "cas_numero": "64-17-5",
                        "concentracao_min": 5,
                        "concentracao_max": 10,
                        "unidade_concentracao": "%",
                        "evidencias": [evidencia("03")],
                    }
                ],
            },
            "04": {
                "encontrada": True,
                "primeiros_socorros": [
                    {
                        "rota_exposicao": "inalacao",
                        "descricao": "Levar para local ventilado.",
                        "sintomas": None,
                        "tratamento_especial": None,
                        "atencao_medica_imediata": None,
                        "evidencias": [evidencia("04")],
                    }
                ],
                "orientacoes_gerais": [],
                "notas_ao_medico": [],
            },
            "10": {
                "encontrada": True,
                "situacao": "identificadas",
                "incompatibilidades": [
                    {
                        "substancia_reagente": "Agente oxidante",
                        "cas_numero": None,
                        "descricao_risco": "Pode reagir com o produto.",
                        "severidade": "alta",
                        "evidencias": [evidencia("10")],
                    }
                ],
                "evidencias": [],
            },
        },
        "pendencias": [],
        "requer_confirmacao": True,
    }


def resposta_com_secoes_nao_localizadas() -> dict:
    dados = resposta_valida()
    dados["status"] = "processado_com_pendencias"
    dados["mensagem"] = "Informações ausentes, verifique o documento anexado"
    dados["secoes"] = {
        "03": {"encontrada": False, "compostos": []},
        "04": {
            "encontrada": False,
            "primeiros_socorros": [],
            "orientacoes_gerais": [],
            "notas_ao_medico": [],
        },
        "10": {
            "encontrada": False,
            "situacao": "secao_nao_localizada",
            "incompatibilidades": [],
            "evidencias": [],
        },
    }
    dados["pendencias"] = [
        {
            "secao": numero,
            "campo": "secao",
            "motivo": "secao_nao_localizada",
            "descricao": "A seção não foi localizada na ficha.",
            "evidencias": [],
        }
        for numero in ("03", "04", "10")
    ]
    return dados


def test_resposta_completa_valida_e_serializa_aliases_das_secoes():
    resposta = ExtracaoSaida.model_validate(resposta_valida())
    assert resposta.status == "processado"
    assert resposta.requer_confirmacao is True
    assert resposta.secoes.composicao.compostos[0].nome == "Etanol"
    assert set(resposta.model_dump(by_alias=True)["secoes"]) == {"03", "04", "10"}


def test_resposta_com_pendencias_e_secoes_nao_localizadas_e_valida():
    resposta = ExtracaoSaida.model_validate(resposta_com_secoes_nao_localizadas())
    assert resposta.status == "processado_com_pendencias"
    assert len(resposta.pendencias) == 3
    assert resposta.secoes.incompatibilidades.situacao == "secao_nao_localizada"


def test_saida_rejeita_status_ou_mensagem_inconsistentes():
    dados = resposta_valida()
    dados["status"] = "processado_com_pendencias"
    with pytest.raises(ValidationError, match="Status deve refletir"):
        ExtracaoSaida.model_validate(dados)

    dados = resposta_com_secoes_nao_localizadas()
    dados["mensagem"] = None
    with pytest.raises(ValidationError, match="exige mensagem"):
        ExtracaoSaida.model_validate(dados)


def test_saida_rejeita_dados_em_secao_nao_localizada():
    dados = resposta_com_secoes_nao_localizadas()
    dados["secoes"]["03"]["compostos"] = resposta_valida()["secoes"]["03"]["compostos"]
    with pytest.raises(ValidationError, match="não pode conter dados"):
        ExtracaoSaida.model_validate(dados)


def test_saida_exige_pendencia_para_cada_secao_nao_localizada():
    dados = resposta_com_secoes_nao_localizadas()
    dados["pendencias"] = [dados["pendencias"][1]]
    with pytest.raises(ValidationError, match="pendência correspondente"):
        ExtracaoSaida.model_validate(dados)
