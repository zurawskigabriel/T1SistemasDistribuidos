from __future__ import annotations

import threading
from typing import Any

from .linkPerfeito import LinkPerfeito
from .tipos import EstadoDimex, TipoMensagem


class Dimex:
    """Modulo de exclusao mutua distribuida com interface Lock/Unlock."""

    def __init__(self, idProcesso: int, processos: dict[int, dict[str, Any]]) -> None:
        self.idProcesso = idProcesso
        self.processos = processos
        self.idsRemotos = [
            idRemoto for idRemoto in sorted(processos.keys()) if idRemoto != idProcesso
        ]

        self.relogioLamport = 0
        self.estadoAtual = EstadoDimex.NaoQueroSc
        self.timestampPedidoAtual: int | None = None

        self.respostasPendentes: set[int] = set()
        self.respostasAdiadas = {idRemoto: False for idRemoto in self.idsRemotos}

        self.condicaoEstado = threading.Condition()
        self.linkPerfeito = LinkPerfeito(
            idProcesso=idProcesso,
            processos=processos,
            aoReceberMensagem=self.TratarMensagemRecebida,
        )

    def Iniciar(self) -> None:
        """Inicializa camada de comunicacao."""
        self.linkPerfeito.Iniciar()

    def Parar(self) -> None:
        """Finaliza camada de comunicacao."""
        self.linkPerfeito.Parar()

    def Lock(self) -> None:
        """Solicita a secao critica e bloqueia ate obter todas as respostas."""
        with self.condicaoEstado:
            self.relogioLamport += 1
            self.timestampPedidoAtual = self.relogioLamport
            self.estadoAtual = EstadoDimex.QueroSc
            self.respostasPendentes = set(self.idsRemotos)

            mensagemPedido = {
                "tipo": TipoMensagem.Pedido.value,
                "origemId": self.idProcesso,
                "relogio": self.timestampPedidoAtual,
            }

        for destinoId in self.idsRemotos:
            self.linkPerfeito.Enviar(destinoId, mensagemPedido)

        with self.condicaoEstado:
            while self.respostasPendentes:
                self.condicaoEstado.wait()
            self.estadoAtual = EstadoDimex.EstouSc

    def Unlock(self) -> None:
        """Libera secao critica e envia respostas que estavam adiadas."""
        destinosAdiados: list[int] = []

        with self.condicaoEstado:
            if self.estadoAtual != EstadoDimex.EstouSc:
                raise RuntimeError("Unlock chamado sem Lock previo concluido")

            self.estadoAtual = EstadoDimex.NaoQueroSc
            self.timestampPedidoAtual = None

            for idRemoto, estavaAdiado in self.respostasAdiadas.items():
                if estavaAdiado:
                    destinosAdiados.append(idRemoto)
                    self.respostasAdiadas[idRemoto] = False

            self.relogioLamport += 1
            relogioResposta = self.relogioLamport

        for destinoId in destinosAdiados:
            mensagemResposta = {
                "tipo": TipoMensagem.Resposta.value,
                "origemId": self.idProcesso,
                "relogio": relogioResposta,
            }
            self.linkPerfeito.Enviar(destinoId, mensagemResposta)

    def TratarMensagemRecebida(self, mensagem: dict[str, Any]) -> None:
        """Roteia mensagens recebidas para o tratamento correto."""
        tipoMensagem = mensagem.get("tipo")

        if tipoMensagem == TipoMensagem.Pedido.value:
            self.TratarPedido(mensagem)
            return

        if tipoMensagem == TipoMensagem.Resposta.value:
            self.TratarResposta(mensagem)

    def TratarPedido(self, mensagem: dict[str, Any]) -> None:
        """Aplica regra de prioridade do DiMeX para responder ou adiar."""
        try:
            origemId = int(mensagem["origemId"])
            relogioRemoto = int(mensagem["relogio"])
        except (KeyError, TypeError, ValueError):
            # Como a rede pode receber dados inesperados, mensagens invalidas sao ignoradas.
            return

        if origemId == self.idProcesso or origemId not in self.respostasAdiadas:
            return

        responderAgora = False

        with self.condicaoEstado:
            self.relogioLamport = max(self.relogioLamport, relogioRemoto) + 1

            if self.DeveResponderImediatamente(origemId, relogioRemoto):
                responderAgora = True
                self.relogioLamport += 1
                relogioResposta = self.relogioLamport
            else:
                self.respostasAdiadas[origemId] = True

        if responderAgora:
            mensagemResposta = {
                "tipo": TipoMensagem.Resposta.value,
                "origemId": self.idProcesso,
                "relogio": relogioResposta,
            }
            self.linkPerfeito.Enviar(origemId, mensagemResposta)

    def TratarResposta(self, mensagem: dict[str, Any]) -> None:
        """Registra respostas recebidas e libera Lock quando todas chegaram."""
        try:
            origemId = int(mensagem["origemId"])
            relogioRemoto = int(mensagem["relogio"])
        except (KeyError, TypeError, ValueError):
            return

        with self.condicaoEstado:
            self.relogioLamport = max(self.relogioLamport, relogioRemoto) + 1
            self.respostasPendentes.discard(origemId)

            if not self.respostasPendentes and self.estadoAtual == EstadoDimex.QueroSc:
                self.condicaoEstado.notify_all()

    def DeveResponderImediatamente(self, origemId: int, timestampRemoto: int) -> bool:
        """Define prioridade entre pedidos concorrentes pelo par (timestamp, id)."""
        if self.estadoAtual == EstadoDimex.NaoQueroSc:
            return True

        if self.estadoAtual == EstadoDimex.EstouSc:
            return False

        if self.timestampPedidoAtual is None:
            return True

        prioridadeLocal = (self.timestampPedidoAtual, self.idProcesso)
        prioridadeRemota = (timestampRemoto, origemId)

        return prioridadeRemota < prioridadeLocal
