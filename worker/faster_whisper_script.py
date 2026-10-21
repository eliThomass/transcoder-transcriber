from functools import cache
from faster_whisper import WhisperModel
import json
import os

# Set WHISPER_MODEL=base (or tiny) for faster local runs; medium.en is ~1.5 GB and slow on CPU.
MODEL_SIZE = os.environ.get("WHISPER_MODEL", "medium.en")


# Creates JSON file from the information collected from faster-whisper and returns the JSON file name
def create_json(segments, info, video_file):
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
    # Error handling for when video_file is empty or otherwise invalid
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
    json_transcript_file_name = base + "_transcript.json"

    with open(json_transcript_file_name, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

    return json_transcript_file_name


# Creates SRT file from the information collected from faster-whisper and returns the SRT file name
def create_srt(segments, info, video_file):
    # Error handling for when video_file is empty or otherwise invalid
    if info.duration == 0:
        return None
    
    base, _ = os.path.splitext(video_file)
    srt_transcript_file_name = base + "_transcript.srt"

    with open(srt_transcript_file_name, "w", encoding="utf-8") as file:
        for index, segment in enumerate(segments, start=1):
            # This pattern is the format needed for SRT
            file.write(f"{index}\n")
            file.write(f"{format_timestamp(segment.start)} --> {format_timestamp(segment.end)}\n")
            file.write(f"{segment.text.strip()}\n\n")

    return srt_transcript_file_name


# Formats timestamp from faster_whisper to a format that SRT can understand (HH:MM:SS,mmm)
def format_timestamp(seconds):
    total_ms = round(seconds * 1_000)
    hours, total_ms = divmod(total_ms, 3_600_000)
    minutes, total_ms = divmod(total_ms, 60_000)
    secs, ms = divmod(total_ms, 1_000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


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
    
    segments, info = MODEL.transcribe(video_file, vad_filter=True)

    json_transcript_file_name = create_json(segments, info, video_file)
    srt_transcript_file_name = create_srt(segments, info, video_file)

    return json_transcript_file_name, srt_transcript_file_name
    