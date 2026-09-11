#!/usr/bin/env bash
# Two-speaker demo WAV (Milena + Yuri) for diarization gate.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/samples/sample_2speakers.wav}"
TMPDIR=$(mktemp -d)

cat >"$TMPDIR/a.txt" <<'EOF'
Анна: Нужно зафиксировать релиз мобильного онбординга. Предлагаю выкатить в прод в пятницу.
EOF
cat >"$TMPDIR/b.txt" <<'EOF'
Борис: Согласен, бэкенд готов. Я до среды закрою баг с токенами, приоритет высокий.
EOF
cat >"$TMPDIR/c.txt" <<'EOF'
Анна: Тогда решение — релиз в пятницу. Открытый вопрос — нужна ли анимация лоадера.
EOF
cat >"$TMPDIR/d.txt" <<'EOF'
Борис: Changelog тоже надо обновить, но ответственного пока не назначили и срока нет.
EOF

VOICE_A="Milena"
VOICE_B="Lesya"
say -v '?' 2>/dev/null | grep -qi "^$VOICE_A " || VOICE_A="Samantha"
say -v '?' 2>/dev/null | grep -qi "^$VOICE_B " || VOICE_B="Alex"

say -v "$VOICE_A" -r 160 -f "$TMPDIR/a.txt" -o "$TMPDIR/a.aiff"
say -v "$VOICE_B" -r 160 -f "$TMPDIR/b.txt" -o "$TMPDIR/b.aiff"
say -v "$VOICE_A" -r 160 -f "$TMPDIR/c.txt" -o "$TMPDIR/c.aiff"
say -v "$VOICE_B" -r 160 -f "$TMPDIR/d.txt" -o "$TMPDIR/d.aiff"

for x in a b c d; do
  afconvert -f WAVE -d LEI16 "$TMPDIR/$x.aiff" "$TMPDIR/$x.wav"
done

# Concatenate with sox if present, else python
if command -v sox >/dev/null 2>&1; then
  sox "$TMPDIR/a.wav" "$TMPDIR/b.wav" "$TMPDIR/c.wav" "$TMPDIR/d.wav" "$OUT"
else
  python3 - <<PY
import wave
from pathlib import Path
parts = [Path("$TMPDIR")/f"{x}.wav" for x in "abcd"]
out = Path("$OUT")
with wave.open(str(parts[0]), "rb") as w0:
    params = w0.getparams()
    frames = [w0.readframes(w0.getnframes())]
for p in parts[1:]:
    with wave.open(str(p), "rb") as w:
        frames.append(w.readframes(w.getnframes()))
with wave.open(str(out), "wb") as wo:
    wo.setparams(params)
    for f in frames:
        wo.writeframes(f)
print("wrote", out)
PY
fi

rm -rf "$TMPDIR"
afinfo "$OUT" | awk '/estimated duration/'
echo "OK: $OUT (voices $VOICE_A / $VOICE_B)"
