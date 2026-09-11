# AI Meeting Intelligence

Локальный ИИ-протоколист совещаний: **файл/текст → JSON-протокол → экспорт**. 100% offline (Ollama + Faster-Whisper).

## Стек (эта машина: Apple M4, 24 GB)

| Компонент | Выбор | Почему |
|-----------|--------|--------|
| LLM | `gemma3:12b` (A/B: `qwen3:14b`, `qwen2.5:14b`) | JSON + RU/KK; 12–14B свободно рядом с Whisper turbo. Опционально `gemma3:27b` (~17 GB) |
| ASR | Faster-Whisper **`turbo`** (large-v3-turbo int8) | Существенно точнее `small`; `large-v3` — максимум качества |
| Пайплайн | строго последовательно | Whisper → потом Ollama, не вместе |

## Быстрый старт (для коллег)

```bash
git clone https://github.com/mshaim001-hue/voice-manager.git
cd voice-manager
./setup.sh
```

Скрипт сам: создаст `.venv`, поставит зависимости, поставит/запустит **Ollama**, скачает `gemma3:12b`, прогреет Whisper `turbo`, подтянет модели диаризации и откроет UI.

Полезные флаги:

```bash
./setup.sh --no-ui          # только установка, без Streamlit
./setup.sh --full           # + qwen3:14b, qwen2.5:14b
./setup.sh --skip-diarize   # без моделей спикеров
```

Потом снова UI: `bash scripts/run_ui.sh`

## Ручная установка (если нужно)

```bash
# 1) Python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2) Ollama (один раз; brew на этой машине без sudo — не используем)
# App уже можно поставить в ~/Applications — см. scripts/setup_ollama.sh
bash scripts/setup_ollama.sh   # тянет gemma3:12b + qwen3:14b + qwen2.5:14b

# 3) Фаза 1 — протокол из текста
python run.py --text samples/meeting_with_deadline.txt -o output/protocol.json

# A/B трёх моделей на 3 samples
python scripts/ab_models.py

# 4) Фаза 2 — аудио → протокол
bash scripts/make_sample_wav.sh   # ~2 мин WAV (macOS say)
python run.py --audio samples/sample.wav -o output/protocol_from_audio.json \
  --save-transcript output/asr_transcript.txt

# 5) Фаза 3 — экспорт json/csv/pdf
python scripts/export_protocol.py output/protocol_from_audio.json -d output/export
# или сразу: python run.py --text samples/... -o output/p.json --export-dir output/export

# 6) Фаза 4 — UI
bash scripts/run_ui.sh
# откроется http://localhost:8501
```

## CLI

```bash
python run.py --text path/to/transcript.txt -o protocol.json
python run.py --audio samples/sample.wav -o protocol.json --whisper-model turbo --language ru --export-dir output/export
python run.py --audio samples/sample_2speakers.wav --diarize --num-speakers 2 --language ru \
  --whisper-model turbo -o output/protocol_diarized.json --save-transcript output/asr_diarized.txt
python scripts/export_protocol.py protocol.json -d output/export
bash scripts/run_ui.sh
```

Переменные: `OLLAMA_HOST`, `OLLAMA_MODEL` (default `gemma3:12b`), `WHISPER_MODEL` (default `turbo`), `WHISPER_LANGUAGE`, `DIARIZATION_MODELS_DIR`.

## Структура

```
ingest/   # загрузка текста (аудио — фаза 2)
asr/      # Faster-Whisper
llm/      # промпт + Ollama + 1 retry
schema/   # Pydantic MeetingProtocol
export/   # json/csv/pdf (фаза 3)
ui/       # один экран (фаза 4)
samples/  # тестовые транскрипты
```

## Airplane-mode чеклист (демо offline)

1. До демо: `ollama pull gemma3:12b` (и кандидаты) + Whisper `turbo` заранее.
2. Включить **Режим полёта** (или отключить Wi‑Fi + Ethernet).
3. Убедиться, что `ollama serve` уже запущен локально.
4. На записи экрана: System Settings → Network = disconnected / airplane.
5. Прогон: `python run.py --text samples/meeting_with_deadline.txt` → `protocol.json`.
6. Доказательство: в Activity Monitor / `lsof` нет исходящих к внешним API; Ollama только `127.0.0.1:11434`.
7. Запасной путь: только текст (если ASR тормозит) — тот же CLI `--text`.

## Гейты

| Фаза | Гейт |
|------|------|
| 0 | `ollama run gemma3:12b` отвечает локально |
| 1 | 3 текста из `samples/` → валидный JSON, без выдуманных deadline/assignee |
| 2 | `sample.wav` → protocol.json без копипаста (~2 мин аудио; замер wall time в CLI) |
| 3 | json + csv + pdf открываются, поля совпадают (`scripts/export_protocol.py`) |
| 4 | путь в UI <1 мин кликов (`bash scripts/run_ui.sh`) |
| 5 | `--diarize` → в транскрипте видно «Спикер 1/2» (`samples/sample_2speakers.wav`) |

## Тесты схемы (без LLM)

```bash
pip install pytest
pytest tests/ -q
```
