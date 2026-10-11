INSTRUCOES_PRIMEIROS_SOCORROS = """SEÇÃO 04 — MEDIDAS DE PRIMEIROS SOCORROS

Extraia as orientações por rota de exposição: inalacao, pele, olhos ou ingestao.
Agrupe em um único registro todas as informações da mesma rota. Use descricao
para a ação de primeiros socorros; sintomas para efeitos mencionados;
tratamento_especial para tratamento específico; e atencao_medica_imediata para
indicar atendimento imediato.

Preencha atencao_medica_imediata com true somente quando a ficha pedir ou indicar
atendimento imediato; use false somente quando disser explicitamente que não é
necessário. Use null quando não houver indicação explícita. Não transforme uma
recomendação genérica de procurar um médico em urgência imediata.

Coloque orientações não vinculadas a uma rota em orientacoes_gerais e instruções
dirigidas ao profissional de saúde em notas_ao_medico. Cada registro precisa de
evidencias que sustentem seu conteúdo. Se não houver orientação extraível, use
listas vazias; não invente tratamentos.

EXEMPLO
Entrada da seção:
[{"pagina": 3, "texto": "INALAÇÃO: Remova a pessoa para local arejado. Pode causar tontura. Procure atendimento médico imediato."}]

Resposta esperada para este exemplo:
{
  "primeiros_socorros": [
    {
      "rota_exposicao": "inalacao",
      "descricao": "Remova a pessoa para local arejado.",
      "sintomas": "Pode causar tontura.",
      "tratamento_especial": null,
      "atencao_medica_imediata": true,
      "evidencias": [
        {
          "secao": "04",
          "pagina": 3,
          "texto_evidencia": "INALAÇÃO: Remova a pessoa para local arejado. Pode causar tontura. Procure atendimento médico imediato."
        }
      ]
    }
  ],
  "orientacoes_gerais": [],
  "notas_ao_medico": [],
  "pendencias": []
}"""
