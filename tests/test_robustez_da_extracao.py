import asyncio

import pytest

from app.core.exceptions import CreditoLLMInsuficiente, ErroLLM, EvidenciaInvalida
from app.extractors.incompatibilidades import extrair_incompatibilidades
from app.schemas.entrada import ExtracaoEntrada, Pagina, SecaoEntrada, SecoesEntrada
from app.schemas.evidencia import Evidencia
from app.schemas.respostas_llm import RespostaIncompatibilidadesLLM
from app.schemas.saida import Pendencia
from app.services.extracao_service import ExtracaoService
from app.validators.extracao import validar_evidencias

PAGINA_COM_PALAVRAS_ABERTAS = (
    "4.3 - Ingestão\n Se ingerido, não provoque o vômito. Cont ate imediatamente um Centro de Informação "
    "Toxicológica\n e/ou um m édico.\n Reage violentamente com:\n Ácido fórmico\n Aminas\n Metanol"
)


def secao(texto: str, numero_secao: str = "04") -> SecaoEntrada:
    return SecaoEntrada(encontrada=True, paginas=[Pagina(numero=1, texto=texto)])


def resultado_com_citacao(citacao: str, numero_secao: str = "04") -> Pendencia:
    return Pendencia(
        secao=numero_secao,
        campo="primeiros_socorros",
        motivo="informacao_ausente",
        descricao="Descrição qualquer.",
        evidencias=[Evidencia(secao=numero_secao, pagina=1, texto_evidencia=citacao)],
    )


def validar(citacao: str) -> None:
    validar_evidencias(
        resultado_com_citacao(citacao), numero_secao="04", entrada=secao(PAGINA_COM_PALAVRAS_ABERTAS)
    )


def test_citacao_com_a_palavra_inteira_vale_mesmo_que_o_pdf_tenha_aberto_a_palavra():
    validar("Contate imediatamente um Centro de Informação Toxicológica e/ou um médico.")


def test_reticencias_separam_trechos_literais_de_uma_lista():
    validar("Reage violentamente com: ... Aminas")
    validar("Reage violentamente com:\n… Metanol")


@pytest.mark.parametrize(
    "citacao",
    [
        "Lave a boca com bastante água.",
        "Reage violentamente com: ... Água oxigenada",
        "...",
    ],
    ids=["inventada", "um-trecho-inexistente", "so-reticencias"],
)
def test_citacao_que_nao_esta_no_texto_continua_invalida(citacao):
    with pytest.raises(EvidenciaInvalida):
        validar(citacao)


def test_evidencia_de_pagina_inexistente_continua_invalida():
    resultado = Pendencia(
        secao="04",
        campo="x",
        motivo="informacao_ausente",
        descricao="d",
        evidencias=[Evidencia(secao="04", pagina=9, texto_evidencia="Contate imediatamente")],
    )
    with pytest.raises(EvidenciaInvalida):
        validar_evidencias(resultado, numero_secao="04", entrada=secao(PAGINA_COM_PALAVRAS_ABERTAS))


class ClienteFalso:
    def __init__(self, resposta: RespostaIncompatibilidadesLLM):
        self.resposta = resposta

    async def responder_estruturado(self, *, modelo, instrucoes, entrada):
        return self.resposta


def item(substancia: str) -> dict:
    return {
        "substancia_reagente": substancia,
        "cas_numero": None,
        "descricao_risco": None,
        "severidade": None,
        "evidencias": [{"secao": "10", "pagina": 1, "texto_evidencia": f"Incompatível com {substancia}."}],
    }


def evidencia_de_ausencia() -> dict:
    return {"secao": "10", "pagina": 1, "texto_evidencia": "Não há materiais incompatíveis."}


def extrair(situacao: str, itens: list[dict], evidencias: list[dict]):
    resposta = RespostaIncompatibilidadesLLM.model_validate(
        {"situacao": situacao, "incompatibilidades": itens, "evidencias": evidencias, "pendencias": []}
    )
    extraida, _ = asyncio.run(
        extrair_incompatibilidades(ClienteFalso(resposta), secao("texto", "10"))
    )
    return extraida


@pytest.mark.parametrize(
    ("situacao_da_ia", "itens", "evidencias", "situacao_esperada"),
    [
        ("nao_especificadas", [item("ácidos")], [], "identificadas"),
        ("ausencia_declarada", [item("ácidos")], [evidencia_de_ausencia()], "identificadas"),
        ("identificadas", [], [], "nao_especificadas"),
        ("ausencia_declarada", [], [], "nao_especificadas"),
        ("identificadas", [item("ácidos")], [], "identificadas"),
        ("ausencia_declarada", [], [evidencia_de_ausencia()], "ausencia_declarada"),
        ("nao_especificadas", [], [], "nao_especificadas"),
    ],
    ids=[
        "itens-com-nao-especificadas",
        "itens-com-ausencia-declarada",
        "identificadas-sem-itens",
        "ausencia-sem-evidencia",
        "coerente-identificadas",
        "coerente-ausencia-declarada",
        "coerente-nao-especificadas",
    ],
)
def test_situacao_da_secao_10_acompanha_o_que_a_ia_devolveu(situacao_da_ia, itens, evidencias, situacao_esperada):
    extraida = extrair(situacao_da_ia, itens, evidencias)

    assert extraida.situacao == situacao_esperada
    assert bool(extraida.incompatibilidades) == (situacao_esperada == "identificadas")


class ClienteEmSequencia:
    """Devolve (ou lança) cada item na ordem das chamadas e conta quantas houve."""

    def __init__(self, *itens):
        self.itens = list(itens)
        self.chamadas = 0

    async def responder_estruturado(self, *, modelo, instrucoes, entrada):
        item_atual = self.itens[min(self.chamadas, len(self.itens) - 1)]
        self.chamadas += 1
        if isinstance(item_atual, Exception):
            raise item_atual
        return item_atual


def resposta_da_secao_10(citacao: str) -> RespostaIncompatibilidadesLLM:
    return RespostaIncompatibilidadesLLM.model_validate(
        {
            "situacao": "identificadas",
            "incompatibilidades": [
                {
                    "substancia_reagente": "ácidos",
                    "cas_numero": None,
                    "descricao_risco": None,
                    "severidade": None,
                    "evidencias": [{"secao": "10", "pagina": 1, "texto_evidencia": citacao}],
                }
            ],
            "evidencias": [],
            "pendencias": [],
        }
    )


def extrair_so_a_secao_10(cliente):
    sem_secao = SecaoEntrada(encontrada=False, paginas=[])
    entrada = ExtracaoEntrada(
        secoes=SecoesEntrada(
            secao_3=sem_secao, secao_4=sem_secao, secao_10=secao("Incompatível com ácidos.", "10")
        )
    )
    return asyncio.run(ExtracaoService(cliente).extrair(entrada))


def test_citacao_inexistente_na_primeira_resposta_ganha_uma_nova_tentativa():
    cliente = ClienteEmSequencia(resposta_da_secao_10("Texto que não existe"), resposta_da_secao_10("Incompatível com ácidos."))

    saida = extrair_so_a_secao_10(cliente)

    assert cliente.chamadas == 2
    assert saida.secoes.incompatibilidades.situacao == "identificadas"


def test_resposta_fora_do_formato_ganha_uma_nova_tentativa():
    cliente = ClienteEmSequencia(ErroLLM("formato"), resposta_da_secao_10("Incompatível com ácidos."))

    saida = extrair_so_a_secao_10(cliente)

    assert cliente.chamadas == 2
    assert saida.secoes.incompatibilidades.encontrada


def test_segunda_falha_segue_para_quem_chamou():
    cliente = ClienteEmSequencia(resposta_da_secao_10("Texto que não existe"))

    with pytest.raises(EvidenciaInvalida):
        extrair_so_a_secao_10(cliente)

    assert cliente.chamadas == 2


def test_falta_de_credito_nao_e_repetida():
    cliente = ClienteEmSequencia(CreditoLLMInsuficiente("sem créditos"))

    with pytest.raises(CreditoLLMInsuficiente):
        extrair_so_a_secao_10(cliente)

    assert cliente.chamadas == 1


from app.extractors.composicao import extrair_composicao  # noqa: E402
from app.extractors.primeiros_socorros import extrair_primeiros_socorros  # noqa: E402
from app.schemas.respostas_llm import RespostaComposicaoLLM, RespostaPrimeirosSocorrosLLM  # noqa: E402


def extrair_primeiros_socorros_com(urgencia, descricao: str, citacao: str):
    resposta = RespostaPrimeirosSocorrosLLM.model_validate(
        {
            "primeiros_socorros": [
                {
                    "rota_exposicao": "olhos",
                    "descricao": descricao,
                    "sintomas": None,
                    "tratamento_especial": None,
                    "atencao_medica_imediata": urgencia,
                    "evidencias": [{"secao": "04", "pagina": 1, "texto_evidencia": citacao}],
                }
            ],
            "orientacoes_gerais": [],
            "notas_ao_medico": [],
            "pendencias": [],
        }
    )
    extraida, _ = asyncio.run(extrair_primeiros_socorros(ClienteFalso(resposta), secao("texto")))
    return extraida.primeiros_socorros[0].atencao_medica_imediata


@pytest.mark.parametrize(
    ("urgencia", "descricao", "citacao", "esperado"),
    [
        (False, "Enxaguar os olhos.", "Se os sintomas persistirem, consulte um médico.", None),
        (False, "Enxaguar os olhos.", "Não é necessário atendimento médico imediato.", False),
        (False, "Lavar com água. Dispensa atendimento médico.", "Lavar com água.", False),
        (True, "Enxaguar os olhos.", "Procure atendimento médico imediato.", True),
        (None, "Enxaguar os olhos.", "Enxaguar os olhos.", None),
    ],
    ids=["false-sem-negacao", "false-com-negacao", "false-com-dispensa", "true-mantido", "null-mantido"],
)
def test_false_em_atencao_medica_imediata_exige_a_negacao_escrita(urgencia, descricao, citacao, esperado):
    assert extrair_primeiros_socorros_com(urgencia, descricao, citacao) is esperado


def extrair_composto(minimo, maximo, citacao: str):
    resposta = RespostaComposicaoLLM.model_validate(
        {
            "compostos": [
                {
                    "nome": "Álcool benzílico",
                    "cas_numero": "100-51-6",
                    "concentracao_min": minimo,
                    "concentracao_max": maximo,
                    "unidade_concentracao": "%",
                    "evidencias": [{"secao": "03", "pagina": 1, "texto_evidencia": citacao}],
                }
            ],
            "pendencias": [],
        }
    )
    return asyncio.run(extrair_composicao(ClienteFalso(resposta), secao("texto", "03")))


def test_concentracao_que_esta_na_citacao_e_mantida():
    composicao, pendencias = extrair_composto(1.5, 1.5, "Álcool benzílico 1,5%")
    composto = composicao.compostos[0]
    assert (composto.concentracao_min, composto.concentracao_max) == (1.5, 1.5)
    assert pendencias == []

    composicao, _ = extrair_composto(2, 2.5, "Hipoclorito 2 – 2,5 NaClO")
    assert (composicao.compostos[0].concentracao_min, composicao.compostos[0].concentracao_max) == (2.0, 2.5)


def test_citacao_sem_numero_nao_desmente_a_concentracao():
    composicao, pendencias = extrair_composto(1.0, 5.0, "Álcool benzílico CAS 100-51-6")

    composto = composicao.compostos[0]
    assert (composto.concentracao_min, composto.concentracao_max) == (1.0, 5.0)
    assert pendencias == []


def test_concentracao_que_difere_da_citacao_e_omitida_com_pendencia():
    composicao, pendencias = extrair_composto(1.0, 5.0, "Álcool benzílico 1,5%")

    composto = composicao.compostos[0]
    assert (composto.concentracao_min, composto.concentracao_max) == (None, None)
    assert sorted(p.campo for p in pendencias) == ["concentracao_max", "concentracao_min"]
    assert all(p.motivo == "dados_contraditorios" for p in pendencias)
