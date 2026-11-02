"""Rota autenticada que recebe o PDF da FDS e devolve o ExtracaoSaida saneado."""
import asyncio
import hmac
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app.clients.llm import LLMClient
from app.core.config import carregar_config
from app.core.exceptions import (
    ArquivoNaoPdf,
    ConfiguracaoLLMInvalida,
    DocumentoNaoFds,
    EntradaInvalida,
    ErroLLM,
    EvidenciaInvalida,
    PdfSemTexto,
)
from app.pdf.secoes import montar_entrada
from app.pdf.texto import extrair_paginas, possui_assinatura_pdf
from app.services.extracao_service import ExtracaoService
from app.services.extracoes_assincronas import CapacidadeEsgotada, FalhaDaExtracao, RegistroDeExtracoes
from app.validators.saida_http import sanitizar_saida

LIMITE_ARQUIVO_BYTES = 10 * 1024 * 1024
# Cabeçalhos e delimitadores do multipart somam alguns KB além do arquivo.
FOLGA_MULTIPART_BYTES = 64 * 1024
LIMITE_CORPO_BYTES = LIMITE_ARQUIVO_BYTES + FOLGA_MULTIPART_BYTES
# A quimia-api espera no máximo 60 s; a margem cobre rede e serialização.
TIMEOUT_PADRAO_SEGUNDOS = 55.0
CAMPO_ARQUIVO = "arquivo"

logger = logging.getLogger(__name__)
router = APIRouter()


class _FalhaRequisicao(Exception):
    def __init__(self, status: int, detalhe: str):
        super().__init__(detalhe)
        self.status = status
        self.detalhe = detalhe


def _erro(status: int, detalhe: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detalhe})


def verificar_token(request: Request) -> None:
    esperado = carregar_config().extrator_api_token
    if not esperado:
        logger.error("EXTRATOR_API_TOKEN não configurado; extrações recusadas.")
        raise HTTPException(503, "Serviço sem token configurado.")
    esquema, _, fornecido = request.headers.get("authorization", "").partition(" ")
    valido = esquema.lower() == "bearer" and hmac.compare_digest(
        fornecido.strip().encode("utf-8"), esperado.encode("utf-8")
    )
    if not valido:
        raise HTTPException(401, "Token ausente ou inválido.", headers={"WWW-Authenticate": "Bearer"})


def obter_cliente_llm(request: Request) -> LLMClient:
    """Cria o cliente na primeira extração; /health não depende das chaves da IA."""
    cliente = getattr(request.app.state, "cliente_llm", None)
    if cliente is None:
        try:
            cliente = LLMClient()
        except ConfiguracaoLLMInvalida as erro:
            logger.error("Cliente da IA não configurado: %s", erro)
            raise HTTPException(503, "Serviço de IA não configurado.") from erro
        request.app.state.cliente_llm = cliente
    return cliente


def obter_registro(request: Request) -> RegistroDeExtracoes:
    registro = getattr(request.app.state, "registro_extracoes", None)
    if registro is None:
        registro = RegistroDeExtracoes()
        request.app.state.registro_extracoes = registro
    return registro


FALHAS_DA_EXTRACAO = (
    ArquivoNaoPdf,
    DocumentoNaoFds,
    PdfSemTexto,
    EntradaInvalida,
    TimeoutError,
    ErroLLM,
    EvidenciaInvalida,
    ValidationError,
)


def _status_da_falha(erro: Exception) -> tuple[int, str]:
    """Status HTTP e mensagem de uma falha da extração; vale para a rota síncrona e para a assíncrona."""
    if isinstance(erro, (ArquivoNaoPdf, DocumentoNaoFds)):
        return 400, str(erro)
    if isinstance(erro, (PdfSemTexto, EntradaInvalida)):
        return 422, str(erro)
    if isinstance(erro, TimeoutError):
        logger.warning("Extração excedeu o prazo.")
        return 504, "A extração excedeu o tempo limite."
    logger.warning("Resposta da IA rejeitada: %s", type(erro).__name__)
    return 502, "A IA não devolveu uma extração válida."


@router.post("/extracoes", dependencies=[Depends(verificar_token)])
async def criar_extracao(
    request: Request,
    cliente: LLMClient = Depends(obter_cliente_llm),
) -> JSONResponse:
    try:
        conteudo = await _ler_pdf_enviado(request)
        saida = await _extrair_com_prazo(cliente, conteudo)
    except _FalhaRequisicao as falha:
        return _erro(falha.status, falha.detalhe)
    except FALHAS_DA_EXTRACAO as erro:
        return _erro(*_status_da_falha(erro))
    return JSONResponse(content=sanitizar_saida(saida))


@router.post("/extracoes/assincronas", status_code=202, dependencies=[Depends(verificar_token)])
async def criar_extracao_assincrona(
    request: Request,
    cliente: LLMClient = Depends(obter_cliente_llm),
    registro: RegistroDeExtracoes = Depends(obter_registro),
) -> JSONResponse:
    """Mesma entrada de `POST /extracoes`; devolve o id na hora e a extração roda em segundo plano."""
    try:
        conteudo = await _ler_pdf_enviado(request)
    except _FalhaRequisicao as falha:
        return _erro(falha.status, falha.detalhe)

    async def trabalho() -> dict:
        try:
            return sanitizar_saida(await _extrair_com_prazo(cliente, conteudo))
        except FALHAS_DA_EXTRACAO as erro:
            raise FalhaDaExtracao(*_status_da_falha(erro)) from erro

    try:
        extracao = registro.iniciar(trabalho)
    except CapacidadeEsgotada:
        return JSONResponse(
            status_code=429,
            content={"detail": "Há extrações demais em andamento. Tente de novo em instantes."},
            headers={"Retry-After": "10"},
        )
    return JSONResponse(
        status_code=202,
        content=extracao.como_resposta(),
        headers={"Location": f"/extracoes/assincronas/{extracao.id}"},
    )


@router.get("/extracoes/assincronas/{id_extracao}", dependencies=[Depends(verificar_token)])
async def consultar_extracao_assincrona(
    id_extracao: str,
    registro: RegistroDeExtracoes = Depends(obter_registro),
) -> JSONResponse:
    extracao = registro.consultar(id_extracao)
    if extracao is None:
        return _erro(404, "Extração não encontrada ou expirada.")
    return JSONResponse(content=extracao.como_resposta())


async def _ler_pdf_enviado(request: Request) -> bytes:
    corpo = await _ler_corpo_limitado(request)

    async def reenviar_corpo() -> dict:
        return {"type": "http.request", "body": corpo, "more_body": False}

    formulario = await Request(request.scope, reenviar_corpo).form(max_files=1, max_fields=10)
    try:
        arquivo = formulario.get(CAMPO_ARQUIVO)
        if not isinstance(arquivo, UploadFile):
            raise _FalhaRequisicao(400, f"Envie o PDF no campo '{CAMPO_ARQUIVO}'.")
        conteudo = await arquivo.read(LIMITE_ARQUIVO_BYTES + 1)
    finally:
        await formulario.close()

    if len(conteudo) > LIMITE_ARQUIVO_BYTES:
        raise _FalhaRequisicao(413, "O arquivo excede 10 MB.")
    if not possui_assinatura_pdf(conteudo):
        raise _FalhaRequisicao(400, "O arquivo enviado não é um PDF.")
    return conteudo


async def _ler_corpo_limitado(request: Request) -> bytes:
    """Recusa pelo Content-Length e, sem ele, interrompe a leitura ao passar do limite."""
    declarado = request.headers.get("content-length")
    if declarado is not None and declarado.isdigit() and int(declarado) > LIMITE_CORPO_BYTES:
        raise _FalhaRequisicao(413, "O arquivo excede 10 MB.")

    corpo = bytearray()
    async for parte in request.stream():
        corpo.extend(parte)
        if len(corpo) > LIMITE_CORPO_BYTES:
            raise _FalhaRequisicao(413, "O arquivo excede 10 MB.")
    return bytes(corpo)


async def _extrair_com_prazo(cliente: LLMClient, conteudo: bytes) -> dict:
    prazo = carregar_config().extrator_timeout_seconds or TIMEOUT_PADRAO_SEGUNDOS
    async with asyncio.timeout(prazo):
        paginas = await run_in_threadpool(extrair_paginas, conteudo)
        entrada = montar_entrada(paginas)
        saida = await ExtracaoService(cliente).extrair(entrada)
    return saida.model_dump(mode="json", by_alias=True)
