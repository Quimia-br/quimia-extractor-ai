"""Saneia o JSON devolvido à quimia-api para que o trigger do PostgreSQL o aceite.

A API grava a resposta em `fds.raw_json` (jsonb) e um trigger materializa as
tabelas sem tratar exceções. Valores fora dos limites das colunas são cortados
ou anulados aqui; cada valor anulado vira uma pendência para revisão humana.
"""
import copy
import math

from app.validators.extracao import MENSAGEM_PENDENCIA

MAX_NOME_COMPOSTO = 255
MAX_CAS = 20
MAX_SUBSTANCIA_REAGENTE = 255
# NUMERIC(5,2): até 999.99, com duas casas decimais.
CONCENTRACAO_MINIMA = 0.0
CONCENTRACAO_MAXIMA = 999.99
CASAS_CONCENTRACAO = 2

STATUS_VALIDOS = {"processado", "processado_com_pendencias"}
SEVERIDADES = {"baixa", "media", "alta", "critica"}
TIPOS_RESIDUO = {"quimico", "biologico", "comum", "reciclavel", "outro"}


def sanitizar_saida(dados: dict) -> dict:
    """Devolve uma cópia de `dados` dentro das regras do contrato com a API."""
    saida = _limpar_textos(copy.deepcopy(dados))
    secoes = saida.get("secoes")
    if not isinstance(secoes, dict):
        secoes = {}
        saida["secoes"] = secoes

    novas_pendencias: list[dict] = []
    _sanitizar_composicao(secoes, novas_pendencias)
    _sanitizar_incompatibilidades(secoes, novas_pendencias)
    _sanitizar_descartes(secoes)
    _ajustar_status(saida, novas_pendencias)
    return saida


def _limpar_textos(valor):
    """Troca NUL por espaço e remove surrogates isolados, que o jsonb recusa."""
    if isinstance(valor, str):
        return valor.replace("\x00", " ").encode("utf-8", "replace").decode("utf-8")
    if isinstance(valor, dict):
        return {_limpar_textos(chave): _limpar_textos(item) for chave, item in valor.items()}
    if isinstance(valor, list):
        return [_limpar_textos(item) for item in valor]
    return valor


def _pendencia(secao: str, campo: str, motivo: str, descricao: str) -> dict:
    return {
        "secao": secao,
        "campo": campo,
        "motivo": motivo,
        "descricao": descricao,
        "evidencias": [],
    }


def _objetos(valor) -> list[dict]:
    if not isinstance(valor, list):
        return []
    return [item for item in valor if isinstance(item, dict)]


def _texto_limitado(valor, limite: int) -> str | None:
    if not isinstance(valor, str):
        return None
    return valor[:limite]


def _concentracao_valida(valor) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    if not math.isfinite(valor):
        return None
    arredondado = round(float(valor), CASAS_CONCENTRACAO)
    if not CONCENTRACAO_MINIMA <= arredondado <= CONCENTRACAO_MAXIMA:
        return None
    return arredondado


def _sanitizar_composicao(secoes: dict, pendencias: list[dict]) -> None:
    secao = secoes.get("03")
    if not isinstance(secao, dict):
        secao = {"encontrada": False, "compostos": []}
        secoes["03"] = secao

    compostos = []
    for composto in _objetos(secao.get("compostos")):
        nome = composto.get("nome")
        nome = nome.strip() if isinstance(nome, str) else ""
        if not nome:
            pendencias.append(
                _pendencia("03", "nome", "informacao_ausente", "Um componente sem nome foi descartado.")
            )
            continue
        composto["nome"] = nome[:MAX_NOME_COMPOSTO].rstrip()
        _sanitizar_cas(composto, pendencias)
        _sanitizar_concentracoes(composto, pendencias)
        compostos.append(composto)
    secao["compostos"] = compostos


def _sanitizar_cas(composto: dict, pendencias: list[dict]) -> None:
    cas = composto.get("cas_numero")
    if cas is None:
        return
    # Cortar um CAS produziria um número inexistente; anula e registra.
    if not isinstance(cas, str) or len(cas) > MAX_CAS:
        composto["cas_numero"] = None
        pendencias.append(
            _pendencia(
                "03",
                "cas_numero",
                "termo_ambiguo",
                f"O CAS de {composto['nome']} não pôde ser representado e foi omitido.",
            )
        )


def _sanitizar_concentracoes(composto: dict, pendencias: list[dict]) -> None:
    for campo in ("concentracao_min", "concentracao_max"):
        original = composto.get(campo)
        valido = _concentracao_valida(original)
        composto[campo] = valido
        if original is not None and valido is None:
            pendencias.append(
                _pendencia(
                    "03",
                    campo,
                    "dados_contraditorios",
                    f"A concentração de {composto['nome']} está fora da faixa de 0 a 999.99 e foi omitida.",
                )
            )

    minimo, maximo = composto["concentracao_min"], composto["concentracao_max"]
    if minimo is not None and maximo is not None and minimo > maximo:
        composto["concentracao_min"] = None
        composto["concentracao_max"] = None
        pendencias.append(
            _pendencia(
                "03",
                "concentracao",
                "dados_contraditorios",
                f"A concentração mínima de {composto['nome']} supera a máxima; a faixa foi omitida.",
            )
        )


def _sanitizar_incompatibilidades(secoes: dict, pendencias: list[dict]) -> None:
    secao = secoes.get("10")
    if not isinstance(secao, dict) or "incompatibilidades" not in secao:
        return

    incompatibilidades = _objetos(secao.get("incompatibilidades"))
    for item in incompatibilidades:
        item["substancia_reagente"] = _texto_limitado(
            item.get("substancia_reagente"), MAX_SUBSTANCIA_REAGENTE
        )
        severidade = item.get("severidade")
        if severidade is not None and severidade not in SEVERIDADES:
            item["severidade"] = None
            pendencias.append(
                _pendencia(
                    "10",
                    "severidade",
                    "termo_ambiguo",
                    "Uma severidade fora da escala baixa, media, alta ou critica foi omitida.",
                )
            )
    secao["incompatibilidades"] = incompatibilidades


def _sanitizar_descartes(secoes: dict) -> None:
    secao = secoes.get("13")
    if not isinstance(secao, dict) or "descartes" not in secao:
        return

    descartes = _objetos(secao.get("descartes"))
    for item in descartes:
        instrucao = item.get("instrucao_descarte")
        item["instrucao_descarte"] = instrucao if isinstance(instrucao, str) else None
        if item.get("tipo_residuo") not in TIPOS_RESIDUO:
            item["tipo_residuo"] = None
    secao["descartes"] = descartes


def _ajustar_status(saida: dict, novas_pendencias: list[dict]) -> None:
    pendencias = saida.get("pendencias")
    if not isinstance(pendencias, list):
        pendencias = []
    pendencias.extend(novas_pendencias)
    saida["pendencias"] = pendencias

    if pendencias:
        saida["status"] = "processado_com_pendencias"
        if not isinstance(saida.get("mensagem"), str) or not saida["mensagem"].strip():
            saida["mensagem"] = MENSAGEM_PENDENCIA
    elif saida.get("status") not in STATUS_VALIDOS:
        saida["status"] = "processado"
