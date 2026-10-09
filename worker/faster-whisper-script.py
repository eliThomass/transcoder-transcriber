from faster_whisper import WhisperModel
import json

def run_faster_whisper(video_file, transcript):
    MODEL_SIZE = "medium.en"
    # Run on GPU with FP16
    # model = WhisperModel(MODEL_SIZE, device="cuda", compute_type="float16")
    # or run on GPU with INT8
    # model = WhisperModel(MODEL_SIZE, device="cuda", compute_type="int8_float16")

    # or run on CPU with INT8
    MODEL = WhisperModel(
        MODEL_SIZE,
        device="cpu",
        compute_type="int8"
    )
    
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

    with open(transcript, "r", encoding="utf-8") as file:
        data = json.load(file)

    if "transcript_metadata" not in data:
        data["transcript_metadata"] = {}

    duration_seconds = info.duration
    if duration_seconds == 0:
        return 0
    
    duration_minutes = duration_seconds / 60
    speech_rate = word_count / duration_minutes

    data["transcript_metadata"]["speech_rate_wpm"] = speech_rate
    data["transcript_metadata"]["word_count"] = word_count
    data["transcript_metadata"]["transcript"] = transcript
    data["transcript_metadata"]["segments"] = transcript_segments    

    with open(transcript, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)
