#!/usr/bin/env bash
# Launch Phase 4 UI (expects ./setup.sh already run once).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="${HOME}/bin:${HOME}/Applications/Ollama.app/Contents/Resources:${PATH}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

if [[ ! -d .venv ]]; then
  echo "No .venv — run once from repo root:"
  echo "  ./setup.sh"
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "Ollama не отвечает — открываю приложение…"
  open "$HOME/Applications/Ollama.app" 2>/dev/null || open -a Ollama 2>/dev/null || true
  for _ in $(seq 1 20); do
    curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
    sleep 1
  done
fi

if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "Ollama всё ещё недоступна. Запусти: ollama serve   или открой Ollama.app"
  echo "Полная установка: ./setup.sh"
  exit 1
fi

exec streamlit run ui/app.py --server.headless true --browser.gatherUsageStats false
