import pytest
from pydantic import ValidationError

from app.schemas.composto import Composto
from app.schemas.incompatibilidade import Incompatibilidade
from app.schemas.primeiro_socorro import PrimeiroSocorro
from app.schemas.saida import (
    IncompatibilidadesExtraidas,
    Pendencia,
    PrimeirosSocorrosExtraidos,
)


def evidencia(secao: str) -> dict:
    return {"secao": secao, "pagina": 2, "texto_evidencia": "trecho relevante"}


def composto(minimo: float | None, maximo: float | None, unidade: str | None) -> dict:
    return {
        "nome": "Substância",
        "cas_numero": "64-17-5",
        "concentracao_min": minimo,
        "concentracao_max": maximo,
        "unidade_concentracao": unidade,
        "evidencias": [evidencia("03")],
    }


def incompatibilidade() -> dict:
    return {
        "substancia_reagente": "Agente oxidante",
        "cas_numero": None,
        "descricao_risco": "Reação possível.",
        "severidade": "media",
        "evidencias": [evidencia("10")],
    }


def socorro(rota: str) -> dict:
    return {
        "rota_exposicao": rota,
        "descricao": "Lavar com água.",
        "sintomas": None,
        "tratamento_especial": None,
        "atencao_medica_imediata": None,
        "evidencias": [evidencia("04")],
    }


def test_composto_rejeita_intervalo_invertido_e_percentual_acima_de_cem():
    with pytest.raises(ValidationError, match="concentracao_min"):
        Composto.model_validate(composto(30, 20, "%"))
    with pytest.raises(ValidationError, match="percentual"):
        Composto.model_validate(composto(100.1, None, "%"))

    unidade_nao_percentual = Composto.model_validate(composto(150, None, "g/L"))
    assert unidade_nao_percentual.concentracao_min == 150


def test_primeiros_socorros_exigem_uma_entrada_por_rota():
    validos = PrimeirosSocorrosExtraidos.model_validate(
        {
            "encontrada": True,
            "primeiros_socorros": [socorro("pele"), socorro("olhos")],
            "orientacoes_gerais": [],
            "notas_ao_medico": [],
        }
    )
    assert len(validos.primeiros_socorros) == 2

    with pytest.raises(ValidationError, match="Agrupe"):
        PrimeirosSocorrosExtraidos.model_validate(
            {
                "encontrada": True,
                "primeiros_socorros": [socorro("pele"), socorro("pele")],
                "orientacoes_gerais": [],
                "notas_ao_medico": [],
            }
        )

    with pytest.raises(ValidationError):
        PrimeiroSocorro.model_validate({**socorro("pele"), "rota_exposicao": "corpo todo"})


def test_incompatibilidades_validam_estado_e_evidencia_de_ausencia():
    identificadas = IncompatibilidadesExtraidas.model_validate(
        {
            "encontrada": True,
            "situacao": "identificadas",
            "incompatibilidades": [incompatibilidade()],
            "evidencias": [],
        }
    )
    ausentes = IncompatibilidadesExtraidas.model_validate(
        {
            "encontrada": True,
            "situacao": "ausencia_declarada",
            "incompatibilidades": [],
            "evidencias": [evidencia("10")],
        }
    )
    nao_especificadas = IncompatibilidadesExtraidas.model_validate(
        {
            "encontrada": True,
            "situacao": "nao_especificadas",
            "incompatibilidades": [],
            "evidencias": [],
        }
    )
    nao_localizada = IncompatibilidadesExtraidas.model_validate(
        {
            "encontrada": False,
            "situacao": "secao_nao_localizada",
            "incompatibilidades": [],
            "evidencias": [],
        }
    )
    assert identificadas.situacao == "identificadas"
    assert ausentes.evidencias
    assert nao_especificadas.incompatibilidades == []
    assert nao_localizada.encontrada is False

    with pytest.raises(ValidationError, match="localização"):
        IncompatibilidadesExtraidas.model_validate(
            {
                "encontrada": False,
                "situacao": "identificadas",
                "incompatibilidades": [],
                "evidencias": [],
            }
        )
    with pytest.raises(ValidationError, match="Somente"):
        IncompatibilidadesExtraidas.model_validate(
            {
                "encontrada": True,
                "situacao": "nao_especificadas",
                "incompatibilidades": [incompatibilidade()],
                "evidencias": [],
            }
        )
    with pytest.raises(ValidationError, match="evidência explícita"):
        IncompatibilidadesExtraidas.model_validate(
            {
                "encontrada": True,
                "situacao": "ausencia_declarada",
                "incompatibilidades": [],
                "evidencias": [],
            }
        )
    with pytest.raises(ValidationError):
        Incompatibilidade.model_validate({**incompatibilidade(), "severidade": "extrema"})


def test_pendencia_restringe_motivos_previstos_no_contrato():
    pendencia = Pendencia.model_validate(
        {
            "secao": "03",
            "campo": "concentracao",
            "motivo": "informacao_ausente",
            "descricao": "A ficha não informa a concentração.",
            "evidencias": [],
        }
    )
    assert pendencia.motivo == "informacao_ausente"

    with pytest.raises(ValidationError):
        Pendencia.model_validate(
            {
                "secao": "03",
                "campo": "concentracao",
                "motivo": "inventado",
                "descricao": "Motivo fora do contrato.",
                "evidencias": [],
            }
        )
