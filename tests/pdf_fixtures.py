"""Gera PDFs mínimos em memória para os testes, sem dependências extras."""

# Texto de uma FDS de álcool etílico 70% no formato da ABNT NBR 14725, com a
# seção 3 atravessando a quebra entre as páginas 1 e 2.
FDS_ALCOOL_70 = [
    [
        "FICHA DE INFORMAÇÕES DE SEGURANÇA DE PRODUTOS QUÍMICOS",
        "Álcool Etílico Hidratado 70% INPM - Revisão 03/2025",
        "1. IDENTIFICAÇÃO",
        "Nome do produto: Álcool Etílico Hidratado 70% INPM",
        "Uso recomendado: Desinfetante de superfícies.",
        "2. IDENTIFICAÇÃO DE PERIGOS",
        "Líquidos inflamáveis - Categoria 2.",
        "Lesões oculares graves/irritação ocular - Categoria 2A.",
        "3. COMPOSIÇÃO E INFORMAÇÕES SOBRE OS INGREDIENTES",
        "Tipo de produto: Mistura.",
        "Etanol CAS 64-17-5 Concentração: 65 - 70%",
    ],
    [
        "Água CAS 7732-18-5 Concentração: 30 - 35%",
        "4. MEDIDAS DE PRIMEIROS-SOCORROS",
        "Inalação: Remova a vítima para local ventilado. Procure atendimento médico.",
        "Contato com a pele: Lave com água em abundância.",
        "Contato com os olhos: Enxágue cuidadosamente com água durante vários minutos.",
        "Ingestão: Não induza o vômito. Consulte um médico.",
        "5. MEDIDAS DE COMBATE A INCÊNDIO",
        "Meios de extinção apropriados: Pó químico, espuma resistente a álcool, CO2.",
    ],
    [
        "9. PROPRIEDADES FÍSICAS E QUÍMICAS",
        "Ponto de fulgor: 17 °C",
        "10. ESTABILIDADE E REATIVIDADE",
        "Estabilidade química: Estável em condições normais.",
        "Materiais incompatíveis: Agentes oxidantes fortes, ácidos e metais alcalinos.",
        "11. INFORMAÇÕES TOXICOLÓGICAS",
        "Toxicidade aguda: DL50 oral (rato): 7060 mg/kg.",
    ],
]

RELATORIO_SEM_SECOES = [
    [
        "Relatório trimestral de vendas",
        "As vendas cresceram em todas as regiões no período analisado.",
        "Próximos passos: ampliar a equipe comercial.",
    ]
]


def _escapar(linha: str) -> bytes:
    bruto = linha.encode("cp1252")
    return bruto.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _stream(conteudo: bytes, extra: bytes = b"") -> bytes:
    return b"<< /Length %d%s >>\nstream\n" % (len(conteudo), extra) + conteudo + b"\nendstream"


def _montar(objetos: list[bytes]) -> bytes:
    saida = bytearray(b"%PDF-1.4\n")
    deslocamentos = []
    for numero, corpo in enumerate(objetos, start=1):
        deslocamentos.append(len(saida))
        saida += b"%d 0 obj\n" % numero + corpo + b"\nendobj\n"
    inicio_xref = len(saida)
    saida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    for deslocamento in deslocamentos:
        saida += b"%010d 00000 n \n" % deslocamento
    saida += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objetos) + 1,
        inicio_xref,
    )
    return bytes(saida)


def gerar_pdf_texto(paginas: list[list[str]]) -> bytes:
    """PDF com uma linha de texto por instrução, em Helvetica/WinAnsi."""
    objetos = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    referencias = []
    for linhas in paginas:
        comandos = b"BT /F1 10 Tf 12 TL 50 800 Td\n" + b"".join(
            b"(" + _escapar(linha) + b") Tj T*\n" for linha in linhas
        ) + b"ET"
        objetos.append(_stream(comandos))
        conteudo = len(objetos)
        objetos.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % conteudo
        )
        referencias.append(len(objetos))
    objetos[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objetos[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
        b" ".join(b"%d 0 R" % ref for ref in referencias),
        len(referencias),
    )
    return _montar(objetos)


def gerar_pdf_imagem() -> bytes:
    """PDF de uma página contendo apenas uma imagem, como um documento escaneado."""
    pixels = bytes([128] * 4)
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /XObject << /Im1 4 0 R >> >> /Contents 5 0 R >>",
        _stream(pixels, b" /Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceGray /BitsPerComponent 8"),
        _stream(b"q 400 0 0 400 100 300 cm /Im1 Do Q"),
    ]
    return _montar(objetos)
