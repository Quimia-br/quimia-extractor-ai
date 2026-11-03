"""Extrações em segundo plano.

O host da Discloud corta a resposta de uma requisição após cerca de 30 s e entrega uma página HTML com status 200.
Uma extração real de FDS leva de 9 s a mais de 30 s, então a rota assíncrona devolve um id na hora e o chamador
consulta o resultado. Os registros ficam em memória (um único processo uvicorn) e expiram; um reinício perde as
extrações em andamento, e o chamador refaz o envio.
"""
import asyncio
import logging
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

VALIDADE_SEGUNDOS = 900.0
LIMITE_EM_ANDAMENTO = 6

PROCESSANDO = "processando"
CONCLUIDA = "concluida"
FALHOU = "falhou"


class CapacidadeEsgotada(Exception):
    """Já há extrações demais em andamento para aceitar outra."""


class FalhaDaExtracao(Exception):
    """Falha prevista da extração, com o status HTTP que a rota síncrona devolveria."""

    def __init__(self, status: int, detalhe: str):
        super().__init__(detalhe)
        self.status = status
        self.detalhe = detalhe


@dataclass
class Extracao:
    id: str
    estado: str = PROCESSANDO
    resultado: dict | None = None
    status_http: int | None = None
    detalhe: str | None = None
    finalizada_em: float | None = field(default=None, repr=False)

    def como_resposta(self) -> dict:
        if self.estado == CONCLUIDA:
            return {"id": self.id, "status": CONCLUIDA, "resultado": self.resultado}
        if self.estado == FALHOU:
            return {"id": self.id, "status": FALHOU, "codigo": self.status_http, "detail": self.detalhe}
        return {"id": self.id, "status": PROCESSANDO}


class RegistroDeExtracoes:
    def __init__(
        self,
        validade_segundos: float = VALIDADE_SEGUNDOS,
        limite_em_andamento: int = LIMITE_EM_ANDAMENTO,
        relogio: Callable[[], float] = time.monotonic,
    ):
        self._validade = validade_segundos
        self._limite = limite_em_andamento
        self._relogio = relogio
        self._extracoes: dict[str, Extracao] = {}
        self._tarefas: set[asyncio.Task] = set()

    def iniciar(self, trabalho: Callable[[], Awaitable[dict]]) -> Extracao:
        """Agenda o trabalho e devolve o registro; o resultado sai de `consultar`."""
        self._descartar_expiradas()
        if sum(1 for e in self._extracoes.values() if e.estado == PROCESSANDO) >= self._limite:
            raise CapacidadeEsgotada
        extracao = Extracao(id=secrets.token_urlsafe(16))
        self._extracoes[extracao.id] = extracao
        tarefa = asyncio.create_task(self._executar(extracao, trabalho))
        self._tarefas.add(tarefa)
        tarefa.add_done_callback(self._tarefas.discard)
        return extracao

    def consultar(self, id_extracao: str) -> Extracao | None:
        self._descartar_expiradas()
        return self._extracoes.get(id_extracao)

    async def _executar(self, extracao: Extracao, trabalho: Callable[[], Awaitable[dict]]) -> None:
        try:
            extracao.resultado = await trabalho()
            extracao.estado = CONCLUIDA
        except FalhaDaExtracao as falha:
            extracao.estado = FALHOU
            extracao.status_http = falha.status
            extracao.detalhe = falha.detalhe
        except Exception:
            logger.exception("Falha inesperada na extração %s.", extracao.id)
            extracao.estado = FALHOU
            extracao.status_http = 500
            extracao.detalhe = "Falha inesperada na extração."
        finally:
            extracao.finalizada_em = self._relogio()

    def _descartar_expiradas(self) -> None:
        agora = self._relogio()
        vencidas = [
            id_extracao
            for id_extracao, extracao in self._extracoes.items()
            if extracao.finalizada_em is not None and agora - extracao.finalizada_em > self._validade
        ]
        for id_extracao in vencidas:
            del self._extracoes[id_extracao]
