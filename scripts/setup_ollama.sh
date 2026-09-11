#!/usr/bin/env bash
# Phase 0 — Ollama + candidate models (Apple Silicon / 24GB)
set -euo pipefail

export PATH="${HOME}/bin:${HOME}/Applications/Ollama.app/Contents/Resources:${PATH}"

if [[ -n "${MODELS_OVERRIDE:-}" ]]; then
  # shellcheck disable=SC2206
  MODELS=($MODELS_OVERRIDE)
else
  MODELS=(gemma3:12b qwen3:14b qwen2.5:14b)
fi

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama CLI not found."
  echo "Install app to ~/Applications (no sudo):"
  echo "  curl -fsSL -o /tmp/Ollama.zip https://ollama.com/download/Ollama-darwin.zip"
  echo "  unzip -o /tmp/Ollama.zip -d /tmp/ollama-extract"
  echo "  mkdir -p ~/Applications ~/bin"
  echo "  rm -rf ~/Applications/Ollama.app && mv /tmp/ollama-extract/Ollama.app ~/Applications/"
  echo "  ln -sfn ~/Applications/Ollama.app/Contents/Resources/ollama ~/bin/ollama"
  echo "  open ~/Applications/Ollama.app"
  exit 1
fi

if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "Starting Ollama.app..."
  open "$HOME/Applications/Ollama.app" 2>/dev/null || open -a Ollama || true
  for _ in $(seq 1 20); do
    curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
    sleep 1
  done
fi

for m in "${MODELS[@]}"; do
  echo "Pulling: $m"
  ollama pull "$m"
done

echo "Smoke: gemma3:12b"
ollama run gemma3:12b "Reply with one word: ok"

echo "OK — Phase 0 gate ready. Default model in code: gemma3:12b"
echo "A/B: source .venv/bin/activate && python scripts/ab_models.py"
