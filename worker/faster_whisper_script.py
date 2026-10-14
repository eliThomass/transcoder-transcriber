from functools import cache
from faster_whisper import WhisperModel
import json
import os

# Set WHISPER_MODEL=base (or tiny) for faster local runs; medium.en is ~1.5 GB and slow on CPU.
MODEL_SIZE = os.environ.get("WHISPER_MODEL", "medium.en")

# Load the model once and reuse it for every job (the first call downloads it).
@cache
def load_model():
    # Run on GPU with FP16
    # model = WhisperModel(MODEL_SIZE, device="cuda", compute_type="float16")
    # or run on GPU with INT8
    # model = WhisperModel(MODEL_SIZE, device="cuda", compute_type="int8_float16")

    # or run on CPU with INT8
    return WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

# Writes <video>_transcript.json next to the video and returns its path (None if there's no audio to transcribe).
def run_faster_whisper(video_file):
    MODEL = load_model()
    
    segments, info = MODEL.transcribe(video_file)

    transcript_segments = []
    transcript_text = []
    
    for segment in segments:
        transcript_segments.append({
            "start": round(segment.start, 2),
            "end": round(segment.end, 2),
            "text": segment.text.strip()
        })
        transcript_text.append(segment.text.strip())
    
    transcript = "\n".join(transcript_text)    
    word_count = len(transcript.split())
    
    duration_seconds = info.duration
    if duration_seconds == 0:
        return None

    duration_minutes = duration_seconds / 60
    speech_rate = word_count / duration_minutes

    data = {
        "transcript_metadata": {
            "speech_rate_wpm": speech_rate,
            "word_count": word_count,
            "transcript": transcript,
            "segments": transcript_segments,
        }
    }   

    base, _ = os.path.splitext(video_file)
    transcript_file_name = base + "_transcript.json"

    with open(transcript_file_name, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

    return transcript_file_name
    