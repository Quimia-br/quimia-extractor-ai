import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.saida import ExtracaoSaida


def resposta_valida() -> dict:
    fixture_path = Path(__file__).parent / "fixtures" / "resposta_extracao_completa.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


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
    assert resposta.secoes.composicao.compostos[0].nome == "Etanol"
    assert set(resposta.model_dump(by_alias=True)["secoes"]) == {"03", "04", "10"}


def test_json_serializado_contem_dados_extraidos_e_evidencias():
    resposta = ExtracaoSaida.model_validate(resposta_valida())
    raw_json = resposta.model_dump(mode="json", by_alias=True)

    composto = raw_json["secoes"]["03"]["compostos"][0]
    assert composto["nome"] == "Etanol"
    assert composto["cas_numero"] == "64-17-5"
    assert composto["unidade_concentracao"] == "%"
    assert composto["evidencias"][0]["secao"] == "03"

    primeiro_socorro = raw_json["secoes"]["04"]["primeiros_socorros"][0]
    assert primeiro_socorro["atencao_medica_imediata"] is True
    assert primeiro_socorro["evidencias"][0]["secao"] == "04"

    incompatibilidade = raw_json["secoes"]["10"]["incompatibilidades"][0]
    assert incompatibilidade["severidade"] == "alta"
    assert incompatibilidade["evidencias"][0]["secao"] == "10"


def test_json_serializado_preserva_atencao_medica_indeterminada_como_null():
    dados = resposta_valida()
    dados["secoes"]["04"]["primeiros_socorros"][0]["atencao_medica_imediata"] = None

    resposta = ExtracaoSaida.model_validate(dados)
    raw_json = resposta.model_dump(mode="json", by_alias=True)

    assert raw_json["secoes"]["04"]["primeiros_socorros"][0]["atencao_medica_imediata"] is None


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
