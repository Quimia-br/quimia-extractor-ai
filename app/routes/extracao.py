"""API de extração e página de teste, acessíveis localmente por padrão."""
import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError

from app.clients.llm import LLMClient
from app.core.exceptions import ConfiguracaoLLMInvalida, CreditoLLMInsuficiente, EntradaInvalida, ErroLLM, EvidenciaInvalida
from app.schemas.entrada import ExtracaoEntrada
from app.schemas.erro import ErroResposta
from app.schemas.saida import ExtracaoSaida
from app.services.extracao_service import ExtracaoService

router = APIRouter()
logger = logging.getLogger(__name__)
PAGINA_TESTE = Path(__file__).resolve().parents[1] / "static" / "teste.html"


def exigir_acesso_local(request: Request) -> None:
    """Evita publicar chamadas pagas antes de existir autenticação da API."""
    if os.getenv("EXTRACTION_ALLOW_REMOTE", "false").lower() == "true":
        return
    host = request.client.host if request.client else ""
    destino = request.url.hostname
    if host not in {"127.0.0.1", "::1", "testclient"} or destino not in {"127.0.0.1", "localhost", "::1", "testserver"}:
        raise HTTPException(status_code=403, detail="Extração disponível apenas localmente.")


def resposta_erro(status_code: int, tipo: str, mensagem: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"erro": {"tipo": tipo, "mensagem": mensagem, "detalhes": []}})


@router.get("/teste", include_in_schema=False, dependencies=[Depends(exigir_acesso_local)])
async def pagina_teste() -> FileResponse:
    return FileResponse(PAGINA_TESTE, media_type="text/html; charset=utf-8")


@router.post(
    "/api/extracoes",
    response_model=ExtracaoSaida,
    response_model_by_alias=True,
    responses={codigo: {"model": ErroResposta} for codigo in (403, 422, 500, 502, 503)},
    dependencies=[Depends(exigir_acesso_local)],
)
async def extrair(entrada: ExtracaoEntrada) -> ExtracaoSaida | JSONResponse:
    try:
        cliente = LLMClient()
        try:
            return await ExtracaoService(cliente).extrair(entrada)
        finally:
            await cliente.fechar()
    except EntradaInvalida as erro:
        return resposta_erro(422, "validacao", str(erro))
    except ConfiguracaoLLMInvalida as erro:
        return resposta_erro(503, "configuracao", str(erro))
    except CreditoLLMInsuficiente as erro:
        return resposta_erro(503, "configuracao", str(erro))
    except ErroLLM as erro:
        logger.warning("Falha do provedor de IA na extração: %s", erro)
        return resposta_erro(502, "processamento", str(erro))
    except EvidenciaInvalida:
        logger.exception("Evidência inválida produzida durante a extração")
        return resposta_erro(502, "processamento", "A extração gerou evidências incompatíveis com o documento.")
    except ValidationError:
        logger.exception("Resposta estruturada inválida durante a extração")
        return resposta_erro(502, "processamento", "A extração gerou uma resposta fora do contrato.")
    except Exception:
        logger.exception("Falha inesperada durante a extração")
        return resposta_erro(500, "processamento", "Falha inesperada ao processar a FDS.")
