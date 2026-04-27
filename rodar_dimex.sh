#!/usr/bin/env bash
set -euo pipefail

# Roda os 3 processos DiMeX em terminais separados e abre um 4o terminal
# que espera os processos terminarem para executar a validacao.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_ARQ="processosExemplo.json"
SAIDA_ARQ="mxOUT.txt"
QTD_ACESSOS="2000"
STATUS_DIR="$ROOT_DIR/.dimex_status"
DONE_P1="$STATUS_DIR/processo1.done"
DONE_P2="$STATUS_DIR/processo2.done"
DONE_P3="$STATUS_DIR/processo3.done"

if [[ ! -f "$ROOT_DIR/processoDimex.py" ]]; then
  echo "Erro: processoDimex.py nao encontrado em $ROOT_DIR"
  exit 1
fi

if [[ ! -f "$ROOT_DIR/validarSaida.py" ]]; then
  echo "Erro: validarSaida.py nao encontrado em $ROOT_DIR"
  exit 1
fi

if [[ ! -f "$ROOT_DIR/$CONFIG_ARQ" ]]; then
  echo "Erro: $CONFIG_ARQ nao encontrado em $ROOT_DIR"
  exit 1
fi

TERMINAL_CMD=""
if command -v gnome-terminal >/dev/null 2>&1; then
  TERMINAL_CMD="gnome-terminal"
elif command -v xfce4-terminal >/dev/null 2>&1; then
  TERMINAL_CMD="xfce4-terminal"
elif command -v konsole >/dev/null 2>&1; then
  TERMINAL_CMD="konsole"
elif command -v xterm >/dev/null 2>&1; then
  TERMINAL_CMD="xterm"
else
  echo "Erro: nenhum terminal suportado encontrado (gnome-terminal, xfce4-terminal, konsole, xterm)."
  exit 1
fi

open_terminal() {
  local title="$1"
  local cmd="$2"

  case "$TERMINAL_CMD" in
    gnome-terminal)
      "$TERMINAL_CMD" --title="$title" -- bash -lc "$cmd; exec bash"
      ;;
    xfce4-terminal)
      "$TERMINAL_CMD" --title="$title" --hold -e "bash -lc \"$cmd\""
      ;;
    konsole)
      "$TERMINAL_CMD" --hold -p tabtitle="$title" -e bash -lc "$cmd; exec bash"
      ;;
    xterm)
      "$TERMINAL_CMD" -T "$title" -hold -e bash -lc "$cmd"
      ;;
  esac
}

echo "Limpando arquivo de saida: $SAIDA_ARQ"
: > "$ROOT_DIR/$SAIDA_ARQ"

mkdir -p "$STATUS_DIR"
rm -f "$DONE_P1" "$DONE_P2" "$DONE_P3"

CMD_P1="cd '$ROOT_DIR' && python3 processoDimex.py --idProcesso 1 --configProcessos '$CONFIG_ARQ' --arquivoCompartilhado '$SAIDA_ARQ' --quantidadeAcessos '$QTD_ACESSOS'; RC=\$?; echo \"\$RC\" > '$DONE_P1'; echo \"Processo 1 terminou com codigo \$RC\""
CMD_P2="cd '$ROOT_DIR' && python3 processoDimex.py --idProcesso 2 --configProcessos '$CONFIG_ARQ' --arquivoCompartilhado '$SAIDA_ARQ' --quantidadeAcessos '$QTD_ACESSOS'; RC=\$?; echo \"\$RC\" > '$DONE_P2'; echo \"Processo 2 terminou com codigo \$RC\""
CMD_P3="cd '$ROOT_DIR' && python3 processoDimex.py --idProcesso 3 --configProcessos '$CONFIG_ARQ' --arquivoCompartilhado '$SAIDA_ARQ' --quantidadeAcessos '$QTD_ACESSOS'; RC=\$?; echo \"\$RC\" > '$DONE_P3'; echo \"Processo 3 terminou com codigo \$RC\""

CMD_VAL="cd '$ROOT_DIR' && \
  echo 'Aguardando termino dos processos processoDimex.py...' && \
  while [[ ! -f '$DONE_P1' || ! -f '$DONE_P2' || ! -f '$DONE_P3' ]]; do sleep 1; done && \
  echo 'Processos finalizados. Executando validacao...' && \
  python3 validarSaida.py --arquivo '$SAIDA_ARQ'"

open_terminal "DiMeX Processo 1" "$CMD_P1"
open_terminal "DiMeX Processo 2" "$CMD_P2"
open_terminal "DiMeX Processo 3" "$CMD_P3"
open_terminal "DiMeX Validacao" "$CMD_VAL"