"""Orquestra a extração estruturada das seções 3, 4 e 10."""
import asyncio

from app.clients.llm import LLMClient
from app.extractors.composicao import extrair_composicao
from app.extractors.incompatibilidades import extrair_incompatibilidades
from app.extractors.primeiros_socorros import extrair_primeiros_socorros
from app.schemas.entrada import ExtracaoEntrada, SecaoEntrada
from app.schemas.saida import (
    ComposicaoExtraida,
    ExtracaoSaida,
    IncompatibilidadesExtraidas,
    Pendencia,
    PrimeirosSocorrosExtraidos,
)
from app.validators.documento import validar_documento
from app.validators.extracao import (
    MENSAGEM_PENDENCIA,
    criar_pendencia_informacao_ausente,
    criar_pendencia_secao_nao_localizada,
    validar_evidencias,
    validar_secao_das_pendencias,
)


class ExtracaoService:
    def __init__(self, cliente: LLMClient):
        self._cliente = cliente

    async def extrair(self, entrada: ExtracaoEntrada) -> ExtracaoSaida:
        validar_documento(entrada)
        tarefas = []
        if entrada.secoes.secao_3.encontrada:
            tarefas.append(extrair_composicao(self._cliente, entrada.secoes.secao_3))
        if entrada.secoes.secao_4.encontrada:
            tarefas.append(extrair_primeiros_socorros(self._cliente, entrada.secoes.secao_4))
        if entrada.secoes.secao_10.encontrada:
            tarefas.append(extrair_incompatibilidades(self._cliente, entrada.secoes.secao_10))

        extraidos = await asyncio.gather(*tarefas) if tarefas else []
        por_secao = iter(extraidos)

        if entrada.secoes.secao_3.encontrada:
            composicao, pendencias_03 = next(por_secao)
            self._validar_resultado(composicao, pendencias_03, "03", entrada.secoes.secao_3)
        else:
            composicao = ComposicaoExtraida(encontrada=False, compostos=[])
            pendencias_03 = [criar_pendencia_secao_nao_localizada("03")]
        if not composicao.compostos and not pendencias_03 and composicao.encontrada:
            pendencias_03.append(
                criar_pendencia_informacao_ausente(
                    "03", "composicao", "A seção 3 foi localizada, mas não informa componentes extraíveis."
                )
            )

        if entrada.secoes.secao_4.encontrada:
            primeiros_socorros, pendencias_04 = next(por_secao)
            self._validar_resultado(
                primeiros_socorros, pendencias_04, "04", entrada.secoes.secao_4
            )
        else:
            primeiros_socorros = PrimeirosSocorrosExtraidos(
                encontrada=False,
                primeiros_socorros=[],
                orientacoes_gerais=[],
                notas_ao_medico=[],
            )
            pendencias_04 = [criar_pendencia_secao_nao_localizada("04")]
        if (
            primeiros_socorros.encontrada
            and not primeiros_socorros.primeiros_socorros
            and not primeiros_socorros.orientacoes_gerais
            and not primeiros_socorros.notas_ao_medico
            and not pendencias_04
        ):
            pendencias_04.append(
                criar_pendencia_informacao_ausente(
                    "04", "primeiros_socorros", "A seção 4 foi localizada, mas não informa medidas extraíveis."
                )
            )

        if entrada.secoes.secao_10.encontrada:
            incompatibilidades, pendencias_10 = next(por_secao)
            self._validar_resultado(
                incompatibilidades, pendencias_10, "10", entrada.secoes.secao_10
            )
        else:
            incompatibilidades = IncompatibilidadesExtraidas(
                encontrada=False,
                situacao="secao_nao_localizada",
                incompatibilidades=[],
                evidencias=[],
            )
            pendencias_10 = [criar_pendencia_secao_nao_localizada("10")]
        if (
            incompatibilidades.encontrada
            and incompatibilidades.situacao == "nao_especificadas"
            and not pendencias_10
        ):
            pendencias_10.append(
                Pendencia(
                    secao="10",
                    campo="incompatibilidades",
                    motivo="documento_nao_especifica",
                    descricao="A seção 10 não especifica se há materiais incompatíveis.",
                    evidencias=[],
                )
            )

        pendencias = pendencias_03 + pendencias_04 + pendencias_10
        return ExtracaoSaida(
            status="processado_com_pendencias" if pendencias else "processado",
            mensagem=MENSAGEM_PENDENCIA if pendencias else None,
            secoes={
                "03": composicao,
                "04": primeiros_socorros,
                "10": incompatibilidades,
            },
            pendencias=pendencias,
        )

    @staticmethod
    def _validar_resultado(
        resultado,
        pendencias: list[Pendencia],
        numero_secao: str,
        entrada_secao: SecaoEntrada,
    ) -> None:
        validar_secao_das_pendencias(pendencias, numero_secao)
        validar_evidencias(
            resultado,
            numero_secao=numero_secao,
            entrada=entrada_secao,
        )
        for pendencia in pendencias:
            validar_evidencias(
                pendencia,
                numero_secao=numero_secao,
                entrada=entrada_secao,
            )
