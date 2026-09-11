#!/usr/bin/env bash
# Download shyngys879/kazakh-whisper-large-v3-turbo (Transformers) for 8GB Mac.
# Runtime: fp16 on Apple MPS via asr/kazakh_hf.py (alias: kazakh-turbo).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
export PATH="${HOME}/bin:${PATH}"

HF_ID="${KAZAKH_WHISPER_HF:-shyngys879/kazakh-whisper-large-v3-turbo}"
OUT="$ROOT/models/whisper/_hf_src"

echo "Installing torch/transformers if needed…"
pip install -q 'torch' 'transformers>=4.46,<4.50' 'accelerate' 'sentencepiece' 'huggingface_hub'

mkdir -p "$(dirname "$OUT")"
echo "Downloading $HF_ID → $OUT …"
python - <<PY
from huggingface_hub import snapshot_download
p = snapshot_download("$HF_ID", local_dir="$OUT")
print("OK", p)
PY

du -sh "$OUT"
ls -lah "$OUT" | head
echo "Ready. Use: --whisper-model kazakh-turbo --language kk"
echo "Tip: на 8GB закрой Ollama на время ASR, потом снова открой для LLM."
