"""Validador que espelha a tabela de regras da resposta 200 combinada com a quimia-api.

Mantido de forma independente do código de produção: se a sanitização deixar
passar algo, este validador acusa.
"""
import json
import math

STATUS = {"processado", "processado_com_pendencias"}
SEVERIDADES = {"baixa", "media", "alta", "critica"}
TIPOS_RESIDUO = {"quimico", "biologico", "comum", "reciclavel", "outro"}


def _rejeitar_constante(nome: str):
    raise ValueError(f"constante não JSON: {nome}")


def _textos_com_nul(valor, caminho: str = "$") -> list[str]:
    if isinstance(valor, str):
        return [caminho] if "\x00" in valor else []
    if isinstance(valor, dict):
        erros = []
        for chave, item in valor.items():
            if "\x00" in chave:
                erros.append(f"{caminho}.<chave>")
            erros.extend(_textos_com_nul(item, f"{caminho}.{chave}"))
        return erros
    if isinstance(valor, list):
        return [erro for i, item in enumerate(valor) for erro in _textos_com_nul(item, f"{caminho}[{i}]")]
    return []


def _texto_ate(valor, limite: int) -> bool:
    return isinstance(valor, str) and len(valor) <= limite


def _concentracao_ok(valor) -> bool:
    if valor is None:
        return True
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return False
    return math.isfinite(valor) and 0 <= round(valor, 2) <= 999.99


def _lista_de_objetos(valor) -> bool:
    return isinstance(valor, list) and all(isinstance(item, dict) for item in valor)


def validar_contrato(corpo: str) -> list[str]:
    """Devolve a lista de violações; vazia quando o corpo cumpre o contrato."""
    try:
        dados = json.loads(corpo, parse_constant=_rejeitar_constante)
    except ValueError as erro:
        return [f"raiz: JSON inválido ou com conteúdo após o objeto ({erro})"]
    if not isinstance(dados, dict):
        return ["raiz: não é um objeto JSON"]

    erros = [f"{caminho}: contém NUL" for caminho in _textos_com_nul(dados)]
    if dados.get("status") not in STATUS:
        erros.append("status: fora da lista")

    secoes = dados.get("secoes")
    if not isinstance(secoes, dict):
        return erros + ["secoes: não é objeto"]

    compostos = secoes.get("03", {}).get("compostos") if isinstance(secoes.get("03"), dict) else None
    if not _lista_de_objetos(compostos):
        erros.append("secoes.03.compostos: ausente ou não é lista de objetos")
        compostos = []
    for i, composto in enumerate(compostos):
        prefixo = f"compostos[{i}]"
        nome = composto.get("nome")
        if not (_texto_ate(nome, 255) and nome):
            erros.append(f"{prefixo}.nome: vazio ou acima de 255")
        cas = composto.get("cas_numero")
        if cas is not None and not _texto_ate(cas, 20):
            erros.append(f"{prefixo}.cas_numero: acima de 20 ou não é texto")
        minimo, maximo = composto.get("concentracao_min"), composto.get("concentracao_max")
        for campo, valor in (("concentracao_min", minimo), ("concentracao_max", maximo)):
            if not _concentracao_ok(valor):
                erros.append(f"{prefixo}.{campo}: fora de NUMERIC(5,2)")
        if _concentracao_ok(minimo) and _concentracao_ok(maximo) and None not in (minimo, maximo) and minimo > maximo:
            erros.append(f"{prefixo}: concentracao_min > concentracao_max")

    secao_10 = secoes.get("10")
    if isinstance(secao_10, dict) and "incompatibilidades" in secao_10:
        itens = secao_10["incompatibilidades"]
        if not _lista_de_objetos(itens):
            erros.append("secoes.10.incompatibilidades: não é lista de objetos")
            itens = []
        for i, item in enumerate(itens):
            reagente = item.get("substancia_reagente")
            if reagente is not None and not _texto_ate(reagente, 255):
                erros.append(f"incompatibilidades[{i}].substancia_reagente: acima de 255")
            if item.get("severidade") not in SEVERIDADES | {None}:
                erros.append(f"incompatibilidades[{i}].severidade: fora da lista")

    secao_13 = secoes.get("13")
    if isinstance(secao_13, dict) and "descartes" in secao_13:
        itens = secao_13["descartes"]
        if not _lista_de_objetos(itens):
            erros.append("secoes.13.descartes: não é lista de objetos")
            itens = []
        for i, item in enumerate(itens):
            instrucao = item.get("instrucao_descarte")
            if instrucao is not None and not isinstance(instrucao, str):
                erros.append(f"descartes[{i}].instrucao_descarte: não é texto")
            if item.get("tipo_residuo") not in TIPOS_RESIDUO | {None}:
                erros.append(f"descartes[{i}].tipo_residuo: fora da lista")
    return erros
