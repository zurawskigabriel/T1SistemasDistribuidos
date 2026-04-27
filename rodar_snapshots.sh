#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_ARQ="processosExemplo.json"
SAIDA_ARQ="mxOUT.txt"
SNAPSHOT_DIR="$ROOT_DIR/.dimex_snapshots"
QTD_ACESSOS="2000"
SNAPSHOT_QTD="200"
SNAPSHOT_INTERVALO="0.05"
SNAPSHOT_INICIADOR="1"

if [[ ! -f "$ROOT_DIR/processoDimex.py" ]]; then
  echo "Erro: processoDimex.py nao encontrado em $ROOT_DIR"
  exit 1
fi

if [[ ! -f "$ROOT_DIR/validarSnapshots.py" ]]; then
  echo "Erro: validarSnapshots.py nao encontrado em $ROOT_DIR"
  exit 1
fi

if [[ ! -f "$ROOT_DIR/$CONFIG_ARQ" ]]; then
  echo "Erro: $CONFIG_ARQ nao encontrado em $ROOT_DIR"
  exit 1
fi

echo "Limpando arquivo de saida: $SAIDA_ARQ"
: > "$ROOT_DIR/$SAIDA_ARQ"

if [[ -d "$SNAPSHOT_DIR" ]]; then
  rm -rf "$SNAPSHOT_DIR"
fi

python3 "$ROOT_DIR/processoDimex.py" \
  --idProcesso 1 \
  --configProcessos "$ROOT_DIR/$CONFIG_ARQ" \
  --arquivoCompartilhado "$ROOT_DIR/$SAIDA_ARQ" \
  --quantidadeAcessos "$QTD_ACESSOS" \
  --snapshotQuantidade "$SNAPSHOT_QTD" \
  --snapshotIntervalo "$SNAPSHOT_INTERVALO" \
  --snapshotIniciador "$SNAPSHOT_INICIADOR" \
  --snapshotDir "$SNAPSHOT_DIR" &
PID1=$!

python3 "$ROOT_DIR/processoDimex.py" \
  --idProcesso 2 \
  --configProcessos "$ROOT_DIR/$CONFIG_ARQ" \
  --arquivoCompartilhado "$ROOT_DIR/$SAIDA_ARQ" \
  --quantidadeAcessos "$QTD_ACESSOS" \
  --snapshotDir "$SNAPSHOT_DIR" &
PID2=$!

python3 "$ROOT_DIR/processoDimex.py" \
  --idProcesso 3 \
  --configProcessos "$ROOT_DIR/$CONFIG_ARQ" \
  --arquivoCompartilhado "$ROOT_DIR/$SAIDA_ARQ" \
  --quantidadeAcessos "$QTD_ACESSOS" \
  --snapshotDir "$SNAPSHOT_DIR" &
PID3=$!

wait "$PID1" "$PID2" "$PID3"

echo "Processos finalizados. Validando snapshots..."
python3 "$ROOT_DIR/validarSnapshots.py" \
  --diretorio "$SNAPSHOT_DIR" \
  --configProcessos "$ROOT_DIR/$CONFIG_ARQ"
