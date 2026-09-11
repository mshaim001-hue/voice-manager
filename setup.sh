#!/usr/bin/env bash
# One-shot setup for colleagues: clone → ./setup.sh → UI opens.
# Idempotent — safe to re-run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

START_UI=1
DO_DIARIZE=1
DO_SMOKE=1
FULL=0
# Default: one LLM for M4 24GB. --full also pulls A/B candidates.
MODELS=(gemma3:12b)
WHISPER_PRELOAD="turbo"

usage() {
  cat <<'EOF'
Usage: ./setup.sh [options]

  (no args)       Install everything and open the UI
  --no-ui         Setup only, do not launch Streamlit
  --skip-diarize  Skip sherpa-onnx speaker models
  --skip-smoke    Skip quick LLM smoke test
  --full          Also pull qwen3:14b + qwen2.5:14b
  -h, --help      This help

Env:
  MODELS_OVERRIDE="gemma3:12b qwen3:14b"   custom Ollama pulls
  SKIP_DIARIZE=1                         same as --skip-diarize
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-ui) START_UI=0 ;;
    --skip-diarize) DO_DIARIZE=0 ;;
    --skip-smoke) DO_SMOKE=0 ;;
    --full) FULL=1 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [[ "${SKIP_DIARIZE:-}" == "1" ]]; then
  DO_DIARIZE=0
fi

if [[ "$FULL" == "1" ]]; then
  MODELS=(gemma3:12b qwen3:14b qwen2.5:14b)
  WHISPER_PRELOAD="turbo"
fi

if [[ -n "${MODELS_OVERRIDE:-}" ]]; then
  # shellcheck disable=SC2206
  MODELS=($MODELS_OVERRIDE)
fi

export PATH="${HOME}/bin:${HOME}/Applications/Ollama.app/Contents/Resources:/usr/local/bin:/opt/homebrew/bin:${PATH}"

log() { printf '\n==> %s\n' "$*"; }
ok() { printf '    OK %s\n' "$*"; }
warn() { printf '    ! %s\n' "$*" >&2; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

# ---------- Python ----------
log "Python venv + pip"
if ! need_cmd python3; then
  echo "python3 not found. Install Python 3.9+ and re-run." >&2
  exit 1
fi
PY_VER="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
ok "python3 $PY_VER"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  ok "created .venv"
else
  ok ".venv already exists"
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -U pip wheel >/dev/null
pip install -r requirements.txt
ok "requirements installed"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

# ---------- Ollama ----------
install_ollama_mac() {
  log "Installing Ollama.app → ~/Applications (no sudo)"
  local zip="/tmp/Ollama-darwin.zip"
  local extract="/tmp/ollama-extract-$$"
  curl -fsSL -o "$zip" https://ollama.com/download/Ollama-darwin.zip
  rm -rf "$extract"
  mkdir -p "$extract" "$HOME/Applications" "$HOME/bin"
  unzip -qo "$zip" -d "$extract"
  rm -rf "$HOME/Applications/Ollama.app"
  if [[ -d "$extract/Ollama.app" ]]; then
    mv "$extract/Ollama.app" "$HOME/Applications/"
  else
    local found
    found="$(find "$extract" -maxdepth 3 -type d -name 'Ollama.app' | head -1)"
    if [[ -z "$found" ]]; then
      echo "Could not find Ollama.app in zip" >&2
      exit 1
    fi
    mv "$found" "$HOME/Applications/"
  fi
  ln -sfn "$HOME/Applications/Ollama.app/Contents/Resources/ollama" "$HOME/bin/ollama"
  rm -rf "$extract"
  ok "Ollama installed"
}

install_ollama_linux() {
  log "Installing Ollama (Linux)"
  if ! need_cmd curl; then
    echo "curl required to install Ollama" >&2
    exit 1
  fi
  if curl -fsSL https://ollama.com/install.sh | sh; then
    ok "Ollama install script finished"
  else
    warn "Auto-install failed — install manually: https://ollama.com/download"
    exit 1
  fi
}

ensure_ollama() {
  if need_cmd ollama; then
    ok "ollama CLI: $(command -v ollama)"
    return
  fi
  case "$(uname -s)" in
    Darwin) install_ollama_mac ;;
    Linux) install_ollama_linux ;;
    *)
      echo "Unsupported OS for auto Ollama install: $(uname -s)" >&2
      echo "Install from https://ollama.com/download then re-run ./setup.sh" >&2
      exit 1
      ;;
  esac
  export PATH="${HOME}/bin:${HOME}/Applications/Ollama.app/Contents/Resources:${PATH}"
  if ! need_cmd ollama; then
    echo "ollama still not on PATH after install" >&2
    exit 1
  fi
}

ensure_ollama_running() {
  if curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    ok "Ollama already running"
    return
  fi
  log "Starting Ollama"
  case "$(uname -s)" in
    Darwin)
      open "$HOME/Applications/Ollama.app" 2>/dev/null || open -a Ollama 2>/dev/null || true
      ;;
    Linux)
      if need_cmd systemctl; then
        sudo systemctl start ollama 2>/dev/null || true
      fi
      if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        nohup ollama serve >/tmp/ollama-serve.log 2>&1 &
        ok "ollama serve background (log: /tmp/ollama-serve.log)"
      fi
      ;;
  esac
  local i
  for i in $(seq 1 40); do
    if curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
      ok "Ollama API up"
      return
    fi
    sleep 1
  done
  echo "Ollama did not start on http://127.0.0.1:11434" >&2
  echo "Open the Ollama app / run: ollama serve" >&2
  exit 1
}

log "Ollama"
ensure_ollama
ensure_ollama_running

log "Pull LLM models: ${MODELS[*]}"
for m in "${MODELS[@]}"; do
  echo "    pulling $m …"
  ollama pull "$m"
done
ok "models ready"

# ---------- Whisper preload ----------
log "Preload Whisper ($WHISPER_PRELOAD) — otherwise first ASR downloads this"
export WHISPER_PRELOAD
python - <<'PY'
import os
from faster_whisper import WhisperModel

for size in os.environ.get("WHISPER_PRELOAD", "turbo").split():
    print(f"    loading Whisper {size} (int8/cpu)…")
    WhisperModel(size, device="cpu", compute_type="int8")
    print(f"    OK Whisper {size}")
PY

# ---------- Diarization ----------
if [[ "$DO_DIARIZE" == "1" ]]; then
  log "Diarization models (sherpa-onnx)"
  bash "$ROOT/scripts/setup_diarization.sh"
else
  warn "Skipping diarization models (--skip-diarize)"
fi

# ---------- Smoke ----------
if [[ "$DO_SMOKE" == "1" ]]; then
  log "Smoke: text → protocol"
  mkdir -p output
  if python run.py --text samples/meeting_with_deadline.txt \
    -o output/smoke_protocol.json --no-polish --output-lang ru; then
    ok "output/smoke_protocol.json"
  else
    warn "Smoke failed — check Ollama model; UI may still work"
  fi
fi

log "Ready"
echo "    UI:     bash scripts/run_ui.sh"
echo "    CLI:    source .venv/bin/activate && python run.py --text samples/meeting_with_deadline.txt -o out.json"
echo "    Offline after this: airplane mode OK (models already local)."

if [[ "$START_UI" == "1" ]]; then
  log "Launching UI"
  exec bash "$ROOT/scripts/run_ui.sh"
fi
