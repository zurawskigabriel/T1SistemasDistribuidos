import argparse
import json
from pathlib import Path
from typing import Any

ESTADO_NAO_QUERO = "NAO_QUERO_SC"
ESTADO_QUERO = "QUERO_SC"
ESTADO_ESTOU = "ESTOU_SC"
TIPO_RESPOSTA = "RESPOSTA"


def CarregarConfigProcessos(caminhoConfig: str) -> set[int]:
    with open(caminhoConfig, "r", encoding="utf-8") as arquivoConfig:
        dadosConfig = json.load(arquivoConfig)

    if "processos" not in dadosConfig or not isinstance(dadosConfig["processos"], list):
        raise ValueError("Arquivo de configuracao invalido: campo 'processos' ausente")

    processos = set()
    for registro in dadosConfig["processos"]:
        processos.add(int(registro["idProcesso"]))

    return processos


def LerSnapshots(diretorio: Path) -> dict[str, dict[int, dict[str, Any]]]:
    snapshots: dict[str, dict[int, dict[str, Any]]] = {}

    for arquivo in sorted(diretorio.glob("snapshot_*_processo*.json")):
        with arquivo.open("r", encoding="utf-8") as handle:
            dados = json.load(handle)

        snapshotId = str(dados.get("snapshotId", ""))
        processoId = int(dados.get("processoId", -1))

        if not snapshotId or processoId < 0:
            continue

        snapshots.setdefault(snapshotId, {})[processoId] = dados

    return snapshots


def ExtrairEstadoProcesso(dados: dict[str, Any]) -> dict[str, Any]:
    estado = dados.get("estado", {})

    respostasPendentes = {
        int(idRemoto) for idRemoto in estado.get("respostasPendentes", [])
    }
    respostasAdiadas = {
        int(idRemoto): bool(adiado)
        for idRemoto, adiado in estado.get("respostasAdiadas", {}).items()
    }

    canaisEntrada = {
        int(idRemoto): list(mensagens)
        for idRemoto, mensagens in dados.get("canaisEntrada", {}).items()
    }

    return {
        "estadoAtual": str(estado.get("estadoAtual", "")),
        "timestampPedidoAtual": estado.get("timestampPedidoAtual"),
        "relogioLamport": estado.get("relogioLamport"),
        "respostasPendentes": respostasPendentes,
        "respostasAdiadas": respostasAdiadas,
        "canaisEntrada": canaisEntrada,
    }


def HaRespostaEmTransito(canaisEntrada: dict[int, list[dict[str, Any]]], origemId: int) -> bool:
    for mensagem in canaisEntrada.get(origemId, []):
        if mensagem.get("tipo") == TIPO_RESPOSTA:
            return True
    return False


def ValidarSnapshot(
    snapshotId: str,
    grupo: dict[int, dict[str, Any]],
    processosEsperados: set[int] | None,
) -> list[str]:
    violacoes: list[str] = []

    processosSnapshot = set(grupo.keys())
    processos = processosEsperados or processosSnapshot

    if processosEsperados is not None and processosSnapshot != processosEsperados:
        faltando = sorted(processosEsperados - processosSnapshot)
        extras = sorted(processosSnapshot - processosEsperados)
        if faltando:
            violacoes.append(
                f"Snapshot {snapshotId}: processos faltando {faltando}"
            )
        if extras:
            violacoes.append(
                f"Snapshot {snapshotId}: processos extras {extras}"
            )

    estados = {
        processoId: ExtrairEstadoProcesso(dados)
        for processoId, dados in grupo.items()
    }

    em_sc = [
        processoId
        for processoId, estado in estados.items()
        if estado["estadoAtual"] == ESTADO_ESTOU
    ]
    if len(em_sc) > 1:
        violacoes.append(
            f"Snapshot {snapshotId}: mais de um processo na SC: {sorted(em_sc)}"
        )

    todos_nao_quero = all(
        estado["estadoAtual"] == ESTADO_NAO_QUERO for estado in estados.values()
    )
    if todos_nao_quero:
        for processoId, estado in estados.items():
            if estado["respostasPendentes"]:
                violacoes.append(
                    f"Snapshot {snapshotId}: processo {processoId} com respostasPendentes"
                )
            if estado["timestampPedidoAtual"] is not None:
                violacoes.append(
                    f"Snapshot {snapshotId}: processo {processoId} com timestampPedidoAtual"
                )
            if any(estado["respostasAdiadas"].values()):
                violacoes.append(
                    f"Snapshot {snapshotId}: processo {processoId} com respostasAdiadas"
                )
            if any(estado["canaisEntrada"].get(idRemoto) for idRemoto in processos if idRemoto != processoId):
                violacoes.append(
                    f"Snapshot {snapshotId}: processo {processoId} com mensagens em transito"
                )

    for processoId, estado in estados.items():
        if estado["estadoAtual"] in (ESTADO_NAO_QUERO, ESTADO_ESTOU):
            if estado["respostasPendentes"]:
                violacoes.append(
                    f"Snapshot {snapshotId}: processo {processoId} nao deveria ter respostasPendentes"
                )

        for remotoId, adiado in estado["respostasAdiadas"].items():
            if adiado and estado["estadoAtual"] == ESTADO_NAO_QUERO:
                violacoes.append(
                    f"Snapshot {snapshotId}: processo {processoId} adiou resposta sem querer SC"
                )

    for processoId, estado in estados.items():
        if estado["estadoAtual"] != ESTADO_QUERO:
            continue

        pendentes = estado["respostasPendentes"]
        canaisEntrada = estado["canaisEntrada"]

        for remotoId in processos:
            if remotoId == processoId:
                continue
            recebeu = remotoId not in pendentes
            em_transito = HaRespostaEmTransito(canaisEntrada, remotoId)
            adiado = False
            if remotoId in estados:
                adiado = estados[remotoId]["respostasAdiadas"].get(processoId, False)
            total = int(recebeu) + int(em_transito) + int(adiado)
            if total != 1:
                violacoes.append(
                    "Snapshot {}: processo {} inconsistencias com remoto {} (recebeu={}, transito={}, adiado={})".format(
                        snapshotId,
                        processoId,
                        remotoId,
                        recebeu,
                        em_transito,
                        adiado,
                    )
                )

    return violacoes


def OrdenarSnapshotIds(snapshotIds: list[str]) -> list[str]:
    def chave(snapshotId: str) -> tuple[int, str]:
        return (0, str(int(snapshotId))) if snapshotId.isdigit() else (1, snapshotId)

    return sorted(snapshotIds, key=chave)


def Main() -> None:
    parser = argparse.ArgumentParser(description="Valida invariantes em snapshots do DiMeX")
    parser.add_argument(
        "--diretorio",
        type=str,
        default=".dimex_snapshots",
        help="Diretorio contendo os arquivos de snapshot",
    )
    parser.add_argument(
        "--configProcessos",
        type=str,
        default="",
        help="JSON com configuracao dos processos (opcional)",
    )

    args = parser.parse_args()

    diretorio = Path(args.diretorio)
    if not diretorio.exists():
        raise SystemExit(f"Diretorio nao encontrado: {diretorio}")

    processosEsperados = None
    if args.configProcessos:
        processosEsperados = CarregarConfigProcessos(args.configProcessos)

    snapshots = LerSnapshots(diretorio)
    if not snapshots:
        raise SystemExit("Nenhum snapshot encontrado")

    totalViolacoes = 0
    totalSnapshots = 0

    for snapshotId in OrdenarSnapshotIds(list(snapshots.keys())):
        grupo = snapshots[snapshotId]
        violacoes = ValidarSnapshot(snapshotId, grupo, processosEsperados)
        totalSnapshots += 1
        if violacoes:
            totalViolacoes += len(violacoes)
            for violacao in violacoes:
                print(violacao)

    print(f"Snapshots avaliados: {totalSnapshots}")
    print(f"Total de violacoes: {totalViolacoes}")

    raise SystemExit(1 if totalViolacoes else 0)


if __name__ == "__main__":
    Main()
