import asyncio

import pytest

from app.core.exceptions import EntradaInvalida, EvidenciaInvalida
from app.schemas.entrada import ExtracaoEntrada
from app.schemas.respostas_llm import (
    RespostaComposicaoLLM,
    RespostaIncompatibilidadesLLM,
    RespostaPrimeirosSocorrosLLM,
)
from app.services.extracao_service import ExtracaoService


class FakeLLM:
    def __init__(self, respostas):
        self.respostas = respostas
        self.chamadas = []

    async def responder_estruturado(self, *, modelo, instrucoes, entrada):
        self.chamadas.append((modelo, instrucoes, entrada))
        return self.respostas[modelo]


def entrada_completa():
    return ExtracaoEntrada.model_validate(
        {
            "secoes": {
                "secao_3": {
                    "encontrada": True,
                    "paginas": [
                        {
                            "numero": 2,
                            "texto": "Etanol: concentração entre 5 e 10%.",
                        }
                    ],
                },
                "secao_4": {
                    "encontrada": True,
                    "paginas": [
                        {
                            "numero": 3,
                            "texto": "Levar para local ventilado. Pode causar tontura e sonolência. Atendimento médico imediato em casos graves.",
                        }
                    ],
                },
                "secao_10": {
                    "encontrada": True,
                    "paginas": [
                        {
                            "numero": 8,
                            "texto": "Incompatível com agentes oxidantes fortes. Pode reagir com o produto.",
                        }
                    ],
                },
            },
        }
    )


def respostas_validas():
    return {
        RespostaComposicaoLLM: RespostaComposicaoLLM.model_validate(
            {
                "compostos": [
                    {
                        "nome": "Etanol",
                        "cas_numero": "64-17-5",
                        "concentracao_min": 5,
                        "concentracao_max": 10,
                        "unidade_concentracao": "%",
                        "evidencias": [
                            {
                                "secao": "03",
                                "pagina": 2,
                                "texto_evidencia": "Etanol: concentração entre 5 e 10%.",
                            }
                        ],
                    }
                ],
                "pendencias": [],
            }
        ),
        RespostaPrimeirosSocorrosLLM: RespostaPrimeirosSocorrosLLM.model_validate(
            {
                "primeiros_socorros": [
                    {
                        "rota_exposicao": "inalacao",
                        "descricao": "Levar para local ventilado.",
                        "sintomas": "Tontura e sonolência.",
                        "tratamento_especial": None,
                        "atencao_medica_imediata": True,
                        "evidencias": [
                            {
                                "secao": "04",
                                "pagina": 3,
                                "texto_evidencia": "Levar para local ventilado. Pode causar tontura e sonolência. Atendimento médico imediato em casos graves.",
                            }
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
                        "descricao_risco": "Pode reagir com o produto.",
                        "severidade": "alta",
                        "evidencias": [
                            {
                                "secao": "10",
                                "pagina": 8,
                                "texto_evidencia": "Incompatível com agentes oxidantes fortes. Pode reagir com o produto.",
                            }
                        ],
                    }
                ],
                "evidencias": [],
                "pendencias": [],
            }
        ),
    }


def test_servico_extrai_tres_secoes_e_devolve_dados_estruturados():
    cliente = FakeLLM(respostas_validas())
    saida = asyncio.run(ExtracaoService(cliente).extrair(entrada_completa()))

    json_saida = saida.model_dump(mode="json", by_alias=True)
    assert set(json_saida["secoes"]) == {"03", "04", "10"}
    assert json_saida["status"] == "processado"
    assert json_saida["secoes"]["03"]["compostos"][0]["cas_numero"] == "64-17-5"
    assert json_saida["secoes"]["04"]["primeiros_socorros"][0]["evidencias"]
    assert json_saida["secoes"]["10"]["incompatibilidades"][0]["severidade"] == "alta"
    assert len(cliente.chamadas) == 3


def test_servico_nao_chama_ia_para_secoes_nao_localizadas():
    dados = entrada_completa().model_dump()
    dados["secoes"] = {
        "secao_3": {"encontrada": False, "paginas": []},
        "secao_4": {"encontrada": False, "paginas": []},
        "secao_10": {"encontrada": False, "paginas": []},
    }
    entrada = ExtracaoEntrada.model_validate(dados)
    cliente = FakeLLM({})

    saida = asyncio.run(ExtracaoService(cliente).extrair(entrada))

    assert cliente.chamadas == []
    assert saida.status == "processado_com_pendencias"
    assert {item.secao for item in saida.pendencias} == {"03", "04", "10"}


def test_servico_rejeita_evidencia_que_nao_existe_no_texto():
    respostas = respostas_validas()
    respostas[RespostaComposicaoLLM] = RespostaComposicaoLLM.model_validate(
        {
            "compostos": [
                {
                    "nome": "Etanol",
                    "cas_numero": "64-17-5",
                    "concentracao_min": 5,
                    "concentracao_max": 10,
                    "unidade_concentracao": "%",
                    "evidencias": [
                        {
                            "secao": "03",
                            "pagina": 2,
                            "texto_evidencia": "Trecho inventado.",
                        }
                    ],
                }
            ],
            "pendencias": [],
        }
    )

    with pytest.raises(EvidenciaInvalida):
        asyncio.run(ExtracaoService(FakeLLM(respostas)).extrair(entrada_completa()))


def test_servico_cria_pendencia_quando_secao_10_nao_especifica_incompatibilidades():
    respostas = respostas_validas()
    respostas[RespostaIncompatibilidadesLLM] = RespostaIncompatibilidadesLLM.model_validate(
        {
            "situacao": "nao_especificadas",
            "incompatibilidades": [],
            "evidencias": [],
            "pendencias": [],
        }
    )

    saida = asyncio.run(ExtracaoService(FakeLLM(respostas)).extrair(entrada_completa()))

    pendencia_10 = next(item for item in saida.pendencias if item.secao == "10")
    assert pendencia_10.motivo == "documento_nao_especifica"
    assert saida.mensagem == "Informações ausentes, verifique o documento anexado"


def test_servico_rejeita_requisicao_acima_do_limite():
    entrada = entrada_completa()
    entrada.secoes.secao_3.paginas[0].texto = "x" * 30_001

    with pytest.raises(EntradaInvalida):
        asyncio.run(ExtracaoService(FakeLLM({})).extrair(entrada))


def test_servico_rejeita_pendencia_associada_a_outra_secao():
    respostas = respostas_validas()
    respostas[RespostaComposicaoLLM] = RespostaComposicaoLLM.model_validate(
        {
            "compostos": [],
            "pendencias": [
                {
                    "secao": "10",
                    "campo": "composicao",
                    "motivo": "informacao_ausente",
                    "descricao": "Pendência associada à seção incorreta.",
                    "evidencias": [],
                }
            ],
        }
    )

    with pytest.raises(EvidenciaInvalida):
        asyncio.run(ExtracaoService(FakeLLM(respostas)).extrair(entrada_completa()))


def test_servico_rejeita_texto_total_acima_do_limite():
    dados = entrada_completa().model_dump()
    dados["secoes"]["secao_3"]["paginas"] = [
        {"numero": numero, "texto": "x" * 25_000}
        for numero in range(1, 6)
    ]
    entrada = ExtracaoEntrada.model_validate(dados)

    with pytest.raises(EntradaInvalida):
        asyncio.run(ExtracaoService(FakeLLM({})).extrair(entrada))
