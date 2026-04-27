import argparse
import json
import os
import time

from pathlib import Path

from dimex.dimex import Dimex


def CarregarConfigProcessos(caminhoConfig: str) -> dict[int, dict[str, int | str]]:
    with open(caminhoConfig, "r", encoding="utf-8") as arquivoConfig:
        dadosConfig = json.load(arquivoConfig)

    if "processos" not in dadosConfig or not isinstance(dadosConfig["processos"], list):
        raise ValueError("Arquivo de configuracao invalido: campo 'processos' ausente")

    processos = {}

    for registroProcesso in dadosConfig["processos"]:
        idProcesso = int(registroProcesso["idProcesso"])
        hostProcesso = str(registroProcesso["host"])
        portaProcesso = int(registroProcesso["porta"])

        processos[idProcesso] = {
            "host": hostProcesso,
            "porta": portaProcesso,
        }

    return processos

# Funciona
def EscreverNoArquivoCompartilhado(caminhoArquivo: str) -> None:
    fd = os.open(caminhoArquivo, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_SYNC, 0o644)
    os.write(fd, b".")
    os.write(fd, b"|")
    os.close(fd)

# não funciona, provavelmente por causa do buffering do Python
# def EscreverNoArquivoCompartilhado(caminhoArquivo: str) -> None:
#     with open(caminhoArquivo, "a", encoding="utf-8") as arquivoSaida:
#         arquivoSaida.write(".")
#         arquivoSaida.flush()
#         arquivoSaida.write("|")
#         arquivoSaida.flush()


def ExecutarProcesso(idProcesso: int, caminhoConfig: str, caminhoArquivoCompartilhado: str, quantidadeAcessos: int, logIntervalo: int) -> None:
    processos = CarregarConfigProcessos(caminhoConfig)

    if idProcesso not in processos:
        raise ValueError(f"idProcesso {idProcesso} nao existe no arquivo de configuracao")

    dimex = Dimex(idProcesso=idProcesso, processos=processos)
    dimex.Iniciar()

    acessosConcluidos = 0

    try:
        for indiceAcesso in range(quantidadeAcessos):
            # dimex.Lock()
            # try:
            #     # O trecho abaixo representa o uso do recurso compartilhado protegido pelo lock.
            #     EscreverNoArquivoCompartilhado(caminhoArquivoCompartilhado)
            # finally:
            #     dimex.Unlock()

            EscreverNoArquivoCompartilhado(caminhoArquivoCompartilhado)


            acessosConcluidos = indiceAcesso + 1

            if logIntervalo > 0 and acessosConcluidos % logIntervalo == 0:
                print(
                    f"Processo {idProcesso}: {acessosConcluidos} acessos concluidos",
                    flush=True,
                )

        # Aguarda os demais processos para evitar que fiquem sem respostas.
        statusDir = Path(caminhoArquivoCompartilhado).resolve().parent / ".dimex_status"
        statusDir.mkdir(parents=True, exist_ok=True)
        arquivoDone = statusDir / f"processo{idProcesso}.done"
        arquivoDone.write_text("1", encoding="utf-8")
        arquivosPendentes = [
            statusDir / f"processo{outroId}.done"
            for outroId in processos
            if outroId != idProcesso
        ]

        while any(not arquivo.exists() for arquivo in arquivosPendentes):
            time.sleep(0.2)
    finally:
        dimex.Parar()

    print(f"Processo {idProcesso}: execucao finalizada", flush=True)


def Main() -> None:
    parser = argparse.ArgumentParser(description="Executa um processo da aplicacao de teste com DiMeX")
    parser.add_argument("--idProcesso", type=int, required=True, help="ID do processo local")
    parser.add_argument(
        "--configProcessos",
        type=str,
        default="processosExemplo.json",
        help="Caminho do JSON com host e porta de cada processo",
    )
    parser.add_argument(
        "--arquivoCompartilhado",
        type=str,
        default="mxOUT.txt",
        help="Arquivo usado como recurso compartilhado",
    )
    parser.add_argument(
        "--quantidadeAcessos",
        type=int,
        default=2000,
        help="Numero de vezes que este processo entra na secao critica",
    )
    parser.add_argument(
        "--logIntervalo",
        type=int,
        default=200,
        help="Frequencia de logs de progresso (0 desabilita)",
    )

    args = parser.parse_args()

    caminhoArquivo = Path(args.arquivoCompartilhado)
    caminhoArquivo.parent.mkdir(parents=True, exist_ok=True)

    ExecutarProcesso(
        idProcesso=args.idProcesso,
        caminhoConfig=args.configProcessos,
        caminhoArquivoCompartilhado=args.arquivoCompartilhado,
        quantidadeAcessos=args.quantidadeAcessos,
        logIntervalo=args.logIntervalo,
    )


if __name__ == "__main__":
    Main()
