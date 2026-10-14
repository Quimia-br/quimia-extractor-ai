INSTRUCOES_INCOMPATIBILIDADES = """SEÇÃO 10 — ESTABILIDADE E REATIVIDADE

Escolha situacao de acordo com o que está escrito:
- identificadas: a ficha cita pelo menos um material, substância ou condição
  incompatível; extraia cada item em incompatibilidades.
- ausencia_declarada: a ficha afirma explicitamente que não há materiais
  incompatíveis; mantenha incompatibilidades vazio e cite a declaração em
  evidencias no nível da resposta.
- nao_especificadas: a ficha não informa se há incompatibilidades; mantenha
  incompatibilidades e evidencias no nível da resposta vazios e crie uma
  pendência com motivo documento_nao_especifica.

Não confunda ausência de menção com uma declaração de ausência. Para cada item,
preencha substancia_reagente com o material ou condição citada, cas_numero quando
estiver explícito, descricao_risco quando o risco estiver descrito e severidade
somente se a ficha indicar diretamente um nível compatível com baixa, media,
alta ou critica. Palavras como “forte” ou “violenta” descrevem o texto, mas não
autorizam inferir uma severidade. Cada item precisa de evidencias próprias.

EXEMPLO — INCOMPATIBILIDADE IDENTIFICADA
Entrada da seção:
[{"pagina": 8, "texto": "Incompatível com agentes oxidantes fortes. O contato pode provocar reação violenta."}]

Resposta esperada para este exemplo:
{
  "situacao": "identificadas",
  "incompatibilidades": [
    {
      "substancia_reagente": "Agentes oxidantes fortes",
      "cas_numero": null,
      "descricao_risco": "O contato pode provocar reação violenta.",
      "severidade": null,
      "evidencias": [
        {
          "secao": "10",
          "pagina": 8,
          "texto_evidencia": "Incompatível com agentes oxidantes fortes. O contato pode provocar reação violenta."
        }
      ]
    }
  ],
  "evidencias": [],
  "pendencias": []
}

EXEMPLO — AUSÊNCIA DECLARADA
Se a entrada disser “Não há materiais incompatíveis conhecidos.”, responda:
{
  "situacao": "ausencia_declarada",
  "incompatibilidades": [],
  "evidencias": [
    {
      "secao": "10",
      "pagina": 8,
      "texto_evidencia": "Não há materiais incompatíveis conhecidos."
    }
  ],
  "pendencias": []
}

EXEMPLO — NÃO ESPECIFICADO
Se a seção não mencionar incompatibilidades, use situacao nao_especificadas,
listas de incompatibilidades e evidencias vazias, e uma pendência como:
{
  "situacao": "nao_especificadas",
  "incompatibilidades": [],
  "evidencias": [],
  "pendencias": [
    {
      "secao": "10",
      "campo": "incompatibilidades",
      "motivo": "documento_nao_especifica",
      "descricao": "A seção 10 não especifica se há materiais incompatíveis.",
      "evidencias": []
    }
  ]
}"""
