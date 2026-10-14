INSTRUCOES_COMPOSICAO = """SEÇÃO 03 — COMPOSIÇÃO

Extraia cada substância ou componente citado. Preserve o nome como aparece na
ficha. Preencha cas_numero apenas quando o CAS estiver explícito e válido;
preencha concentracao_min, concentracao_max e unidade_concentracao somente na
medida em que a faixa puder ser representada sem assumir limites. Os valores de
concentração devem ser numéricos. Use null para cada campo que não puder ser
determinado com segurança e crie uma pendência para informação relevante que
está ausente, ambígua ou contraditória.

Cada item de compostos precisa de evidencias. A evidência deve sustentar o nome
e os valores preenchidos; não use uma citação sobre outro componente. Se não
houver nenhum componente extraível, devolva compostos como lista vazia e
descreva a informação faltante em pendencias quando for relevante.

EXEMPLO
Entrada da seção:
[{"pagina": 2, "texto": "Etanol (CAS 64-17-5): 5 a 10%. Mistura proprietária sem faixa de concentração informada."}]

Resposta esperada para este exemplo:
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
          "texto_evidencia": "Etanol (CAS 64-17-5): 5 a 10%."
        }
      ]
    },
    {
      "nome": "Mistura proprietária",
      "cas_numero": null,
      "concentracao_min": null,
      "concentracao_max": null,
      "unidade_concentracao": null,
      "evidencias": [
        {
          "secao": "03",
          "pagina": 2,
          "texto_evidencia": "Mistura proprietária sem faixa de concentração informada."
        }
      ]
    }
  ],
  "pendencias": [
    {
      "secao": "03",
      "campo": "concentracao",
      "motivo": "informacao_ausente",
      "descricao": "A ficha identifica a mistura proprietária, mas não informa sua faixa de concentração.",
      "evidencias": []
    }
  ]
}"""