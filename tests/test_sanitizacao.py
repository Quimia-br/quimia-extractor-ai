import json
from pathlib import Path

import pytest

from app.validators.saida_http import sanitizar_saida
from tests.contrato_api import validar_contrato

FIXTURE = Path(__file__).parent / "fixtures" / "resposta_extracao_completa.json"


def saida_valida() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def serializar(dados: dict) -> str:
    # Mesmo serializador da JSONResponse: recusa NaN/Infinity.
    return json.dumps(dados, ensure_ascii=False, allow_nan=False)


def composto(dados: dict) -> dict:
    return dados["secoes"]["03"]["compostos"][0]


def test_fixture_original_ja_cumpre_o_contrato_e_nao_muda():
    dados = saida_valida()
    assert validar_contrato(serializar(dados)) == []
    assert sanitizar_saida(dados) == dados


def test_texto_com_nul_vira_espaco_em_qualquer_campo():
    dados = saida_valida()
    composto(dados)["nome"] = "Eta\x00nol"
    dados["secoes"]["04"]["primeiros_socorros"][0]["descricao"] = "Levar\x00 ao ar livre."
    dados["secoes"]["10"]["incompatibilidades"][0]["substancia_reagente"] = "Oxidantes\x00"

    saida = sanitizar_saida(dados)

    assert composto(saida)["nome"] == "Eta nol"
    assert "\x00" not in serializar(saida)
    assert validar_contrato(serializar(saida)) == []


def test_nome_com_300_caracteres_e_cortado_em_255():
    dados = saida_valida()
    composto(dados)["nome"] = "N" * 300

    saida = sanitizar_saida(dados)

    assert composto(saida)["nome"] == "N" * 255
    assert validar_contrato(serializar(saida)) == []


def test_nome_vazio_remove_composto_e_registra_pendencia():
    dados = saida_valida()
    composto(dados)["nome"] = "\x00 "

    saida = sanitizar_saida(dados)

    assert saida["secoes"]["03"]["compostos"] == []
    assert saida["pendencias"][-1]["campo"] == "nome"
    assert validar_contrato(serializar(saida)) == []


@pytest.mark.parametrize("valor", [1500, -1, float("nan"), float("inf"), "10%", True, 999.996])
def test_concentracao_fora_da_faixa_vira_null_com_pendencia(valor):
    dados = saida_valida()
    composto(dados)["concentracao_max"] = valor

    saida = sanitizar_saida(dados)

    assert composto(saida)["concentracao_max"] is None
    assert composto(saida)["concentracao_min"] == 5
    assert saida["status"] == "processado_com_pendencias"
    assert saida["mensagem"]
    assert any(p["campo"] == "concentracao_max" and p["secao"] == "03" for p in saida["pendencias"])
    assert validar_contrato(serializar(saida)) == []


def test_concentracao_minima_maior_que_maxima_anula_a_faixa():
    dados = saida_valida()
    composto(dados)["concentracao_min"] = 20
    composto(dados)["concentracao_max"] = 10

    saida = sanitizar_saida(dados)

    assert composto(saida)["concentracao_min"] is None
    assert composto(saida)["concentracao_max"] is None
    assert any(p["motivo"] == "dados_contraditorios" for p in saida["pendencias"])
    assert validar_contrato(serializar(saida)) == []


def test_cas_acima_de_20_caracteres_vira_null():
    dados = saida_valida()
    composto(dados)["cas_numero"] = "1" * 25

    saida = sanitizar_saida(dados)

    assert composto(saida)["cas_numero"] is None
    assert validar_contrato(serializar(saida)) == []


def test_severidade_fora_da_lista_vira_null_com_pendencia():
    dados = saida_valida()
    dados["secoes"]["10"]["incompatibilidades"][0]["severidade"] = "extrema"

    saida = sanitizar_saida(dados)

    assert saida["secoes"]["10"]["incompatibilidades"][0]["severidade"] is None
    assert any(p["secao"] == "10" and p["campo"] == "severidade" for p in saida["pendencias"])
    assert validar_contrato(serializar(saida)) == []


def test_substancia_reagente_e_cortada_em_255():
    dados = saida_valida()
    dados["secoes"]["10"]["incompatibilidades"][0]["substancia_reagente"] = "S" * 400

    saida = sanitizar_saida(dados)

    assert len(saida["secoes"]["10"]["incompatibilidades"][0]["substancia_reagente"]) == 255
    assert validar_contrato(serializar(saida)) == []


def test_descartes_da_secao_13_saem_dentro_das_regras():
    dados = saida_valida()
    dados["secoes"]["13"] = {
        "descartes": [
            {"instrucao_descarte": 42, "tipo_residuo": "toxico"},
            {"instrucao_descarte": "Incinerar.", "tipo_residuo": "quimico"},
        ]
    }

    saida = sanitizar_saida(dados)

    assert saida["secoes"]["13"]["descartes"] == [
        {"instrucao_descarte": None, "tipo_residuo": None},
        {"instrucao_descarte": "Incinerar.", "tipo_residuo": "quimico"},
    ]
    assert validar_contrato(serializar(saida)) == []


def test_sanitizacao_nao_altera_a_entrada():
    dados = saida_valida()
    composto(dados)["concentracao_max"] = 1500
    sanitizar_saida(dados)
    assert composto(dados)["concentracao_max"] == 1500


def test_validador_de_contrato_acusa_violacoes():
    dados = saida_valida()
    composto(dados)["nome"] = "N" * 300
    composto(dados)["concentracao_min"] = 20
    dados["secoes"]["10"]["incompatibilidades"][0]["severidade"] = "extrema"
    dados["status"] = "ok"
    corpo = json.dumps(dados).replace('"Etanol', '"Eta\\u0000nol', 1)

    erros = validar_contrato(corpo)

    assert len(erros) >= 4
    assert validar_contrato(corpo + " {}")[0].startswith("raiz")
    assert validar_contrato('{"x": NaN}')[0].startswith("raiz")
