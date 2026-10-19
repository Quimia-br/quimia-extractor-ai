import pytest

from app.core.exceptions import DocumentoNaoFds
from app.pdf.secoes import montar_entrada


@pytest.mark.parametrize(
    "titulo",
    [
        "3. COMPOSIÇÃO E INFORMAÇÕES SOBRE OS INGREDIENTES",
        "SEÇÃO 3: Composição e informações sobre os ingredientes",
        "03 - Composição e informações sobre os ingredientes",
        "3 – COMPOSICAO E INFORMACOES SOBRE OS INGREDIENTES",
    ],
)
def test_reconhece_variacoes_do_titulo_da_secao_3(titulo):
    entrada = montar_entrada([f"{titulo}\nEtanol 64-17-5 70%\n4. Medidas de primeiros-socorros\nLavar."])

    assert entrada.secoes.secao_3.paginas[0].texto.endswith("Etanol 64-17-5 70%")
    assert entrada.secoes.secao_4.paginas[0].texto.endswith("Lavar.")
    assert not entrada.secoes.secao_10.encontrada


def test_titulo_quebrado_em_duas_linhas():
    entrada = montar_entrada(["10.\nESTABILIDADE E REATIVIDADE\nEstável.\n11. Informações toxicológicas\nDL50."])

    assert entrada.secoes.secao_10.paginas[0].texto == "10.\nESTABILIDADE E REATIVIDADE\nEstável."


def test_lista_numerada_dentro_da_secao_nao_encerra_a_secao():
    entrada = montar_entrada(
        ["4. Primeiros socorros\n1. Remova a vítima.\n3. Lave a pele.\n5. Medidas de combate a incêndio\nEspuma."]
    )

    assert "3. Lave a pele." in entrada.secoes.secao_4.paginas[0].texto


def test_sumario_e_ignorado_em_favor_do_conteudo():
    sumario = "Sumário\n3. Composição\n4. Primeiros socorros\n10. Estabilidade e reatividade\n"
    conteudo = "3. Composição\nEtanol 64-17-5 entre 65 e 70 por cento em massa.\n4. Primeiros socorros\nLavar."

    entrada = montar_entrada([sumario, conteudo])

    assert [pagina.numero for pagina in entrada.secoes.secao_3.paginas] == [2]
    assert [pagina.numero for pagina in entrada.secoes.secao_4.paginas] == [2]
    assert not entrada.secoes.secao_10.encontrada


def test_documento_sem_secoes_da_norma_e_recusado():
    with pytest.raises(DocumentoNaoFds):
        montar_entrada(["Contrato de prestação de serviços.\n3. Pagamento em 30 dias."])
