from __future__ import annotations

import queue
import socket
import threading
import time
from typing import Any, Callable

from .serializacao import DesserializarMensagem, SerializarMensagem


class LinkPerfeito:
    """Implementacao de Perfect Link sobre sockets TCP."""

    def __init__(
        self,
        idProcesso: int,
        processos: dict[int, dict[str, Any]],
        aoReceberMensagem: Callable[[dict[str, Any]], None],
    ) -> None:
        self.idProcesso = idProcesso
        self.processos = processos
        self.aoReceberMensagem = aoReceberMensagem

        self.destinos = [
            idRemoto for idRemoto in sorted(processos.keys()) if idRemoto != idProcesso
        ]
        self.enderecosDestino = {
            idRemoto: (
                str(processos[idRemoto]["host"]),
                int(processos[idRemoto]["porta"]),
            )
            for idRemoto in self.destinos
        }

        self.encerrado = threading.Event()
        self.filasSaida = {idRemoto: queue.Queue() for idRemoto in self.destinos}

        self.travaConexoes = threading.Lock()
        self.socketServidor: socket.socket | None = None
        self.conexoesSaida: dict[int, socket.socket] = {}
        self.conexoesEntrada: set[socket.socket] = set()

        self.threads: list[threading.Thread] = []

    def Iniciar(self) -> None:
        """Inicializa servidor local e threads de envio para cada destino."""
        hostLocal = str(self.processos[self.idProcesso]["host"])
        portaLocal = int(self.processos[self.idProcesso]["porta"])

        self.socketServidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socketServidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socketServidor.bind((hostLocal, portaLocal))
        self.socketServidor.listen()
        self.socketServidor.settimeout(1.0)

        threadAceite = threading.Thread(target=self.ThreadAlvoAceitar, daemon=True)
        threadAceite.start()
        self.threads.append(threadAceite)

        for destinoId in self.destinos:
            threadEnvio = threading.Thread(
                target=self.ThreadAlvoEnviar,
                args=(destinoId,),
                daemon=True,
            )
            threadEnvio.start()
            self.threads.append(threadEnvio)

    def Parar(self) -> None:
        """Encerra servidor, conexoes e threads do modulo de comunicacao."""
        self.encerrado.set()

        if self.socketServidor is not None:
            self.socketServidor.close()

        for destinoId in self.destinos:
            self.filasSaida[destinoId].put(None)

        with self.travaConexoes:
            for conexao in self.conexoesSaida.values():
                conexao.close()
            self.conexoesSaida.clear()

            for conexao in list(self.conexoesEntrada):
                conexao.close()
            self.conexoesEntrada.clear()

        for threadAtual in self.threads:
            threadAtual.join(timeout=1.0)

    def Enviar(self, destinoId: int, mensagem: dict[str, Any]) -> None:
        """Enfileira mensagem para envio ordenado ao destino."""
        if destinoId not in self.filasSaida:
            raise ValueError(f"Destino desconhecido: {destinoId}")
        self.filasSaida[destinoId].put(mensagem)

    def ThreadAlvoAceitar(self) -> None:
        """Aceita conexoes de entrada e cria uma thread de leitura por conexao."""
        while not self.encerrado.is_set():
            try:
                conexaoSocket, _ = self.socketServidor.accept()  # type: ignore[union-attr]
            except socket.timeout:
                continue
            except OSError:
                break

            with self.travaConexoes:
                self.conexoesEntrada.add(conexaoSocket)

            threadRecepcao = threading.Thread(
                target=self.ThreadAlvoReceber,
                args=(conexaoSocket,),
                daemon=True,
            )
            threadRecepcao.start()
            self.threads.append(threadRecepcao)

    def ThreadAlvoReceber(self, conexaoSocket: socket.socket) -> None:
        """Le mensagens de uma conexao de entrada ate o seu encerramento."""
        try:
            with conexaoSocket.makefile("r", encoding="utf-8") as leitor:
                for linha in leitor:
                    if self.encerrado.is_set():
                        break

                    linhaLimpa = linha.strip()
                    if not linhaLimpa:
                        continue

                    try:
                        mensagem = DesserializarMensagem(linhaLimpa)
                    except ValueError:
                        # Uma linha invalida nao deve derrubar o processo todo.
                        continue

                    self.aoReceberMensagem(mensagem)
        finally:
            with self.travaConexoes:
                if conexaoSocket in self.conexoesEntrada:
                    self.conexoesEntrada.remove(conexaoSocket)
            conexaoSocket.close()

    def ThreadAlvoEnviar(self, destinoId: int) -> None:
        """Consome fila de saida e envia mensagens em ordem FIFO por destino."""
        filaDestino = self.filasSaida[destinoId]

        while not self.encerrado.is_set():
            try:
                mensagem = filaDestino.get(timeout=0.2)
            except queue.Empty:
                continue

            if mensagem is None:
                break

            while not self.encerrado.is_set():
                conexaoSocket = self.ObterOuConectar(destinoId)
                if conexaoSocket is None:
                    time.sleep(0.2)
                    continue

                try:
                    conexaoSocket.sendall(SerializarMensagem(mensagem))
                    break
                except OSError:
                    self.FecharConexaoSaida(destinoId)

    def ObterOuConectar(self, destinoId: int) -> socket.socket | None:
        """Retorna conexao de saida ativa; caso nao exista, tenta criar."""
        with self.travaConexoes:
            conexaoExistente = self.conexoesSaida.get(destinoId)
            if conexaoExistente is not None:
                return conexaoExistente

        hostDestino, portaDestino = self.enderecosDestino[destinoId]

        try:
            novoSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            novoSocket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            novoSocket.settimeout(1.0)
            novoSocket.connect((hostDestino, portaDestino))
            novoSocket.settimeout(None)
        except OSError:
            return None

        with self.travaConexoes:
            if destinoId in self.conexoesSaida:
                novoSocket.close()
                return self.conexoesSaida[destinoId]

            self.conexoesSaida[destinoId] = novoSocket
            return novoSocket

    def FecharConexaoSaida(self, destinoId: int) -> None:
        """Fecha a conexao de saida para forcar reconexao no proximo envio."""
        with self.travaConexoes:
            conexaoAtual = self.conexoesSaida.pop(destinoId, None)

        if conexaoAtual is not None:
            conexaoAtual.close()
