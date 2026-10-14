import os
from functools import cache
from pathlib import Path

# Bigger models are more accurate but slower: tiny, base, small, medium, large-v3.
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")


# Load the model once and reuse it; the first run downloads it (~150 MB for base).
@cache
def _model():
    from faster_whisper import WhisperModel  # slow import; only load when a job asks for a transcript

    return WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")


# Writes the transcript as plain text, one spoken segment per line.
def transcribe(src: Path, dst: Path) -> None:
    segments, _ = _model().transcribe(str(src), vad_filter=True)
    dst.write_text("".join(f"{s.text.strip()}\n" for s in segments))
