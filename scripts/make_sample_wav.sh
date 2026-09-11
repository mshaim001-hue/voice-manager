#!/usr/bin/env bash
# Build ~2 min demo WAV from Russian meeting transcript (macOS say + afconvert).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:-$ROOT/samples/meeting_with_deadline.txt}"
OUT="${2:-$ROOT/samples/sample.wav}"
TMP_AIFF="$(mktemp -t meeting).aiff"

# 3× script + pauses ≈ 2+ minutes at -r 145
BODY="$(cat "$SRC")

Пауза.

$(cat "$SRC")

Пауза.

$(cat "$SRC")"

echo "$BODY" >"${TMP_AIFF}.txt"

echo "Synthesizing speech → $OUT"
VOICE="Milena"
if ! say -v '?' 2>/dev/null | grep -qi "^$VOICE "; then
  VOICE="$(say -v '?' 2>/dev/null | awk '/ru_RU/{print $1; exit}')"
  VOICE="${VOICE:-Samantha}"
fi

say -v "$VOICE" -r 145 -f "${TMP_AIFF}.txt" -o "$TMP_AIFF"
afconvert -f WAVE -d LEI16 "$TMP_AIFF" "$OUT"
rm -f "$TMP_AIFF" "${TMP_AIFF}.txt"

SEC=$(afinfo "$OUT" 2>/dev/null | awk '/estimated duration/{print $3}')
SIZE=$(wc -c <"$OUT" | tr -d ' ')
echo "OK: $OUT (${SEC:-?}s, ${SIZE} bytes, voice=$VOICE)"
