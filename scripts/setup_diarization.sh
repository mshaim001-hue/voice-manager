#!/usr/bin/env bash
# Download sherpa-onnx diarization models (offline after this).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$ROOT/models/diarization"
mkdir -p "$DIR"
cd "$DIR"

if [ ! -f sherpa-onnx-pyannote-segmentation-3-0/model.onnx ]; then
  echo "Downloading segmentation model…"
  curl -fsSL -o seg.tar.bz2 \
    https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2
  tar xjf seg.tar.bz2
  rm -f seg.tar.bz2
fi

if [ ! -f nemo_en_titanet_small.onnx ]; then
  echo "Downloading embedding model…"
  curl -fsSL -o nemo_en_titanet_small.onnx \
    https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/nemo_en_titanet_small.onnx
fi

echo "OK: $DIR"
ls -lah "$DIR"
