"""Diarization merge unit tests — no models required."""

from asr.diarize import SpeakerTurn, TimedSegment, merge_transcript, speaker_label


def test_speaker_label_one_based():
    assert speaker_label(0) == "Спикер 1"
    assert speaker_label(1) == "Спикер 2"


def test_merge_transcript_labels_speakers():
    segments = [
        TimedSegment(0.0, 1.0, "Привет"),
        TimedSegment(1.0, 2.0, "от Анны"),
        TimedSegment(2.5, 3.5, "Ответ Бориса"),
        TimedSegment(3.5, 4.5, "про токены"),
    ]
    turns = [
        SpeakerTurn(0.0, 2.2, 0),
        SpeakerTurn(2.3, 5.0, 1),
    ]
    text = merge_transcript(segments, turns)
    assert "Спикер 1:" in text
    assert "Спикер 2:" in text
    assert "Привет" in text
    assert "Бориса" in text
