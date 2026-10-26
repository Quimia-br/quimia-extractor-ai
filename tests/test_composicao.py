import asyncio
import math

import pytest

from app.extractors.composicao import extrair_composicao
from app.schemas.entrada import SecaoEntrada
from app.schemas.respostas_llm import RespostaComposicaoLLM

EVIDENCIA = {"secao": "03", "pagina": 1, "texto_evidencia": "Etanol 64-17-5"}
SECAO = SecaoEntrada(encontrada=True, paginas=[{"numero": 1, "texto": "Etanol 64-17-5"}])


class FakeLLM:
    def __init__(self, resposta):
        self.resposta = resposta

    async def responder_estruturado(self, *, modelo, instrucoes, entrada):
        return self.resposta


def extrair(minimo, maximo, unidade="%", pendencias=None):
    resposta = RespostaComposicaoLLM.model_validate(
        {
            "compostos": [
                {
                    "nome": "Etanol",
                    "cas_numero": "64-17-5",
                    "concentracao_min": minimo,
                    "concentracao_max": maximo,
                    "unidade_concentracao": unidade,
                    "evidencias": [EVIDENCIA],
                }
            ],
            "pendencias": pendencias or [],
        }
    )
    composicao, pendencias_saida = asyncio.run(extrair_composicao(FakeLLM(resposta), SECAO))
    return composicao.compostos[0], pendencias_saida


def test_resposta_tolerante_aceita_valores_fora_do_contrato():
    resposta = RespostaComposicaoLLM.model_validate(
        {
            "compostos": [
                {
                    "nome": "Etanol",
                    "cas_numero": None,
                    "concentracao_min": math.nan,
                    "concentracao_max": 1500,
                    "unidade_concentracao": "%",
                    "evidencias": [EVIDENCIA],
                }
            ],
            "pendencias": [],
        }
    )
    assert resposta.compostos[0].concentracao_max == 1500


def test_concentracao_valida_e_mantida_sem_pendencia():
    composto, pendencias = extrair(65, 70)
    assert (composto.concentracao_min, composto.concentracao_max) == (65, 70)
    assert pendencias == []


@pytest.mark.parametrize(
    ("valor", "unidade"),
    [
        (1500, "g/L"),
        (999.996, "mg/kg"),
        (-1, "%"),
        (100.5, "%"),
        (math.nan, "%"),
        (math.inf, "%"),
        (-math.inf, None),
    ],
    ids=["acima-999.99", "arredonda-para-1000", "negativa", "percentual-acima-100", "nan", "infinity", "-infinity"],
)
def test_concentracao_fora_do_contrato_vira_null_com_pendencia(valor, unidade):
    composto, pendencias = extrair(10, valor, unidade)

    assert composto.concentracao_min == 10
    assert composto.concentracao_max is None
    assert len(pendencias) == 1
    pendencia = pendencias[0]
    assert (pendencia.secao, pendencia.campo, pendencia.motivo) == ("03", "concentracao_max", "dados_contraditorios")
    assert pendencia.evidencias[0].texto_evidencia == EVIDENCIA["texto_evidencia"]


def test_unidade_nao_percentual_aceita_valores_acima_de_100():
    composto, pendencias = extrair(150, 999.99, "g/L")
    assert (composto.concentracao_min, composto.concentracao_max) == (150, 999.99)
    assert pendencias == []


def test_minimo_acima_do_maximo_anula_a_faixa_com_pendencia():
    composto, pendencias = extrair(70, 65)

    assert (composto.concentracao_min, composto.concentracao_max) == (None, None)
    assert [(p.secao, p.campo, p.motivo) for p in pendencias] == [("03", "concentracao", "dados_contraditorios")]


def test_ambas_fora_do_contrato_geram_uma_pendencia_por_campo():
    composto, pendencias = extrair(-5, 1500)

    assert (composto.concentracao_min, composto.concentracao_max) == (None, None)
    assert [p.campo for p in pendencias] == ["concentracao_min", "concentracao_max"]


def test_pendencias_da_ia_sao_preservadas_antes_das_novas():
    pendencia_ia = {
        "secao": "03",
        "campo": "cas_numero",
        "motivo": "informacao_ausente",
        "descricao": "CAS ausente.",
        "evidencias": [],
    }
    _, pendencias = extrair(10, 1500, pendencias=[pendencia_ia])
    assert [p.campo for p in pendencias] == ["cas_numero", "concentracao_max"]


TEXTO_DUAS_LINHAS = "Etanol 64-17-5 5 - 10\nHipoclorito de Sódio 7681-52-9 2 - 2,5 NaClO"
LINHA_ETANOL = "Etanol 64-17-5 5 - 10"
LINHA_HIPOCLORITO = "Hipoclorito de Sódio 7681-52-9 2 - 2,5 NaClO"


def extrair_dois_compostos(evidencias_da_pendencia, campo="unidade_concentracao"):
    def composto(nome, cas, linha, unidade):
        return {
            "nome": nome,
            "cas_numero": cas,
            "concentracao_min": 2,
            "concentracao_max": 10,
            "unidade_concentracao": unidade,
            "evidencias": [{"secao": "03", "pagina": 1, "texto_evidencia": linha}],
        }

    resposta = RespostaComposicaoLLM.model_validate(
        {
            "compostos": [
                composto("Etanol", "64-17-5", LINHA_ETANOL, "%"),
                composto("Hipoclorito de Sódio", "7681-52-9", LINHA_HIPOCLORITO, None),
            ],
            "pendencias": [
                {
                    "secao": "03",
                    "campo": campo,
                    "motivo": "informacao_ausente",
                    "descricao": "A unidade de concentração não está especificada.",
                    "evidencias": evidencias_da_pendencia,
                }
            ],
        }
    )
    secao = SecaoEntrada(encontrada=True, paginas=[{"numero": 1, "texto": TEXTO_DUAS_LINHAS}])
    _, pendencias = asyncio.run(extrair_composicao(FakeLLM(resposta), secao))
    return pendencias[0]


def test_pendencia_aponta_o_composto_cuja_evidencia_ela_repete():
    pendencia = extrair_dois_compostos([{"secao": "03", "pagina": 1, "texto_evidencia": LINHA_HIPOCLORITO}])
    assert pendencia.composto is not None
    assert (pendencia.composto.indice, pendencia.composto.nome, pendencia.composto.cas_numero) == (
        1,
        "Hipoclorito de Sódio",
        "7681-52-9",
    )


def test_pendencia_sem_correspondencia_unica_fica_sem_referencia():
    assert extrair_dois_compostos([]).composto is None


def test_pendencia_de_campo_fora_do_composto_nao_recebe_referencia():
    pendencia = extrair_dois_compostos(
        [{"secao": "03", "pagina": 1, "texto_evidencia": LINHA_HIPOCLORITO}], campo="composicao"
    )
    assert pendencia.composto is None


def test_unico_composto_resolve_pendencia_sem_evidencia():
    _, pendencias = extrair(10, 20, unidade=None, pendencias=[
        {
            "secao": "03",
            "campo": "unidade_concentracao",
            "motivo": "informacao_ausente",
            "descricao": "A unidade de concentração não está especificada.",
            "evidencias": [],
        }
    ])
    assert pendencias[0].composto.indice == 0
