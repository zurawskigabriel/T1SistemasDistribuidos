import argparse
import sys


def LerConteudoArquivo(caminhoArquivo: str) -> str:
    with open(caminhoArquivo, "r", encoding="utf-8") as arquivoEntrada:
        return arquivoEntrada.read()


def EncontrarViolacoes(conteudoArquivo: str) -> list[tuple[int, str]]:
    violacoes = []

    for indice in range(len(conteudoArquivo) - 1):
        parAtual = conteudoArquivo[indice : indice + 2]
        if parAtual == "||" or parAtual == "..":
            violacoes.append((indice, parAtual))

    return violacoes


def Main() -> None:
    parser = argparse.ArgumentParser(description="Valida violacoes de exclusao mutua no arquivo de saida")
    parser.add_argument(
        "--arquivo",
        type=str,
        default="mxOUT.txt",
        help="Arquivo gerado pela aplicacao distribuida",
    )

    args = parser.parse_args()

    conteudoArquivo = LerConteudoArquivo(args.arquivo)
    violacoes = EncontrarViolacoes(conteudoArquivo)

    print(f"Total de caracteres no arquivo: {len(conteudoArquivo)}")
    print(f"Total de pares avaliados: {max(0, len(conteudoArquivo) - 1)}")

    if not violacoes:
        print("Nenhuma violacao encontrada: nao ha || nem ..")
        sys.exit(0)

    print(f"Foram encontradas {len(violacoes)} violacoes")
    print("Primeiras violacoes:")

    for indice, (posicao, padrao) in enumerate(violacoes[:20], start=1):
        print(f"{indice:02d}. posicao={posicao} padrao={padrao}")

    sys.exit(1)


if __name__ == "__main__":
    Main()
