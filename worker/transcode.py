import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from api.schemas import TranscodeSettings

# Whitelisted key -> FFmpeg value maps; settings are already Literal-validated.
HEIGHTS = {"1080p": "1080", "720p": "720", "480p": "480"}
VIDEO_ENCODERS = {"h264": "libx264"}
AUDIO_ENCODERS = {"mp3": "libmp3lame"}
AUDIO_BITRATE = "128k"
MAX_DURATION_SECONDS = 2 * 3600
FFMPEG_TIMEOUT_SECONDS = 4 * 3600

# Force the MP4 demuxer and local files only, so crafted inputs (e.g. HLS playlists) can't pull in other files or URLs.
SAFE_INPUT = ["-protocol_whitelist", "file", "-f", "mp4"]


# The upload isn't a usable MP4 (shown to the user as a bad-file error).
class InvalidInput(Exception):
    pass


@dataclass
class ProbeInfo:
    duration: float
    has_audio: bool


# Checks the upload with ffprobe before encoding; uploads are untrusted input.
def probe(src: Path) -> ProbeInfo:
    result = subprocess.run(
        ["ffprobe", "-v", "error", *SAFE_INPUT, "-print_format", "json", "-show_format", "-show_streams", str(src)],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise InvalidInput(f"ffprobe failed: {result.stderr.strip()[:500]}")
    info = json.loads(result.stdout)
    types = {s.get("codec_type") for s in info.get("streams", [])}
    duration = float(info.get("format", {}).get("duration") or 0)
    if "video" not in types:
        raise InvalidInput("no video stream")
    if not 0 < duration <= MAX_DURATION_SECONDS:
        raise InvalidInput(f"duration {duration}s out of range")
    return ProbeInfo(duration=duration, has_audio="audio" in types)


# Builds the FFmpeg command as an argument list (never a shell string), so nothing can be injected.
def ffmpeg_args(settings: TranscodeSettings, src: Path, dst: Path) -> list[str]:
    filters = [f"scale=-2:{HEIGHTS[settings.resolution]}"]  # -2 keeps aspect ratio with an even width
    if settings.brightness != "0":
        filters.append(f"eq=brightness={settings.brightness}")
    args = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *SAFE_INPUT, "-i", str(src),
        "-map", "0:v:0", "-map", "0:a:0?", "-map_metadata", "-1",  # drop extra streams and metadata (e.g. GPS)
        "-vf", ",".join(filters),
    ]
    if settings.frame_rate != "original":
        args += ["-r", settings.frame_rate]
    return args + [
        "-c:v", VIDEO_ENCODERS[settings.video_codec], "-preset", settings.encoding_speed, "-crf", settings.quality,
        "-pix_fmt", "yuv420p", "-c:a", AUDIO_ENCODERS[settings.audio_codec], "-b:a", AUDIO_BITRATE,
        "-movflags", "+faststart", str(dst),
    ]


# Encodes src into dst with the chosen settings; raises if FFmpeg fails.
def transcode(settings: TranscodeSettings, src: Path, dst: Path) -> None:
    result = subprocess.run(ffmpeg_args(settings, src, dst), capture_output=True, text=True, timeout=FFMPEG_TIMEOUT_SECONDS)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg exited {result.returncode}: {result.stderr.strip()[:1000]}")
