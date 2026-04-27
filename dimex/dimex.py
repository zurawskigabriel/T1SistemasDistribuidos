from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .linkPerfeito import LinkPerfeito
from .tipos import EstadoDimex, TipoMensagem


@dataclass
class SnapshotContext:
    snapshotId: str
    estadoLocal: dict[str, Any]
    canaisEstado: dict[int, list[dict[str, Any]]]
    canaisGravando: set[int] = field(default_factory=set)
    marcadoresRecebidos: set[int] = field(default_factory=set)

    def MarcarCanal(self, origemId: int) -> None:
        self.marcadoresRecebidos.add(origemId)
        self.canaisGravando.discard(origemId)

    def Concluido(self, totalCanais: int) -> bool:
        return len(self.marcadoresRecebidos) >= totalCanais


class Dimex:
    """Modulo de exclusao mutua distribuida com interface Lock/Unlock."""

    def __init__(
        self,
        idProcesso: int,
        processos: dict[int, dict[str, Any]],
        diretorioSnapshots: str | Path | None = None,
    ) -> None:
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
        self.travaSnapshot = threading.Lock()
        self.sequenciaSnapshot = 0
        self.snapshotsEmAndamento: dict[str, SnapshotContext] = {}
        self.diretorioSnapshots = (
            Path(diretorioSnapshots)
            if diretorioSnapshots is not None
            else Path(".dimex_snapshots")
        )
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

    def IniciarSnapshot(self, snapshotId: int | str | None = None) -> str:
        """Inicia um snapshot distribuido pelo algoritmo de Chandy-Lamport."""
        if snapshotId is None:
            with self.travaSnapshot:
                self.sequenciaSnapshot += 1
                snapshotId = str(self.sequenciaSnapshot)
        snapshotIdStr = str(snapshotId)
        self.RegistrarSnapshot(snapshotIdStr, None)
        return snapshotIdStr

    def TratarMensagemRecebida(self, mensagem: dict[str, Any]) -> None:
        """Roteia mensagens recebidas para o tratamento correto."""
        tipoMensagem = mensagem.get("tipo")

        if tipoMensagem == TipoMensagem.Marker.value:
            self.TratarMarker(mensagem)
            return

        self.RegistrarMensagemEmSnapshots(mensagem)

        if tipoMensagem == TipoMensagem.Pedido.value:
            self.TratarPedido(mensagem)
            return

        if tipoMensagem == TipoMensagem.Resposta.value:
            self.TratarResposta(mensagem)

    def TratarMarker(self, mensagem: dict[str, Any]) -> None:
        """Processa mensagem de marker do algoritmo de snapshot."""
        try:
            origemId = int(mensagem["origemId"])
            snapshotId = str(mensagem["snapshotId"])
        except (KeyError, TypeError, ValueError):
            return

        if origemId == self.idProcesso or origemId not in self.idsRemotos:
            return

        self.RegistrarSnapshot(snapshotId, origemId)

    def RegistrarMensagemEmSnapshots(self, mensagem: dict[str, Any]) -> None:
        """Registra mensagens em transito nos snapshots ativos."""
        tipoMensagem = mensagem.get("tipo")
        if tipoMensagem == TipoMensagem.Marker.value:
            return

        try:
            origemId = int(mensagem["origemId"])
        except (KeyError, TypeError, ValueError):
            return

        if origemId == self.idProcesso or origemId not in self.idsRemotos:
            return

        with self.travaSnapshot:
            if not self.snapshotsEmAndamento:
                return
            for contexto in self.snapshotsEmAndamento.values():
                if origemId in contexto.canaisGravando:
                    contexto.canaisEstado[origemId].append(dict(mensagem))

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

    def RegistrarSnapshot(self, snapshotId: str, origemId: int | None) -> None:
        """Cria ou atualiza o contexto de snapshot conforme markers recebidos."""
        contexto = None
        novoSnapshot = False

        with self.travaSnapshot:
            contexto = self.snapshotsEmAndamento.get(snapshotId)

        if contexto is None:
            estadoLocal = self.CapturarEstadoLocal()
            contextoNovo = self.CriarContextoSnapshot(snapshotId, estadoLocal, origemId)
            with self.travaSnapshot:
                contexto = self.snapshotsEmAndamento.get(snapshotId)
                if contexto is None:
                    self.snapshotsEmAndamento[snapshotId] = contextoNovo
                    contexto = contextoNovo
                    novoSnapshot = True

        if contexto is None:
            return

        if origemId is not None and not novoSnapshot:
            with self.travaSnapshot:
                contexto.MarcarCanal(origemId)

        contextoFinal = None
        with self.travaSnapshot:
            if contexto.Concluido(len(self.idsRemotos)):
                contextoFinal = self.snapshotsEmAndamento.pop(snapshotId, None)

        if novoSnapshot:
            self.EnviarMarkers(snapshotId)

        if contextoFinal is not None:
            self.SalvarSnapshot(contextoFinal)

    def CapturarEstadoLocal(self) -> dict[str, Any]:
        """Captura o estado local do DiMeX para uso no snapshot."""
        with self.condicaoEstado:
            return {
                "relogioLamport": self.relogioLamport,
                "estadoAtual": self.estadoAtual.value,
                "timestampPedidoAtual": self.timestampPedidoAtual,
                "respostasPendentes": sorted(self.respostasPendentes),
                "respostasAdiadas": {
                    str(idRemoto): bool(adiado)
                    for idRemoto, adiado in self.respostasAdiadas.items()
                },
            }

    def CriarContextoSnapshot(
        self,
        snapshotId: str,
        estadoLocal: dict[str, Any],
        origemId: int | None,
    ) -> SnapshotContext:
        canaisEstado = {idRemoto: [] for idRemoto in self.idsRemotos}
        canaisGravando = set(self.idsRemotos)
        marcadoresRecebidos: set[int] = set()

        if origemId is not None and origemId in canaisGravando:
            canaisGravando.discard(origemId)
            marcadoresRecebidos.add(origemId)

        return SnapshotContext(
            snapshotId=snapshotId,
            estadoLocal=estadoLocal,
            canaisEstado=canaisEstado,
            canaisGravando=canaisGravando,
            marcadoresRecebidos=marcadoresRecebidos,
        )

    def EnviarMarkers(self, snapshotId: str) -> None:
        """Envia markers para todos os processos remotos."""
        mensagemMarker = {
            "tipo": TipoMensagem.Marker.value,
            "origemId": self.idProcesso,
            "snapshotId": snapshotId,
        }
        for destinoId in self.idsRemotos:
            self.linkPerfeito.Enviar(destinoId, mensagemMarker)

    def SalvarSnapshot(self, contexto: SnapshotContext) -> None:
        """Persiste o snapshot completo em arquivo JSON."""
        self.diretorioSnapshots.mkdir(parents=True, exist_ok=True)
        arquivoSnapshot = self.diretorioSnapshots / self.NomeArquivoSnapshot(
            contexto.snapshotId
        )
        conteudo = {
            "snapshotId": contexto.snapshotId,
            "processoId": self.idProcesso,
            "estado": contexto.estadoLocal,
            "canaisEntrada": {
                str(idRemoto): contexto.canaisEstado.get(idRemoto, [])
                for idRemoto in self.idsRemotos
            },
        }
        arquivoSnapshot.write_text(
            json.dumps(conteudo, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def NomeArquivoSnapshot(self, snapshotId: str) -> str:
        """Gera um nome seguro de arquivo para um snapshot."""
        permitido = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        safeId = "".join(ch if ch in permitido else "_" for ch in snapshotId)
        return f"snapshot_{safeId}_processo{self.idProcesso}.json"
